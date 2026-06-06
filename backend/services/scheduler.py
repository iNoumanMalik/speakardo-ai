from datetime import datetime, timedelta, timezone
import os
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import or_
from sqlalchemy.orm import Session

from database import SessionLocal
import models
import logging
from services.notifications import send_push_notification
from services.local_schedule import (
    delivery_dedupe_key_local,
    is_reminder_due,
    is_snooze_due,
    local_now,
)
from services.reminder_state import reset_for_reschedule
from services.repeat_schedule import normalize_repeat

logger = logging.getLogger(__name__)

SCHEDULER_INTERVAL_SECONDS = int(os.getenv("SCHEDULER_INTERVAL_SECONDS", "30"))
MAX_DELIVERY_ATTEMPTS = int(os.getenv("MAX_DELIVERY_ATTEMPTS", "5"))
PROCESSING_TIMEOUT_SECONDS = int(os.getenv("PROCESSING_TIMEOUT_SECONDS", "120"))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def delivery_dedupe_key(reminder_id, device_id, scheduled_at: datetime) -> str:
    """One delivery per device per scheduled fire time (snooze changes scheduled_at)."""
    if scheduled_at.tzinfo is None:
        scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)
    else:
        scheduled_at = scheduled_at.astimezone(timezone.utc)
    slot = int(scheduled_at.timestamp())
    return f"{reminder_id}:{device_id}:{slot}"


def _next_retry_at(now: datetime, attempt_count: int) -> datetime:
    minutes = min(16, 2 ** max(0, attempt_count - 1))
    return now + timedelta(minutes=minutes)


def _recover_stale_processing(db: Session, now: datetime) -> int:
    stale_before = now - timedelta(seconds=PROCESSING_TIMEOUT_SECONDS)
    stale_rows = (
        db.query(models.Reminder)
        .filter(
            models.Reminder.status == models.ReminderStatus.PROCESSING.value,
            or_(
                models.Reminder.processing_started_at.is_(None),
                models.Reminder.processing_started_at <= stale_before,
            ),
        )
        .all()
    )
    if not stale_rows:
        return 0

    for reminder in stale_rows:
        logger.warning(
            "Recovering stale processing reminder_id=%s processing_started_at=%s last_error=%s",
            reminder.id,
            reminder.processing_started_at,
            reminder.last_error,
        )
        reminder.status = models.ReminderStatus.PENDING.value
        reminder.processing_started_at = None
        if not reminder.last_error:
            reminder.last_error = "processing_timeout_recovered"
        # Defer slightly so recovery does not immediately re-fire in the same tick.
        reminder.next_attempt_at = now + timedelta(seconds=SCHEDULER_INTERVAL_SECONDS)

    db.commit()
    logger.info("Recovered %d stale processing reminder(s)", len(stale_rows))
    return len(stale_rows)


def _claim_due_reminder(db: Session, reminder_id, now: datetime) -> bool:
    updated = (
        db.query(models.Reminder)
        .filter(
            models.Reminder.id == reminder_id,
            models.Reminder.status == models.ReminderStatus.PENDING.value,
            or_(
                models.Reminder.next_attempt_at.is_(None),
                models.Reminder.next_attempt_at <= now,
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
    return bool(updated)


def _release_processing_to_pending(
    db: Session,
    reminder: models.Reminder,
    now: datetime,
    error: str,
    *,
    increment_attempt: bool = True,
) -> None:
    if increment_attempt:
        reminder.attempt_count = (reminder.attempt_count or 0) + 1
    reminder.processing_started_at = None
    reminder.last_error = error
    if reminder.attempt_count >= MAX_DELIVERY_ATTEMPTS:
        reminder.status = models.ReminderStatus.FAILED.value
        reminder.next_attempt_at = None
        logger.error(
            "Reminder_id=%s marked failed after %s attempts (%s)",
            reminder.id,
            reminder.attempt_count,
            error,
        )
    else:
        reminder.status = models.ReminderStatus.PENDING.value
        reminder.next_attempt_at = _next_retry_at(now, reminder.attempt_count)
        logger.info(
            "Reminder_id=%s scheduled retry at %s (%s)",
            reminder.id,
            reminder.next_attempt_at,
            error,
        )


def _mark_triggered(
    db: Session,
    reminder: models.Reminder,
    now: datetime,
    *,
    user_timezone: Optional[str] = None,
) -> None:
    if normalize_repeat(reminder.repeat):
        reset_for_reschedule(db, reminder)
        reminder.snoozed_until = None
        reminder.datetime = now
        logger.info(
            "event=repeat_local_fired reminder_id=%s local_time=%s user_tz=%s",
            reminder.id,
            reminder.local_time,
            user_timezone,
        )
        return

    reminder.status = models.ReminderStatus.TRIGGERED.value
    reminder.triggered_at = now
    reminder.next_attempt_at = None
    reminder.processing_started_at = None
    reminder.last_error = None
    logger.info(
        "Reminder_id=%s triggered at %s scheduled_datetime=%s",
        reminder.id,
        now,
        reminder.datetime,
    )


def _dedupe_key_for_fire(
    reminder: models.Reminder,
    device_id,
    now: datetime,
    user_timezone: Optional[str],
) -> str:
    if normalize_repeat(reminder.repeat):
        if is_snooze_due(reminder.snoozed_until, now) and reminder.snoozed_until:
            return delivery_dedupe_key(
                reminder.id, device_id, reminder.snoozed_until
            )
        local = local_now(now, user_timezone)
        return delivery_dedupe_key_local(
            reminder.id,
            device_id,
            local.date().isoformat(),
            reminder.local_time or "00:00",
        )
    scheduled_at = reminder.datetime
    if scheduled_at.tzinfo is None:
        scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)
    else:
        scheduled_at = scheduled_at.astimezone(timezone.utc)
    return delivery_dedupe_key(reminder.id, device_id, scheduled_at)


def _process_reminder(
    db: Session,
    reminder: models.Reminder,
    now: datetime,
    *,
    user_timezone: Optional[str] = None,
) -> None:
    is_repeating = bool(normalize_repeat(reminder.repeat))
    if not is_repeating:
        scheduled_at = reminder.datetime
        if scheduled_at.tzinfo is None:
            scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)
        else:
            scheduled_at = scheduled_at.astimezone(timezone.utc)
        if scheduled_at > now:
            logger.warning(
                "Reminder_id=%s not yet due (scheduled_at=%s now=%s) — releasing claim",
                reminder.id,
                scheduled_at,
                now,
            )
            reminder.status = models.ReminderStatus.PENDING.value
            reminder.processing_started_at = None
            return

    user = db.query(models.User).filter(models.User.id == reminder.user_id).first()
    tz = user_timezone or (user.timezone if user else "UTC")

    if user and not user.notifications_enabled:
        logger.info(
            "Reminder_id=%s notifications disabled for user_id=%s — marking triggered",
            reminder.id,
            reminder.user_id,
        )
        _mark_triggered(db, reminder, now, user_timezone=tz)
        return

    device_tokens = (
        db.query(models.DeviceToken)
        .filter(models.DeviceToken.user_id == reminder.user_id)
        .order_by(models.DeviceToken.created_at.asc())
        .all()
    )

    if not device_tokens:
        logger.info(
            "Reminder_id=%s no devices for user_id=%s",
            reminder.id,
            reminder.user_id,
        )
        db_state = (
            db.query(models.Reminder.status)
            .filter(models.Reminder.id == reminder.id)
            .scalar()
        )
        if db_state != models.ReminderStatus.PROCESSING.value:
            logger.warning(
                "Reminder_id=%s was modified externally (status=%s) before releasing. "
                "Skipping status release to protect user action.",
                reminder.id,
                db_state,
            )
            return
        _release_processing_to_pending(db, reminder, now, "no_devices")
        return

    delivered = False
    last_error = None
    sends_attempted = 0

    for device in device_tokens:
        dedupe_key = _dedupe_key_for_fire(reminder, device.id, now, tz)
        existing = (
            db.query(models.DeliveryAttempt)
            .filter(models.DeliveryAttempt.dedupe_key == dedupe_key)
            .first()
        )
        if existing is not None:
            logger.info(
                "Reminder_id=%s skipping already-delivered dedupe_key=%s status=%s",
                reminder.id,
                dedupe_key,
                existing.status,
            )
            if existing.status == models.DeliveryStatus.SUCCESS.value:
                delivered = True
            continue

        sends_attempted += 1
        logger.info(
            "Reminder_id=%s sending push dedupe_key=%s device_token_id=%s local_time=%s user_tz=%s",
            reminder.id,
            dedupe_key,
            device.id,
            reminder.local_time,
            tz,
        )
        result = send_push_notification(
            device_token=device.token,
            user_id=str(reminder.user_id),
            task=reminder.task,
            reminder_id=str(reminder.id),
        )
        delivered = delivered or result.success
        if not result.success:
            last_error = result.error_message or result.error_code
            logger.warning(
                "Reminder_id=%s push failed device_token_id=%s error=%s",
                reminder.id,
                device.id,
                last_error,
            )

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

    db_state = (
        db.query(models.Reminder.status, models.Reminder.processing_started_at)
        .filter(models.Reminder.id == reminder.id)
        .first()
    )
    if not db_state or db_state[0] != models.ReminderStatus.PROCESSING.value or db_state[1] != reminder.processing_started_at:
        logger.warning(
            "Reminder_id=%s was modified externally (status=%s, started_at=%s) during push delivery. "
            "Skipping state update to protect user action.",
            reminder.id,
            db_state[0] if db_state else None,
            db_state[1] if db_state else None,
        )
        return

    reminder.attempt_count = (reminder.attempt_count or 0) + 1

    if delivered:
        _mark_triggered(db, reminder, now, user_timezone=tz)
        return

    if sends_attempted == 0 and device_tokens:
        logger.warning(
            "Reminder_id=%s no sends — treating as delivery failure",
            reminder.id,
        )

    _release_processing_to_pending(
        db,
        reminder,
        now,
        last_error or "delivery_failed",
        increment_attempt=False,
    )


async def check_due_reminders():
    db = SessionLocal()
    try:
        now = _utcnow()
        recovered = _recover_stale_processing(db, now)
        if recovered:
            logger.info("Stale processing recovery complete count=%s", recovered)

        pending_reminders = (
            db.query(models.Reminder)
            .filter(
                models.Reminder.status == models.ReminderStatus.PENDING.value,
                or_(
                    models.Reminder.next_attempt_at.is_(None),
                    models.Reminder.next_attempt_at <= now,
                ),
            )
            .all()
        )

        user_tz_cache: dict = {}
        due_reminders = []
        for reminder in pending_reminders:
            uid = reminder.user_id
            if uid not in user_tz_cache:
                user = db.query(models.User.timezone).filter(models.User.id == uid).first()
                user_tz_cache[uid] = user[0] if user else "UTC"
            user_tz = user_tz_cache[uid]
            if is_reminder_due(
                repeat=reminder.repeat,
                datetime_utc=reminder.datetime,
                local_time=reminder.local_time,
                local_weekday=reminder.local_weekday,
                local_day_of_month=reminder.local_day_of_month,
                snoozed_until=reminder.snoozed_until,
                user_tz=user_tz,
                now_utc=now,
            ):
                due_reminders.append((reminder, user_tz))

        logger.debug(
            "Scheduler tick at %s found %d due reminder(s) of %d pending",
            now,
            len(due_reminders),
            len(pending_reminders),
        )

        for reminder, user_tz in due_reminders:
            reminder_id = reminder.id
            try:
                logger.info(
                    "Scheduler considering reminder_id=%s scheduled_at=%s status=%s next_attempt_at=%s",
                    reminder.id,
                    reminder.datetime,
                    reminder.status,
                    reminder.next_attempt_at,
                )
                if not _claim_due_reminder(db, reminder_id, now):
                    continue

                # Immediate commit to ensure other workers / ticks cannot process this claimed reminder.
                db.commit()
                db.refresh(reminder)
                logger.info(
                    "Processing start reminder_id=%s scheduled_at=%s processing_started_at=%s",
                    reminder.id,
                    reminder.datetime,
                    reminder.processing_started_at,
                )

                _process_reminder(db, reminder, now, user_timezone=user_tz)
                db.commit()
                logger.info(
                    "Processing finished reminder_id=%s final_status=%s triggered_at=%s",
                    reminder.id,
                    reminder.status,
                    reminder.triggered_at,
                )
            except Exception:
                logger.exception(
                    "Processing failed reminder_id=%s — rolling back and recovering",
                    reminder_id,
                )
                db.rollback()
                try:
                    stuck = (
                        db.query(models.Reminder)
                        .filter(models.Reminder.id == reminder_id)
                        .first()
                    )
                    if (
                        stuck
                        and stuck.status == models.ReminderStatus.PROCESSING.value
                    ):
                        _release_processing_to_pending(
                            db,
                            stuck,
                            now,
                            "processing_exception_recovered",
                        )
                        db.commit()
                        logger.info(
                            "Reminder_id=%s released to pending after exception",
                            reminder_id,
                        )
                except Exception:
                    logger.exception(
                        "Failed to recover reminder_id=%s after processing error",
                        reminder_id,
                    )
                    db.rollback()

    except Exception:
        logger.exception("Scheduler job failed")
        db.rollback()
    finally:
        db.close()


def start_scheduler():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        check_due_reminders,
        "interval",
        seconds=SCHEDULER_INTERVAL_SECONDS,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logger.info(
        "Scheduler started interval=%ss processing_timeout=%ss max_attempts=%s",
        SCHEDULER_INTERVAL_SECONDS,
        PROCESSING_TIMEOUT_SECONDS,
        MAX_DELIVERY_ATTEMPTS,
    )
    return scheduler
