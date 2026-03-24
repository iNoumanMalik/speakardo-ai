from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
import models
import schemas

router = APIRouter()


@router.post("/register-device", response_model=schemas.DeviceRegisterResponse)
def register_device(
    data: schemas.DeviceRegisterRequest, db: Session = Depends(get_db)
):
    existing = (
        db.query(models.DeviceToken)
        .filter(models.DeviceToken.token == data.device_token)
        .first()
    )

    if existing:
        existing.user_id = data.user_id
        existing.platform = data.platform
        db.commit()
        return {"message": "Device token updated"}

    db_token = models.DeviceToken(
        user_id=data.user_id,
        token=data.device_token,
        platform=data.platform,
    )
    db.add(db_token)
    db.commit()
    return {"message": "Device registered"}
