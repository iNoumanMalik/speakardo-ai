import logging
import os

import firebase_admin
from firebase_admin import credentials

logger = logging.getLogger(__name__)

_initialized = False


def init_firebase() -> bool:
    global _initialized

    if _initialized:
        return True

    if firebase_admin._apps:
        _initialized = True
        return True

    cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH", "firebase-service-account.json")
    if not os.path.exists(cred_path):
        logger.warning(
            "Firebase credentials file not found at %s. Push notifications are disabled.",
            cred_path,
        )
        return False

    try:
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        _initialized = True
        logger.info("Firebase Admin initialized.")
        return True
    except Exception as exc:  # pragma: no cover - external service init
        logger.error("Failed to initialize Firebase Admin: %s", exc)
        return False
