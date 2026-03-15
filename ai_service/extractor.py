import os
import json
import logging
from datetime import datetime

try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None

logger = logging.getLogger(__name__)
api_key = os.getenv("OPENAI_API_KEY")
client = AsyncOpenAI(api_key=api_key) if AsyncOpenAI and api_key else None

async def extract_reminder_details(message: str) -> dict:
    """
    Passes the natural language message to an LLM to extract reminder info.
    Returns a dictionary matching the Reminder structure, or None if it fails.
    """
    if not client:
        logger.warning("OpenAI client not initialized. Returning mock data.")
        return {
            "task": "Mock Task (from: " + message[:10] + "...)",
            "date": "2026-03-15",
            "time": "12:00",
            "repeat": None
        }

    system_prompt = f"""
    You are an AI assistant that extracts reminder details from a user's chat message.
    Today's current date and time context is {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.
    
    Extract the following fields from the user's message and return them as valid JSON:
    - task (string): The description of the task without time details.
    - date (string): Extracted date in YYYY-MM-DD format.
    - time (string): Extracted time in HH:MM format (24-hour).
    - repeat (string or null): Recurrence pattern (e.g., "daily", "weekly") or null.
    
    If you cannot safely determine the task and time, return an empty JSON object {{}}.
    Do not output any markdown formatting, just the raw JSON.
    """

    try:
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ],
            temperature=0,
            response_format={ "type": "json_object" }
        )
        
        reply_content = response.choices[0].message.content
        parsed = json.loads(reply_content)
        
        if not parsed or 'task' not in parsed:
            return None
            
        return parsed
    except Exception as e:
        logger.error(f"Error during AI extraction: {{e}}")
        return None
