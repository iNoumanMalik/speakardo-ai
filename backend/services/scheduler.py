from datetime import datetime, timezone
import os
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from database import SessionLocal
import models
import logging
from services.notifications import send_push_notification

logger = logging.getLogger(__name__)

SCHEDULER_INTERVAL_SECONDS = int(os.getenv("SCHEDULER_INTERVAL_SECONDS", "30"))
MAX_DELIVERY_ATTEMPTS = int(os.getenv("MAX_DELIVERY_ATTEMPTS", "5"))
PROCESSING_TIMEOUT_SECONDS = int(os.getenv("PROCESSING_TIMEOUT_SECONDS", "120"))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _next_retry_at(now: datetime, attempt_count: int) -> datetime:
    # Exponential-ish backoff: 1m, 2m, 4m, 8m, 16m...
    minutes = min(16, 2 ** max(0, attempt_count - 1))
    from datetime import timedelta
    return now + timedelta(minutes=minutes)


def _claim_due_reminder(db, reminder: models.Reminder, now: datetime) -> bool:
    from datetime import timedelta
    stale_before = now - timedelta(seconds=PROCESSING_TIMEOUT_SECONDS)
    updated = (
        db.query(models.Reminder)
        .filter(
            models.Reminder.id == reminder.id,
            models.Reminder.datetime <= now,
            models.Reminder.status.in_(
                [models.ReminderStatus.PENDING.value, models.ReminderStatus.PROCESSING.value]
            ),
            (
                (models.Reminder.status == models.ReminderStatus.PENDING.value)
                | (models.Reminder.processing_started_at <= stale_before)
            ),
            (
                (models.Reminder.next_attempt_at.is_(None))
                | (models.Reminder.next_attempt_at <= now)
            ),
        )
        .update(
            {
                "status": models.ReminderStatus.PROCESSING.value,
                "processing_started_at": now,
            },
            synchronize_session=False,
        )
    )
    if updated:
        db.commit()
    return bool(updated)


async def check_due_reminders():
    """
    Background job to check for reminders where current time >= reminder time 
    and status is PENDING.
    """
    db = SessionLocal()
    try:
        now = _utcnow()
        due_reminders = (
            db.query(models.Reminder)
            .filter(
                models.Reminder.datetime <= now,
                models.Reminder.status.in_(
                    [models.ReminderStatus.PENDING.value, models.ReminderStatus.PROCESSING.value]
                ),
                (models.Reminder.next_attempt_at.is_(None))
                | (models.Reminder.next_attempt_at <= now),
            )
            .all()
        )

        for reminder in due_reminders:
            if not _claim_due_reminder(db, reminder, now):
                continue

            db.refresh(reminder)
            user = (
                db.query(models.User)
                .filter(models.User.id == reminder.user_id)
                .first()
            )
            if user and not user.notifications_enabled:
                reminder.status = models.ReminderStatus.TRIGGERED.value
                reminder.triggered_at = now
                reminder.next_attempt_at = None
                reminder.processing_started_at = None
                reminder.last_error = None
                db.commit()
                continue

            devices_query = db.query(models.DeviceToken).filter(
                models.DeviceToken.user_id == reminder.user_id
            )
            device_tokens = devices_query.order_by(models.DeviceToken.created_at.asc()).all()

            if not device_tokens:
                logger.info(
                    "No registered devices found for reminder_id=%s user_id=%s",
                    reminder.id,
                    reminder.user_id,
                )
                reminder.attempt_count = (reminder.attempt_count or 0) + 1
                reminder.last_error = "no_devices"
                reminder.processing_started_at = None
                if reminder.attempt_count >= MAX_DELIVERY_ATTEMPTS:
                    reminder.status = models.ReminderStatus.FAILED.value
                    reminder.next_attempt_at = None
                else:
                    reminder.status = models.ReminderStatus.PENDING.value
                    reminder.next_attempt_at = _next_retry_at(now, reminder.attempt_count)
                db.commit()
                continue

            delivered = False
            last_error = None
            for device in device_tokens:
                attempt_no = (reminder.attempt_count or 0) + 1
                dedupe_key = f"{reminder.id}:{device.id}:{attempt_no}"
                if (
                    db.query(models.DeliveryAttempt)
                    .filter(models.DeliveryAttempt.dedupe_key == dedupe_key)
                    .first()
                    is not None
                ):
                    continue

                result = send_push_notification(
                    device_token=device.token,
                    user_id=str(reminder.user_id),
                    task=reminder.task,
                    reminder_id=str(reminder.id),
                )
                delivered = delivered or result.success
                if not result.success:
                    last_error = result.error_message or result.error_code

                attempt = models.DeliveryAttempt(
                    reminder_id=reminder.id,
                    device_token_id=device.id,
                    dedupe_key=dedupe_key,
                    status=(
                        models.DeliveryStatus.SUCCESS.value
                        if result.success
                        else (
                            models.DeliveryStatus.PERM_FAILURE.value
                            if result.permanent_failure
                            else models.DeliveryStatus.TEMP_FAILURE.value
                        )
                    ),
                    provider_message_id=result.provider_message_id,
                    error_code=result.error_code,
                    error_message=result.error_message,
                )
                db.add(attempt)

                if result.invalid_token:
                    db.delete(device)

            reminder.attempt_count = (reminder.attempt_count or 0) + 1
            if delivered:
                # Keep reminder visible in list as triggered until user completes it.
                reminder.status = models.ReminderStatus.TRIGGERED.value
                reminder.triggered_at = now
                reminder.next_attempt_at = None
                reminder.processing_started_at = None
                reminder.last_error = None
            else:
                reminder.processing_started_at = None
                reminder.last_error = last_error or "delivery_failed"
                if reminder.attempt_count >= MAX_DELIVERY_ATTEMPTS:
                    reminder.status = models.ReminderStatus.FAILED.value
                    reminder.next_attempt_at = None
                else:
                    reminder.status = models.ReminderStatus.PENDING.value
                    reminder.next_attempt_at = _next_retry_at(now, reminder.attempt_count)
            db.commit()
            
    except Exception as e:
        logger.error(f"Error in scheduler job: {e}")
        db.rollback()
    finally:
        db.close()

def start_scheduler():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_due_reminders, "interval", seconds=SCHEDULER_INTERVAL_SECONDS)
    scheduler.start()
    logger.info("Scheduler started successfully.")
    return scheduler
