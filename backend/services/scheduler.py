from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from database import SessionLocal
import models
import logging
from services.notifications import send_push_notification

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
            sent = send_push_notification(
                user_id=str(reminder.user_id) if reminder.user_id else None,
                task=reminder.task,
                reminder_id=str(reminder.id),
            )
            if sent:
                # Keep reminder visible in list as triggered until user completes it.
                reminder.status = models.ReminderStatus.TRIGGERED.value
                db.commit()
            
    except Exception as e:
        logger.error(f"Error in scheduler job: {e}")
    finally:
        db.close()

def start_scheduler():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_due_reminders, "interval", seconds=30)
    scheduler.start()
    logger.info("Scheduler started successfully.")
    return scheduler
