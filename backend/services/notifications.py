import logging
from typing import Optional

from firebase_admin import messaging

from services.firebase import init_firebase

logger = logging.getLogger(__name__)


def send_push_notification(
    device_token: str, user_id: Optional[str], task: str, reminder_id: str
) -> bool:
    """
    Best-effort notification sender for MVP.
    - If Firebase is configured, try sending via firebase-admin.
    - Otherwise, log a trigger so reminder delivery is observable/testable.
    """
    if not init_firebase():
        logger.info(
            "REMINDER NOTIFICATION (fallback/no-firebase): user_id=%s reminder_id=%s task=%s",
            user_id,
            reminder_id,
            task,
        )
        return True

    try:
        message = messaging.Message(
            token=device_token,
            notification=messaging.Notification(
                title="Reminder",
                body=task,
            ),
            data={"reminder_id": reminder_id, "user_id": str(user_id or "")},
        )
        messaging.send(message)
        logger.info(
            "REMINDER NOTIFICATION (fcm): user_id=%s reminder_id=%s", user_id, reminder_id
        )
        return True
    except Exception as exc:  # pragma: no cover - external service best-effort
        logger.error("FCM send failed for reminder_id=%s: %s", reminder_id, exc)
        return False
