from sqlalchemy import func
from sqlalchemy.orm import Session

import models


def enforce_owned_entities(db: Session) -> None:
    """Fail fast if legacy orphan rows exist after auth rollout."""
    orphan_reminders = (
        db.query(func.count(models.Reminder.id))
        .filter(models.Reminder.user_id.is_(None))
        .scalar()
        or 0
    )
    orphan_tokens = (
        db.query(func.count(models.DeviceToken.id))
        .filter(models.DeviceToken.user_id.is_(None))
        .scalar()
        or 0
    )
    if orphan_reminders or orphan_tokens:
        raise RuntimeError(
            "Found legacy rows with NULL user_id "
            f"(reminders={orphan_reminders}, device_tokens={orphan_tokens}). "
            "Run one-time backfill SQL before starting the API."
        )
