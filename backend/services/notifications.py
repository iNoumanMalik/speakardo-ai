import logging
from dataclasses import dataclass
from typing import Optional

from firebase_admin import messaging

from services.firebase import init_firebase

logger = logging.getLogger(__name__)


@dataclass
class NotificationResult:
    success: bool
    permanent_failure: bool = False
    invalid_token: bool = False
    provider_message_id: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


def send_push_notification(
    device_token: str, user_id: Optional[str], task: str, reminder_id: str
) -> NotificationResult:
    """
    Best-effort notification sender for MVP.
    - If Firebase is configured, try sending via firebase-admin.
    - Otherwise, log a trigger so reminder delivery is observable/testable.
    """
    if not init_firebase():
        logger.info(
            "event=push_send provider=fallback success=true user_id=%s reminder_id=%s task_len=%s",
            user_id,
            reminder_id,
            len(task or ""),
        )
        return NotificationResult(success=True, provider_message_id="fallback")

    try:
        # Data-first payload so Android can show actionable local notifications.
        message = messaging.Message(
            token=device_token,
            data={
                "reminder_id": reminder_id,
                "user_id": str(user_id or ""),
                "task": task,
                "type": "reminder_due",
            },
            android=messaging.AndroidConfig(priority="high"),
            apns=messaging.APNSConfig(
                headers={"apns-priority": "10"},
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        alert=messaging.ApsAlert(title="Reminder", body=task),
                        sound="default",
                    ),
                ),
            ),
        )
        message_id = messaging.send(message)
        logger.info(
            "event=push_send provider=fcm success=true user_id=%s reminder_id=%s message_id=%s",
            user_id,
            reminder_id,
            message_id,
        )
        return NotificationResult(success=True, provider_message_id=message_id)
    except Exception as exc:  # pragma: no cover - external service best-effort
        msg = str(exc)
        invalid = (
            "registration-token-not-registered" in msg
            or "Requested entity was not found" in msg
            or "Invalid registration token" in msg
        )
        logger.error(
            "event=push_send provider=fcm success=false reminder_id=%s invalid_token=%s error=%s",
            reminder_id,
            invalid,
            msg,
        )
        return NotificationResult(
            success=False,
            permanent_failure=invalid,
            invalid_token=invalid,
            error_code="invalid_token" if invalid else "send_failed",
            error_message=msg,
        )
