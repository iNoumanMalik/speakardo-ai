from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import models
import schemas
from uuid import UUID

router = APIRouter()

@router.post("", response_model=schemas.ReminderResponse)
def create_reminder(reminder: schemas.ReminderCreate, db: Session = Depends(get_db)):
    db_reminder = models.Reminder(
        task=reminder.task,
        datetime=reminder.datetime,
        repeat=reminder.repeat,
        user_id=reminder.user_id,
        status=models.ReminderStatus.PENDING.value
    )
    db.add(db_reminder)
    db.commit()
    db.refresh(db_reminder)
    return db_reminder

@router.get("", response_model=list[schemas.ReminderResponse])
def get_reminders(db: Session = Depends(get_db)):
    return db.query(models.Reminder).all()

@router.delete("/{reminder_id}")
def delete_reminder(reminder_id: UUID, db: Session = Depends(get_db)):
    db_reminder = db.query(models.Reminder).filter(models.Reminder.id == reminder_id).first()
    if not db_reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    
    db.delete(db_reminder)
    db.commit()
    return {"message": "Reminder deleted successfully"}

@router.patch("/{reminder_id}", response_model=schemas.ReminderResponse)
def update_reminder(
    reminder_id: UUID,
    body: schemas.ReminderUpdate,
    db: Session = Depends(get_db),
):
    db_reminder = (
        db.query(models.Reminder).filter(models.Reminder.id == reminder_id).first()
    )
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
    return db_reminder


@router.patch("/{reminder_id}/complete", response_model=schemas.ReminderResponse)
def complete_reminder(reminder_id: UUID, db: Session = Depends(get_db)):
    db_reminder = db.query(models.Reminder).filter(models.Reminder.id == reminder_id).first()
    if not db_reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    
    db_reminder.status = models.ReminderStatus.COMPLETED.value
    db.commit()
    db.refresh(db_reminder)
    return db_reminder
