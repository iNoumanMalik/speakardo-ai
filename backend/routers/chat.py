from fastapi import APIRouter
import schemas
import sys
import os

# Ensure ai_service is in the path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from ai_service.extractor import extract_reminder_details

router = APIRouter()

@router.post("", response_model=schemas.ChatResponse)
async def process_chat(request: schemas.ChatRequest):
    # Pass user message to AI service for extraction
    parsed_data = await extract_reminder_details(request.message)
    
    if parsed_data:
        # Ask for confirmation
        time_str = parsed_data.get('time', parsed_data.get('datetime', 'the requested time'))
        reply = f"Should I remind you to {parsed_data.get('task', 'do your task')} at {time_str}?"
        return schemas.ChatResponse(reply=reply, parsed_reminder=parsed_data)
    else:
        # Fallback if AI couldn't parse
        reply = "I couldn't quite understand the reminder details. Please try rephrasing."
        return schemas.ChatResponse(reply=reply, parsed_reminder=None)
