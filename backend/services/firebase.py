import logging
import os

import firebase_admin
from firebase_admin import credentials

logger = logging.getLogger(__name__)

_initialized = False


def init_firebase() -> bool:
    global _initialized

    if _initialized:
        logger.debug("event=firebase_init_cached initialized=true")
        return True

    if firebase_admin._apps:
        _initialized = True
        logger.info("event=firebase_init_reuse_existing_app initialized=true")
        return True

    cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH", "").strip()
    if not cred_path:
        logger.error("event=firebase_init_skipped reason=missing_credentials_path")
        return False
    if not os.path.exists(cred_path):
        logger.error("event=firebase_init_skipped reason=credentials_file_not_found path=%s", cred_path)
        return False

    try:
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        _initialized = True
        logger.info("event=firebase_initialized path=%s", cred_path)
        return True
    except Exception as exc:  # pragma: no cover - external service init
        logger.exception("event=firebase_init_failed error=%s", exc)
        return False
