import os
import json
import logging
import asyncio
from dotenv import load_dotenv
from datetime import datetime
from typing import Optional


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


    model_name = "gemini-flash-latest"
else:
    client = None
    model_name = None


async def extract_reminder_details(message: str) -> Optional[dict]:
    """
    Passes the natural language message to Google Gemini to extract reminder info.
    Returns a dictionary matching the Reminder structure, or None if it fails.
    """
    if not client or not api_key:
        logger.warning("Gemini client not initialized. Returning mock data.")
        return get_mock_reminder(message)

    system_prompt = f"""
    You are an AI assistant that extracts reminder details from a user's chat message.
    Today's current date and time context is {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.
    
    Extract the following fields from the user's message and return them as valid JSON:
    - task (string): The description of the task without time details.
    - date (string): Extracted date in YYYY-MM-DD format.
    - time (string): Extracted time in HH:MM format (24-hour).
    - repeat (string or null): Recurrence pattern (e.g., "daily", "weekly", "monthly") or null.
    
    Examples:
    Input: "Remind me to buy milk tomorrow at 3pm"
    Output: {{"task": "buy milk", "date": "2026-03-17", "time": "15:00", "repeat": null}}
    
    Input: "Call mom every Monday at 9am"
    Output: {{"task": "call mom", "date": "2026-03-23", "time": "09:00", "repeat": "weekly"}}
    
    If you cannot safely determine the task and time, return an empty JSON object {{}}.
    
    IMPORTANT: Return ONLY the raw JSON without any markdown formatting, code blocks, or explanations.
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

        reply_content = response.text
        logger.debug(f"Gemini response: {reply_content}")


        reply_content = clean_json_response(reply_content)

        try:
            parsed = json.loads(reply_content)
        except json.JSONDecodeError:
            parsed = extract_json_from_text(reply_content)

        if not parsed or "task" not in parsed:
            logger.warning(f"No task field in parsed response: {parsed}")
            return None

        return parsed

    except Exception as e:
        logger.error(f"Error during AI extraction with Gemini: {e}")
        return None


def clean_json_response(content: str) -> str:
    """Remove markdown formatting from JSON response."""
    content = content.strip()


    if content.startswith("```json"):
        content = content.replace("```json", "").replace("```", "").strip()
    elif content.startswith("```"):
        content = content.replace("```", "").strip()

    return content


def extract_json_from_text(text: str) -> dict:
    """Extract JSON object from text that might contain additional content."""
    try:

        start = text.find("{")
        end = text.rfind("}") + 1

        if start >= 0 and end > start:
            json_str = text[start:end]
            return json.loads(json_str)
    except:
        pass

    return {}


def get_mock_reminder(message: str) -> dict:
    """Return mock reminder data for testing."""
    return {
        "task": f"Mock Task: {message[:30]}...",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "time": "12:00",
        "repeat": None,
    }



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
