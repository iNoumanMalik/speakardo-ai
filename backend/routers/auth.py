from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

import models
import schemas
from rate_limit import limiter
from auth_security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    require_jwt_secret,
    verify_password,
)
from database import get_db

router = APIRouter()


def _issue_tokens(user: models.User) -> schemas.TokenResponse:
    try:
        require_jwt_secret()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        ) from e
    return schemas.TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
        token_type="bearer",
    )


@router.post("/register", response_model=schemas.TokenResponse)
@limiter.limit("20/minute")
def register(
    request: Request,
    body: schemas.UserRegisterRequest,
    db: Session = Depends(get_db),
):
    _ = request
    if db.query(models.User).filter(models.User.email == body.email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    user = models.User(
        email=body.email.strip().lower(),
        password=hash_password(body.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _issue_tokens(user)


@router.post("/login", response_model=schemas.TokenResponse)
@limiter.limit("10/minute")
def login(
    request: Request,
    body: schemas.UserLoginRequest,
    db: Session = Depends(get_db),
):
    _ = request  # used by SlowAPI rate limiter
    user = (
        db.query(models.User)
        .filter(models.User.email == body.email.strip().lower())
        .first()
    )
    if not user or not verify_password(body.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    return _issue_tokens(user)


@router.post("/refresh", response_model=schemas.TokenResponse)
@limiter.limit("30/minute")
def refresh_tokens(
    request: Request,
    body: schemas.RefreshTokenRequest,
    db: Session = Depends(get_db),
):
    _ = request
    payload = decode_token(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )
    try:
        user_id = UUID(sub)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )
    try:
        require_jwt_secret()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        ) from e
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )
    return schemas.TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
        token_type="bearer",
    )
