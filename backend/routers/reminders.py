import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from deps import get_current_user
import models
import schemas

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("", response_model=schemas.ReminderResponse)
def create_reminder(
    reminder: schemas.ReminderCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    db_reminder = models.Reminder(
        task=reminder.task,
        datetime=reminder.datetime,
        repeat=reminder.repeat,
        user_id=current_user.id,
        status=models.ReminderStatus.PENDING.value,
    )
    db.add(db_reminder)
    db.commit()
    db.refresh(db_reminder)
    logger.info(
        "event=reminder_created user_id=%s reminder_id=%s scheduled_at=%s repeat=%s",
        current_user.id,
        db_reminder.id,
        db_reminder.datetime,
        db_reminder.repeat,
    )
    return db_reminder


@router.get("", response_model=list[schemas.ReminderResponse])
def get_reminders(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return (
        db.query(models.Reminder)
        .filter(models.Reminder.user_id == current_user.id)
        .all()
    )


def _reminder_for_user(
    db: Session, reminder_id: UUID, user_id: UUID
) -> Optional[models.Reminder]:
    return (
        db.query(models.Reminder)
        .filter(
            models.Reminder.id == reminder_id,
            models.Reminder.user_id == user_id,
        )
        .first()
    )


@router.delete("/{reminder_id}")
def delete_reminder(
    reminder_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    db_reminder = _reminder_for_user(db, reminder_id, current_user.id)
    if not db_reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")

    db.query(models.DeliveryAttempt).filter(
        models.DeliveryAttempt.reminder_id == reminder_id
    ).delete(synchronize_session=False)
    db.delete(db_reminder)
    db.commit()
    logger.info("event=reminder_deleted user_id=%s reminder_id=%s", current_user.id, reminder_id)
    return {"message": "Reminder deleted successfully"}


@router.patch("/{reminder_id}", response_model=schemas.ReminderResponse)
def update_reminder(
    reminder_id: UUID,
    body: schemas.ReminderUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    db_reminder = _reminder_for_user(db, reminder_id, current_user.id)
    if not db_reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    if body.task is not None:
        db_reminder.task = body.task
    if body.datetime is not None:
        db_reminder.datetime = body.datetime
    if body.repeat is not None:
        db_reminder.repeat = body.repeat
    db.commit()
    db.refresh(db_reminder)
    logger.info(
        "event=reminder_updated user_id=%s reminder_id=%s scheduled_at=%s repeat=%s",
        current_user.id,
        db_reminder.id,
        db_reminder.datetime,
        db_reminder.repeat,
    )
    return db_reminder


@router.patch("/{reminder_id}/complete", response_model=schemas.ReminderResponse)
def complete_reminder(
    reminder_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    db_reminder = _reminder_for_user(db, reminder_id, current_user.id)
    if not db_reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")

    db_reminder.status = models.ReminderStatus.COMPLETED.value
    db_reminder.processing_started_at = None
    db_reminder.next_attempt_at = None
    db_reminder.last_error = None
    db.commit()
    db.refresh(db_reminder)
    logger.info(
        "event=reminder_completed user_id=%s reminder_id=%s",
        current_user.id,
        reminder_id,
    )
    return db_reminder


def _clear_delivery_history(db: Session, reminder_id: UUID) -> int:
    deleted = (
        db.query(models.DeliveryAttempt)
        .filter(models.DeliveryAttempt.reminder_id == reminder_id)
        .delete(synchronize_session=False)
    )
    return deleted


@router.post("/{reminder_id}/snooze", response_model=schemas.ReminderResponse)
def snooze_reminder(
    reminder_id: UUID,
    body: schemas.ReminderSnooze,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    db_reminder = _reminder_for_user(db, reminder_id, current_user.id)
    if not db_reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")

    now = datetime.now(timezone.utc)
    previous_status = db_reminder.status
    previous_datetime = db_reminder.datetime
    new_datetime = now + timedelta(minutes=body.minutes)

    cleared = _clear_delivery_history(db, reminder_id)
    db_reminder.datetime = new_datetime
    db_reminder.status = models.ReminderStatus.PENDING.value
    db_reminder.triggered_at = None
    db_reminder.processing_started_at = None
    db_reminder.next_attempt_at = None
    db_reminder.attempt_count = 0
    db_reminder.last_error = None
    db.commit()
    db.refresh(db_reminder)

    logger.info(
        "Snooze reminder_id=%s user_id=%s minutes=%s previous_status=%s "
        "previous_datetime=%s new_datetime=%s cleared_delivery_attempts=%s",
        reminder_id,
        current_user.id,
        body.minutes,
        previous_status,
        previous_datetime,
        new_datetime,
        cleared,
    )
    return db_reminder
