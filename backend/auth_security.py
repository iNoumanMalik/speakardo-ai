import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from uuid import UUID

import bcrypt
from jose import JWTError, jwt

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "14"))


def require_jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET", "")
    if not secret or len(secret) < 16:
        raise ValueError(
            "Set JWT_SECRET in environment (min 16 characters). "
            "Example: JWT_SECRET=$(openssl rand -hex 32)"
        )
    return secret


def hash_password(plain: str) -> str:
    digest = bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt())
    return digest.decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain.encode("utf-8"),
            hashed.encode("ascii"),
        )
    except ValueError:
        return False


def _create_token(
    subject: UUID,
    token_type: str,
    expires_delta: timedelta,
) -> str:
    secret = require_jwt_secret()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(subject),
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def create_access_token(user_id: UUID) -> str:
    return _create_token(
        user_id,
        "access",
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(user_id: UUID) -> str:
    return _create_token(
        user_id,
        "refresh",
        timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        secret = os.getenv("JWT_SECRET", "")
        if not secret or len(secret) < 16:
            return None
        return jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None
