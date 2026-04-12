from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from deps import get_current_user
import models
import schemas

router = APIRouter()


@router.post("/register-device", response_model=schemas.DeviceRegisterResponse)
def register_device(
    data: schemas.DeviceRegisterRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    existing = (
        db.query(models.DeviceToken)
        .filter(models.DeviceToken.token == data.device_token)
        .first()
    )

    if existing:
        if existing.user_id != current_user.id:
            # Re-binding token to the authenticated account (e.g. new login on same device).
            pass
        existing.user_id = current_user.id
        existing.platform = data.platform
        db.commit()
        return {"message": "Device token updated"}

    db_token = models.DeviceToken(
        user_id=current_user.id,
        token=data.device_token,
        platform=data.platform,
    )
    db.add(db_token)
    db.commit()
    return {"message": "Device registered"}
