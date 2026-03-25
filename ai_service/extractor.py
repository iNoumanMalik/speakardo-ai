import os
import json
import re
import logging
from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta
from typing import Any, Optional


try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None

logger = logging.getLogger(__name__)

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if genai and api_key:

    client = genai.Client(api_key=api_key)
    try:
        models = client.models.list()
        available_models = [m.name for m in models if "gemini" in m.name]
        print(f"Available Gemini models: {available_models}")
        
        # Choose the best available (prioritized order)
        if "models/gemini-2.5-flash" in available_models:
            model_name = "models/gemini-2.5-flash"  # Latest flash (fast & capable)
        elif "models/gemini-flash-latest" in available_models:
            model_name = "models/gemini-flash-latest"  # Auto-updating flash
        elif "models/gemini-2.0-flash" in available_models:
            model_name = "models/gemini-2.0-flash"  # Stable flash
        elif "models/gemini-2.0-flash-lite" in available_models:
            model_name = "models/gemini-2.0-flash-lite"  # Lite version (cheaper)
        elif "models/gemini-2.5-pro" in available_models:
            model_name = "models/gemini-2.5-pro"  # Pro version (more powerful)
        else:
            # Fallback to any available Gemini model (excluding preview)
            gemini_models = [m for m in available_models if "gemini" in m and "preview" not in m]
            model_name = gemini_models[0] if gemini_models else "models/gemini-2.5-flash"
        
        print(f"Selected model: {model_name}")
    
    except Exception as e:
        print(f"Could not list models: {e}")
        model_name = "models/gemini-2.5-flash"  # Safe fallback
    
    safety_settings = [
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
            threshold=types.HarmBlockThreshold.BLOCK_NONE,
        ),
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
            threshold=types.HarmBlockThreshold.BLOCK_NONE,
        ),
    ]
else:
    client = None
    model_name = None


def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _normalize_parsed(raw: dict) -> dict:
    """Fill defaults and normalize flags from model output."""
    out = dict(raw)
    for key in (
        "task",
        "date",
        "time",
        "clarification_question",
        "editable_reminder_id",
    ):
        if out.get(key) == "":
            out[key] = None
    if out.get("time"):
        t = str(out["time"]).strip()
        if len(t) == 5 and t[2] == ":":
            out["time"] = t
        elif len(t) >= 8 and t[2] == ":":
            out["time"] = t[:5]
    if not out.get("date") and out.get("task") and not out.get("needs_clarification"):
        out["date"] = _today_utc()
    has_time = bool(out.get("time"))
    if not has_time:
        out["needs_time"] = True
    elif out.get("needs_time") is True:
        out["needs_time"] = True
    else:
        out["needs_time"] = False
    return out


def clean_json_response(content: str) -> str:
    content = content.strip()
    if content.startswith("```json"):
        content = content.replace("```json", "").replace("```", "").strip()
    elif content.startswith("```"):
        content = content.replace("```", "").strip()
    return content


def extract_json_from_text(text: str) -> dict:
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except Exception:
        pass
    return {}


def get_mock_reminder(
    message: str,
    pending_context: Optional[dict] = None,
) -> dict:
    """Offline fallback with simple relative-time and draft-merge heuristics."""
    text = message.lower().strip()
    base = dict(pending_context) if pending_context else {}
    task = base.get("task")
    date = base.get("date") or _today_utc()
    time_str = base.get("time")
    repeat = base.get("repeat")
    intent = "create"

    if pending_context:
        intent = "refine_draft"
        m = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", text, re.I)
        if m:
            h = int(m.group(1))
            minute = int(m.group(2) or 0)
            mer = (m.group(3) or "").lower()
            if mer == "pm" and h != 12:
                h += 12
            if mer == "am" and h == 12:
                h = 0
            time_str = f"{h:02d}:{minute:02d}"
        elif re.search(r"\b(noon|midnight)\b", text):
            time_str = "12:00" if "noon" in text else "00:00"
            if "midnight" in text:
                pass

    if not task:
        task = (
            re.sub(
                r"^remind me to\s+",
                "",
                text,
                flags=re.I,
            ).strip()
            or f"Task from: {message[:40]}"
        )

    if "tomorrow" in text:
        d = datetime.now(timezone.utc).date() + timedelta(days=1)
        date = d.isoformat()
    if "next monday" in text:
        d = datetime.now(timezone.utc).date()
        days_ahead = (7 - d.weekday()) % 7 or 7
        date = (d + timedelta(days=days_ahead)).isoformat()
    if re.search(r"in\s+(\d+)\s+hours?", text):
        n = int(re.search(r"in\s+(\d+)\s+hours?", text).group(1))
        dt = datetime.now(timezone.utc) + timedelta(hours=n)
        date = dt.strftime("%Y-%m-%d")
        time_str = dt.strftime("%H:%M")

    if not time_str:
        hm = re.search(r"\b(\d{1,2}):(\d{2})\b", message)
        if hm:
            time_str = f"{int(hm.group(1)):02d}:{hm.group(2)}"

    needs_time = time_str is None or time_str == ""
    needs_clarification = not task or len(task) < 2
    clarification_question = None
    if needs_clarification:
        clarification_question = "What would you like to be reminded about?"
    elif needs_time:
        clarification_question = None

    return _normalize_parsed(
        {
            "intent": intent,
            "task": task,
            "date": date,
            "time": time_str,
            "repeat": repeat,
            "needs_time": needs_time,
            "needs_clarification": needs_clarification,
            "clarification_question": clarification_question,
            "editable_reminder_id": None,
        }
    )


async def extract_reminder_details(
    message: str,
    pending_context: Optional[dict] = None,
    recent_reminders: Optional[list] = None,
) -> Optional[dict]:
    """
    Extract structured reminder data. Returns dict with:
    intent, task, date, time, repeat, needs_time, needs_clarification,
    clarification_question, editable_reminder_id (optional).
    """
    if not client or not api_key:
        logger.warning("Gemini client not initialized. Using mock extractor.")
        return get_mock_reminder(message, pending_context)

    now = datetime.now()
    ctx_json = (
        json.dumps(pending_context, ensure_ascii=False) if pending_context else "null"
    )
    recent_json = (
        json.dumps(recent_reminders, ensure_ascii=False) if recent_reminders else "[]"
    )

    system_prompt = f"""
You extract reminder data from chat. Current local server datetime (context only): {now.strftime('%Y-%m-%d %H:%M:%S')}.
Use this to resolve "today", "tomorrow", "next Monday", "in 2 hours", etc. Dates must be YYYY-MM-DD. Times must be HH:MM 24-hour.

Pending draft from the previous turn (merge/refine if the user is answering or correcting): {ctx_json}

User's existing reminders (id + task + datetime ISO) — use only to match phrases like "change my call Ali reminder" or "the gym one": {recent_json}

Return ONE JSON object only (no markdown):
{{
  "intent": "create" | "refine_draft" | "edit_saved",
  "task": string or null,
  "date": "YYYY-MM-DD" or null,
  "time": "HH:MM" or null,
  "repeat": string or null,
  "needs_time": boolean,
  "needs_clarification": boolean,
  "clarification_question": string or null,
  "editable_reminder_id": string UUID or null
}}

Rules:
- If the user only gives a time correction ("make it 12", "9pm instead") and pending draft exists, set intent to "refine_draft" and merge into task/date/time/repeat from the draft, applying the change.
- If no date is mentioned, default date to today ({_today_utc()}) and set needs_time false only when time is present.
- If the user states a task but NO time (e.g. "remind me to call Ali"), set needs_time true, needs_clarification false, time null.
- If ambiguous (e.g. "3" could be AM/PM), set needs_clarification true and ask one short question in clarification_question.
- If you cannot determine the task at all, needs_clarification true and clarification_question helpful.
- For edit_saved: if the user clearly refers to one of the listed reminders, set intent "edit_saved", editable_reminder_id to that id, and new task/date/time/repeat as appropriate.
- Otherwise intent "create" for a new reminder.

IMPORTANT: Raw JSON only, no code fences.
"""

    try:
        full_prompt = f"{system_prompt}\n\nUser message: {message}"
        response = await client.aio.models.generate_content(
            model=model_name,
            contents=full_prompt,
            config=types.GenerateContentConfig(
                temperature=0,
                safety_settings=(
                    safety_settings if "safety_settings" in locals() else None
                ),
            ),
        )
        if not response or not response.text:
            logger.warning("Empty response from Gemini")
            return None

        reply_content = clean_json_response(response.text)
        try:
            parsed = json.loads(reply_content)
        except json.JSONDecodeError:
            parsed = extract_json_from_text(reply_content)

        if not parsed or "task" not in parsed:
            return None

        return _normalize_parsed(parsed)
    except Exception as e:
        logger.error(f"Error during AI extraction with Gemini: {e}")
        return None


async def test_gemini():
    test_messages = [
        "Remind me to buy milk tomorrow at 3pm",
        "Call mom every Monday at 9am",
        "Team meeting in 2 hours",
        "Pay rent on the 1st of each month at 10am",
    ]
    for msg in test_messages:
        result = await extract_reminder_details(msg)
        print(f"Input: {msg}")
        print(f"Output: {result}\n")
