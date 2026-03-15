from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.orm import Session
from database import SessionLocal
import models
import logging

logger = logging.getLogger(__name__)

async def check_due_reminders():
    """
    Background job to check for reminders where current time >= reminder time 
    and status is PENDING.
    """
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc).replace(tzinfo=None) # Handling naive comparison
        due_reminders = db.query(models.Reminder).filter(
            models.Reminder.datetime <= now,
            models.Reminder.status == models.ReminderStatus.PENDING.value
        ).all()

        for reminder in due_reminders:
            logger.info(f"TRIGGERING NOTIFICATION: {reminder.task} for user {reminder.user_id}")
            
            # --- PUSH NOTIFICATION LOGIC ---
            # In a real app, we would call Firebase Cloud Messaging here.
            # Example: fcm_service.send_push(reminder.user_id, "Reminder", reminder.task)
            
            # Mark as COMPLETED for MVP purposes (or TRIGGERED)
            reminder.status = models.ReminderStatus.COMPLETED.value
            db.commit()
            
    except Exception as e:
        logger.error(f"Error in scheduler job: {e}")
    finally:
        db.close()

def start_scheduler():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_due_reminders, 'interval', minutes=1)
    scheduler.start()
    logger.info("Scheduler started successfully.")
    return scheduler
