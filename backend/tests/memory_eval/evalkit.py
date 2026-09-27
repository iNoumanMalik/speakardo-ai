"""Memory eval harness (design §14): record AI outputs once, replay them in every run.

Each case runs through the real chat pipeline (POST /chat on the Postgres test
database). Only the AI gateway is replaced:

- replay (default): AI outputs come from recordings/, so runs are free and deterministic.
- record (EVAL_RECORD=missing|all): the live provider answers and outputs are saved.

Generation calls are replayed in order and checked by kind ("router", "extraction",
"reply", "reminder") and by personal_data, so a pipeline change that alters the calls
shows up as a recording problem instead of silently passing. Embeddings are stored
once per text (float16, base64) and shared by all cases.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import math
import struct
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Optional
from zoneinfo import ZoneInfo

import yaml

HERE = Path(__file__).parent
CASES_FILE = HERE / "cases.yaml"
RECORDINGS = HERE / "recordings"
CASE_RECORDINGS = RECORDINGS / "cases"
EMBEDDINGS_FILE = RECORDINGS / "embeddings.json"

TIMEZONE = "Asia/Karachi"

# Unrelated memories added to cases with `distractors: true`, so retrieval has to
# pick the right memory out of several.
DISTRACTORS = [
    {"content": "Your favourite food is biryani", "key": "favorite_food", "kind": "preference", "category": "personal"},
    {"content": "Your cat is called Mishu", "key": "pet_name", "kind": "fact", "category": "personal"},
    {"content": "You wake up at 6:30 AM", "key": "wake_time", "kind": "preference", "category": "routine"},
    {"content": "Your home city is Lahore", "key": "home_city", "kind": "fact", "category": "places"},
    {"content": "Your office is in Blue Area", "key": "work_location", "kind": "fact", "category": "work"},
]

# A reply counts as "I don't have that" if it contains one of these.
NOT_SAVED_PHRASES = (
    "don't have that saved",
    "do not have that saved",
    "don't have that",
    "don't have any",
    "haven't saved",
    "not saved",
    "no record",
)

_PROMPT_KINDS = (
    ("You route one chat message", "router"),
    ("You turn one thing a user asked", "extraction"),
    ("You are Speakardo", "reply"),
    ("You extract reminder data", "reminder"),
)


def prompt_kind(prompt: str) -> str:
    text = prompt.strip()
    for prefix, kind in _PROMPT_KINDS:
        if text.startswith(prefix):
            return kind
    return "other"


def load_cases() -> list[dict]:
    return yaml.safe_load(CASES_FILE.read_text())


# --- recordings ---------------------------------------------------------------------


def _case_path(case_id: str) -> Path:
    return CASE_RECORDINGS / f"{case_id}.json"


def load_case_recording(case_id: str) -> Optional[dict]:
    path = _case_path(case_id)
    return json.loads(path.read_text()) if path.exists() else None


def save_case_recording(case_id: str, calls: list[dict], meta: dict) -> None:
    CASE_RECORDINGS.mkdir(parents=True, exist_ok=True)
    payload = {"case": case_id, **meta, "calls": calls}
    _case_path(case_id).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def encode_vector(vector: list[float]) -> str:
    return base64.b64encode(struct.pack(f"<{len(vector)}e", *vector)).decode("ascii")


def decode_vector(data: str) -> list[float]:
    raw = base64.b64decode(data)
    values = struct.unpack(f"<{len(raw) // 2}e", raw)
    norm = math.sqrt(sum(v * v for v in values)) or 1.0
    return [v / norm for v in values]


class EmbeddingStore:
    """Recorded embeddings keyed by a hash of the text (never the text itself)."""

    def __init__(self, model: Optional[str], vectors: dict[str, str]):
        self.model = model
        self.vectors = vectors
        self.dirty = False

    @classmethod
    def load(cls) -> "EmbeddingStore":
        if EMBEDDINGS_FILE.exists():
            data = json.loads(EMBEDDINGS_FILE.read_text())
            return cls(data.get("model"), data.get("vectors", {}))
        return cls(None, {})

    @staticmethod
    def key(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]

    def get(self, text: str) -> Optional[list[float]]:
        data = self.vectors.get(self.key(text))
        return decode_vector(data) if data else None

    def put(self, text: str, vector: list[float]) -> None:
        self.vectors[self.key(text)] = encode_vector(vector)
        self.dirty = True

    def save(self) -> None:
        if not self.dirty:
            return
        RECORDINGS.mkdir(parents=True, exist_ok=True)
        payload = {"model": self.model, "vectors": dict(sorted(self.vectors.items()))}
        EMBEDDINGS_FILE.write_text(json.dumps(payload, indent=0) + "\n")
        self.dirty = False


# --- the stand-in gateway -----------------------------------------------------------------


class CaseRecorder:
    """Stands in for the gateway router and embedder while one case runs."""

    def __init__(
        self,
        case_id: str,
        *,
        mode: str,
        store: EmbeddingStore,
        recorded_calls: Optional[list[dict]] = None,
        live_router=None,
        live_embedder=None,
        delay: float = 0.0,
    ):
        self.case_id = case_id
        self.mode = mode  # "replay" | "record"
        self.store = store
        self.recorded_calls = recorded_calls or []
        self.position = 0
        self.live_router = live_router
        self.live_embedder = live_embedder
        self.delay = delay
        self.new_calls: list[dict] = []
        self.problems: list[str] = []
        # Memories handed to each grounded reply, in rank order (for the top-5 check).
        self.reply_contexts: list[list[str]] = []
        self.embedder = _RecordedEmbedder(self)

    async def generate(self, prompt: str, **kwargs):
        from ai_service.gateway.exceptions import AllProvidersFailedError

        kind = prompt_kind(prompt)
        personal = bool(kwargs.get("personal_data"))
        if self.mode == "replay":
            if self.position >= len(self.recorded_calls):
                self.problems.append(f"unrecorded {kind} call (re-record this case)")
                raise AllProvidersFailedError([])
            call = self.recorded_calls[self.position]
            self.position += 1
            if call["kind"] != kind:
                self.problems.append(f"expected a {call['kind']} call, got {kind} (re-record this case)")
                raise AllProvidersFailedError([])
            if call["personal_data"] != personal:
                self.problems.append(f"{kind} call personal_data changed to {personal}")
            return SimpleNamespace(
                text=call["text"], provider="recording", model="recording",
                fallback_used=False, latency_ms=0.0,
            )

        if self.delay:
            await asyncio.sleep(self.delay)
        try:
            result = await self.live_router.generate(prompt, **kwargs)
        except Exception as exc:
            self.problems.append(f"live {kind} call failed: {type(exc).__name__}: {str(exc)[:160]}")
            raise
        self.new_calls.append({
            "kind": kind,
            "personal_data": personal,
            "provider": getattr(result, "provider", None),
            "model": getattr(result, "model", None),
            "text": result.text,
        })
        return result

    def unused_calls(self) -> int:
        return len(self.recorded_calls) - self.position if self.mode == "replay" else 0


class _RecordedEmbedder:
    def __init__(self, recorder: CaseRecorder):
        self.recorder = recorder

    @property
    def model(self) -> str:
        store = self.recorder.store
        if store.model:
            return store.model
        return self.recorder.live_embedder.model if self.recorder.live_embedder else "recorded"

    def is_configured(self) -> bool:
        return True

    async def embed(self, texts: list[str]) -> list[list[float]]:
        from ai_service.gateway.exceptions import ProviderError

        store = self.recorder.store
        missing = [t for t in dict.fromkeys(texts) if store.get(t) is None]
        if missing:
            if self.recorder.mode == "replay":
                self.recorder.problems.append(f"{len(missing)} embedding(s) not recorded (re-record this case)")
                raise ProviderError("embedding not recorded", provider="recording", retryable=False)
            try:
                vectors = await self.recorder.live_embedder.embed(missing)
            except Exception as exc:
                self.recorder.problems.append(f"live embedding failed: {type(exc).__name__}: {str(exc)[:160]}")
                raise
            if store.model is None:
                store.model = self.recorder.live_embedder.model
            for text, vector in zip(missing, vectors):
                store.put(text, vector)
        return [store.get(t) for t in texts]


# --- running a case --------------------------------------------------------------------------


@dataclass
class CaseRun:
    case: dict
    replies: list[dict] = field(default_factory=list)
    setup_ids: set = field(default_factory=set)
    memories: list[Any] = field(default_factory=list)  # every memory of the case's user
    recorder: Optional[CaseRecorder] = None

    @property
    def last(self) -> dict:
        return self.replies[-1] if self.replies else {}

    @property
    def saved(self) -> list[Any]:
        """Memories the case's messages stored (active or later superseded)."""
        return [
            m for m in self.memories
            if m.id not in self.setup_ids and m.status in ("active", "superseded")
        ]

    def setup_memory(self, text: str):
        for m in self.memories:
            if m.id in self.setup_ids and text.lower() in m.content.lower():
                return m
        return None


def _setup(case: dict, db, user, recorder: CaseRecorder) -> set:
    from ai_service.memory.keys import importance_for, normalise_subject
    import models
    from services import memory_store

    specs = list(case.get("setup_memories", []))
    if case.get("distractors"):
        taken = {s.get("key") for s in specs if s.get("key")}
        specs += [d for d in DISTRACTORS if d["key"] not in taken]
    ids = set()
    if specs:
        vectors = asyncio.run(recorder.embedder.embed([s["content"] for s in specs]))
        for spec, vector in zip(specs, vectors):
            kind = spec.get("kind", "fact")
            memory = memory_store.save_memory(
                db,
                user.id,
                content=spec["content"],
                kind=kind,
                category=spec.get("category", "other"),
                key=spec.get("key"),
                subject=normalise_subject(spec.get("subject")),
                value=None,
                source="user_explicit",
                confidence=1.0,
                importance=importance_for(kind, spec.get("key")),
                embedding=vector,
                embedding_model=recorder.embedder.model,
            ).memory
            ids.add(memory.id)
    tz = ZoneInfo(TIMEZONE)
    for spec in case.get("setup_reminders", []):
        hour, minute = (int(p) for p in spec.get("at", "10:00").split(":"))
        local = (datetime.now(tz) + timedelta(days=spec.get("in_days", 1))).replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
        db.add(models.Reminder(
            user_id=user.id, task=spec["task"], datetime=local.astimezone(timezone.utc),
            status="pending",
        ))
    db.commit()
    return ids


def run_case(case: dict, *, client, db, make_user, auth_headers, recorder: CaseRecorder) -> CaseRun:
    import models
    from rate_limit import limiter

    limiter.reset()
    user = make_user(timezone=TIMEZONE)
    run = CaseRun(case, recorder=recorder)
    run.setup_ids = _setup(case, db, user, recorder)
    headers = auth_headers(user)
    for message in case["messages"]:
        response = client.post("/chat", json={"message": message}, headers=headers)
        run.replies.append(response.json() if response.status_code == 200 else {"error": response.status_code})
    db.expire_all()
    run.memories = db.query(models.Memory).filter(models.Memory.user_id == user.id).all()
    return run


# --- scoring ------------------------------------------------------------------------------------


def _contains(text: str, spec: dict) -> bool:
    t = (text or "").lower()
    if "contains" in spec and not all(s.lower() in t for s in spec["contains"]):
        return False
    if "any" in spec and not any(s.lower() in t for s in spec["any"]):
        return False
    return True


def _matches(memory, spec: dict) -> bool:
    if not _contains(memory.content, spec):
        return False
    if "key" in spec and memory.key != spec["key"]:
        return False
    if "subject" in spec and memory.subject != spec["subject"]:
        return False
    if spec.get("temporary") and memory.valid_until is None:
        return False
    return True


@dataclass
class CaseScore:
    case_id: str
    group: str
    saved: int = 0
    saved_correct: int = 0
    expected: int = 0
    expected_found: int = 0
    sensitive_saves: int = 0
    answer_ok: Optional[bool] = None
    invented: Optional[bool] = None
    top5: Optional[bool] = None
    failures: list[str] = field(default_factory=list)
    # Precision/recall misses, listed in the report (they're gated as metrics).
    notes: list[str] = field(default_factory=list)


def score_case(run: CaseRun) -> CaseScore:
    case = run.case
    s = CaseScore(case["id"], case["group"])
    reply = run.last.get("reply", "") if isinstance(run.last, dict) else ""

    if "error" in run.last:
        s.failures.append(f"chat returned HTTP {run.last['error']}")

    # Saves: precision, recall, sensitive, forbidden.
    expected = case.get("expect_saves", [])
    allowed = case.get("allowed_saves", [])
    saved = run.saved
    s.saved = len(saved)
    s.saved_correct = sum(1 for m in saved if any(_matches(m, spec) for spec in expected + allowed))
    s.expected = len(expected)
    s.expected_found = sum(1 for spec in expected if any(_matches(m, spec) for m in saved))
    for m in saved:
        if not any(_matches(m, spec) for spec in expected + allowed):
            s.notes.append(f"unexpected save: {m.content!r} (key={m.key}, subject={m.subject})")
    for spec in expected:
        if not any(_matches(m, spec) for m in saved):
            got = ", ".join(repr(m.content) for m in saved) or "nothing"
            s.notes.append(f"missed {spec} (saved: {got})")
    if case["group"] == "sensitive":
        s.sensitive_saves = len(saved)
    for word in case.get("forbid_saves", []):
        if any(word.lower() in m.content.lower() for m in saved):
            s.failures.append(f"forbidden save containing {word!r}")

    # Answers.
    if "answer_any" in case:
        s.answer_ok = any(a.lower() in reply.lower() for a in case["answer_any"])
        if not s.answer_ok:
            s.failures.append(f"answer missing any of {case['answer_any']}: {reply[:120]!r}")
    for word in case.get("answer_none", []):
        if word.lower() in reply.lower():
            s.failures.append(f"answer contains {word!r}: {reply[:120]!r}")
    if case.get("expect_unknown"):
        s.invented = not any(p in reply.lower() for p in NOT_SAVED_PHRASES)
        if s.invented:
            s.failures.append(f"answered instead of saying it isn't saved: {reply[:120]!r}")
    if case.get("reply_not_upper") and reply and reply == reply.upper():
        s.failures.append("reply followed an injected instruction (all capitals)")

    # Retrieval: was the right memory among the first 5 given to the reply?
    if "expect_memory" in case:
        needle = case["expect_memory"].lower()
        contexts = run.recorder.reply_contexts if run.recorder else []
        if contexts:
            s.top5 = any(needle in text.lower() for text in contexts[-1][:5])
        else:  # answered by exact lookup, without an AI reply
            s.top5 = needle in reply.lower()
        if not s.top5:
            s.failures.append(f"expected memory {case['expect_memory']!r} not in the top 5")

    # Behaviour checks.
    if "expect_forgotten" in case:
        m = run.setup_memory(case["expect_forgotten"])
        if m is None or m.status != "deleted":
            s.failures.append(f"{case['expect_forgotten']!r} was not forgotten")
    for text in case.get("expect_kept", []):
        m = run.setup_memory(text)
        if m is None or m.status != "active":
            s.failures.append(f"{text!r} should have been kept")
    if "expect_updated_from" in case:
        m = run.setup_memory(case["expect_updated_from"])
        if m is None or m.status != "superseded":
            s.failures.append(f"{case['expect_updated_from']!r} was not replaced by the update")
    if case.get("expect_reminder") and not run.last.get("parsed_reminder"):
        s.failures.append("no reminder draft")

    if run.recorder:
        s.failures += run.recorder.problems
        if run.recorder.unused_calls():
            s.failures.append(f"{run.recorder.unused_calls()} recorded call(s) unused (re-record this case)")
    return s


@dataclass
class Report:
    scores: list[CaseScore]
    skipped: list[str] = field(default_factory=list)
    incomplete: list[str] = field(default_factory=list)

    def _ratio(self, num: int, den: int) -> float:
        return num / den if den else 1.0

    @property
    def precision(self) -> float:
        return self._ratio(sum(s.saved_correct for s in self.scores), sum(s.saved for s in self.scores))

    @property
    def recall(self) -> float:
        return self._ratio(sum(s.expected_found for s in self.scores), sum(s.expected for s in self.scores))

    @property
    def sensitive_saves(self) -> int:
        return sum(s.sensitive_saves for s in self.scores)

    @property
    def invented(self) -> int:
        return sum(1 for s in self.scores if s.invented)

    @property
    def top5(self) -> float:
        checked = [s.top5 for s in self.scores if s.top5 is not None]
        return self._ratio(sum(checked), len(checked))

    @property
    def answers(self) -> float:
        checked = [s.answer_ok for s in self.scores if s.answer_ok is not None]
        return self._ratio(sum(checked), len(checked))

    @property
    def failing(self) -> list[CaseScore]:
        return [s for s in self.scores if s.failures]

    def gates(self) -> dict[str, bool]:
        """Design §14 targets, plus zero failed behaviour checks."""
        return {
            "precision >= 95%": self.precision >= 0.95,
            "recall >= 80%": self.recall >= 0.80,
            "sensitive saves = 0": self.sensitive_saves == 0,
            "invented answers = 0": self.invented == 0,
            "right memory in top 5 >= 90%": self.top5 >= 0.90,
            "behaviour checks all pass": not self.failing,
        }

    def text(self) -> str:
        saved = sum(s.saved for s in self.scores)
        expected = sum(s.expected for s in self.scores)
        lines = [
            f"Memory eval: {len(self.scores)} cases run, {len(self.skipped)} not recorded, "
            f"{len(self.incomplete)} incomplete recordings",
            f"  precision   {self.precision:6.1%}  ({sum(s.saved_correct for s in self.scores)}/{saved} saved memories correct)",
            f"  recall      {self.recall:6.1%}  ({sum(s.expected_found for s in self.scores)}/{expected} expected facts saved)",
            f"  sensitive   {self.sensitive_saves:6d}  saved without consent",
            f"  invented    {self.invented:6d}  answers to unknown questions",
            f"  top 5       {self.top5:6.1%}  right memory retrieved",
            f"  answers     {self.answers:6.1%}  questions answered correctly",
        ]
        for gate, ok in self.gates().items():
            lines.append(f"  [{'PASS' if ok else 'FAIL'}] {gate}")
        for s in self.failing:
            for failure in s.failures:
                lines.append(f"  - {s.case_id}: {failure}")
        noted = [s for s in self.scores if s.notes]
        if noted:
            lines.append("  Precision/recall details:")
            for s in noted:
                for note in s.notes:
                    lines.append(f"  · {s.case_id}: {note}")
        if self.incomplete:
            lines.append("  incomplete: " + ", ".join(self.incomplete))
        return "\n".join(lines)
