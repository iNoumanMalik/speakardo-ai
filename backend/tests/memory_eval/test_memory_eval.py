"""Memory eval (design §14): 100 recorded cases, gated on the quality targets.

Replay (default, free, deterministic):
    pytest tests/memory_eval -s

Record with the live provider (costs AI calls; run before and after any prompt or
model change):
    EVAL_RECORD=missing pytest tests/memory_eval -s   # only cases with no recording
    EVAL_RECORD=all     pytest tests/memory_eval -s   # re-record everything

Optional while recording:
    EVAL_GEMINI_MODEL=gemini-2.5-flash-lite   model to record with (overrides .env)
    EVAL_RECORD_DELAY=4.5                     seconds between AI calls (free-tier limits)
    EVAL_CASES=explicit-01,question-02        only these cases (recording or debugging)

A case whose live calls fail (e.g. quota exhausted) isn't saved; run again later
with EVAL_RECORD=missing to finish.
"""

import os
import sys
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

import routers.chat
import services.memory_chat as memory_chat
from ai_service.gateway import factory
from ai_service.memory.extraction import extract_memory
from ai_service.parsing import layer3_llm
from ai_service.reply.grounded import generate_reply
from ai_service.router.turn import route_turn

from evalkit import (
    CaseRecorder,
    EmbeddingStore,
    Report,
    load_case_recording,
    load_cases,
    run_case,
    save_case_recording,
    score_case,
)

# Captured at import, before conftest's block_real_ai replaces them for each test.
REAL_EMBED = memory_chat._embed
REAL_GET_ROUTER = factory.get_default_router
REAL_GET_EMBEDDER = factory.get_default_embedder

MODE = os.getenv("EVAL_RECORD", "").strip().lower()  # "" | "missing" | "all"
ONLY = {c.strip() for c in os.getenv("EVAL_CASES", "").split(",") if c.strip()}
GROUP_SIZES = {
    "explicit_save": 20, "stated_fact": 15, "update": 10, "temporary": 5, "sensitive": 10,
    "implied": 10, "injection": 5, "question": 10, "unknown": 5, "forget": 5, "reminder": 5,
}


def test_case_file_is_well_formed():
    cases = load_cases()
    ids = [c["id"] for c in cases]
    assert len(cases) == 100
    assert len(set(ids)) == len(ids)
    counts: dict[str, int] = {}
    for case in cases:
        counts[case["group"]] = counts.get(case["group"], 0) + 1
        assert case["messages"], case["id"]
    assert counts == GROUP_SIZES


def _live_gateway():
    if os.getenv("EVAL_GEMINI_MODEL"):
        os.environ["GEMINI_MODEL"] = os.environ["EVAL_GEMINI_MODEL"]
    REAL_GET_ROUTER.cache_clear()
    REAL_GET_EMBEDDER.cache_clear()
    return REAL_GET_ROUTER(), REAL_GET_EMBEDDER()


def test_memory_eval(client, db_session, make_user, auth_headers, monkeypatch):
    live_router = live_embedder = None
    if MODE:
        assert MODE in ("missing", "all"), "EVAL_RECORD must be 'missing' or 'all'"
        live_router, live_embedder = _live_gateway()
    delay = float(os.getenv("EVAL_RECORD_DELAY", "4.5"))
    store = EmbeddingStore.load()
    current = {"recorder": None}

    # The real pipeline, with only the AI gateway replaced by the recorder.
    monkeypatch.setattr(routers.chat, "route_turn", route_turn)
    monkeypatch.setattr(memory_chat, "extract_memory", extract_memory)
    monkeypatch.setattr(memory_chat, "_embed", REAL_EMBED)
    monkeypatch.setattr(factory, "get_default_router", lambda: current["recorder"])
    monkeypatch.setattr(layer3_llm, "get_default_router", lambda: current["recorder"])
    monkeypatch.setattr(factory, "get_default_embedder", lambda: current["recorder"].embedder)

    async def capture_reply(message, **kwargs):
        current["recorder"].reply_contexts.append([m.text for m in kwargs.get("memories", [])])
        return await generate_reply(message, **kwargs)

    monkeypatch.setattr(memory_chat, "_generate_reply", capture_reply)

    report = Report(scores=[])
    for case in load_cases():
        if ONLY and case["id"] not in ONLY:
            continue
        recording = load_case_recording(case["id"])
        record = MODE == "all" or (MODE == "missing" and recording is None)
        if not record and recording is None:
            report.skipped.append(case["id"])
            continue
        recorder = CaseRecorder(
            case["id"],
            mode="record" if record else "replay",
            store=store,
            recorded_calls=None if record else recording["calls"],
            live_router=live_router,
            live_embedder=live_embedder,
            delay=delay,
        )
        current["recorder"] = recorder
        run = run_case(
            case, client=client, db=db_session, make_user=make_user,
            auth_headers=auth_headers, recorder=recorder,
        )
        if record:
            if recorder.problems:
                report.incomplete.append(case["id"])
                print(f"[eval] {case['id']}: not saved: {recorder.problems[0]}")
                continue
            save_case_recording(case["id"], recorder.new_calls, {
                "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "embedding_model": store.model,
            })
            store.save()
            print(f"[eval] {case['id']}: recorded {len(recorder.new_calls)} call(s)")
        report.scores.append(score_case(run))

    store.save()
    print("\n" + report.text())
    if not report.scores:
        pytest.skip("No recordings yet. Record with: EVAL_RECORD=missing pytest tests/memory_eval -s")
    failed = [gate for gate, ok in report.gates().items() if not ok]
    assert not failed, f"Memory eval gates failed: {failed}\n{report.text()}"
