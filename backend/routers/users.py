import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from deps import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/me", response_model=schemas.UserProfileResponse)
def get_current_user_profile(
    current_user: models.User = Depends(get_current_user),
):
    return current_user


@router.patch("/me/timezone", response_model=schemas.UserProfileResponse)
def update_user_timezone(
    body: schemas.UserTimezoneUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Update timezone from device detection (e.g. after travel)."""
    if current_user.timezone == body.timezone:
        return current_user
    current_user.timezone = body.timezone
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    logger.info(
        "event=user_timezone_updated user_id=%s timezone=%s",
        current_user.id,
        current_user.timezone,
    )
    return current_user


@router.patch("/me/preferences", response_model=schemas.UserProfileResponse)
def update_user_preferences(
    body: schemas.UserPreferencesUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if body.timezone is None and body.notifications_enabled is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No preference fields to update",
        )

    if body.timezone is not None:
        current_user.timezone = body.timezone
    if body.notifications_enabled is not None:
        current_user.notifications_enabled = body.notifications_enabled

    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    logger.info(
        "event=user_preferences_updated user_id=%s timezone=%s notifications_enabled=%s",
        current_user.id,
        current_user.timezone,
        current_user.notifications_enabled,
    )
    return current_user


@router.post("/me/feedback", response_model=schemas.FeedbackResponse)
def submit_feedback(
    body: schemas.FeedbackCreate,
    current_user: models.User = Depends(get_current_user),
):
    # Delivery channel (email, Slack, DB, etc.) can be wired here later.
    logger.info(
        "event=user_feedback_received user_id=%s email=%s message_len=%s",
        current_user.id,
        current_user.email,
        len(body.message.strip()),
    )
    return schemas.FeedbackResponse(
        message="Thank you for your feedback. We appreciate your input.",
    )
