import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def send_push_notification(
    user_id: Optional[str], task: str, reminder_id: str
) -> bool:
    """
    Best-effort notification sender for MVP.
    - If Firebase is configured, try sending via firebase-admin.
    - Otherwise, log a trigger so reminder delivery is observable/testable.
    """
    # MVP fallback path to keep milestone testable without Firebase setup.
    firebase_cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
    device_token = os.getenv("FCM_DEVICE_TOKEN")

    if not firebase_cred_path or not device_token:
        logger.info(
            "REMINDER NOTIFICATION (fallback): user_id=%s reminder_id=%s task=%s",
            user_id,
            reminder_id,
            task,
        )
        return True

    try:
        import firebase_admin
        from firebase_admin import credentials, messaging

        if not firebase_admin._apps:
            cred = credentials.Certificate(firebase_cred_path)
            firebase_admin.initialize_app(cred)

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
