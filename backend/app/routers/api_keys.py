from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import generate_api_key
from app.dependencies import get_current_admin
from app.models.api_key import ApiKey
from app.schemas.api_key import ApiKeyCreate, ApiKeyCreated, ApiKeyOut

router = APIRouter(prefix="/api-keys", tags=["API Keys (Integrations)"], dependencies=[Depends(get_current_admin)])


@router.get("", response_model=List[ApiKeyOut])
def list_api_keys(db: Session = Depends(get_db)):
    return db.query(ApiKey).order_by(ApiKey.created_at.desc()).all()


@router.post("", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
def create_api_key(payload: ApiKeyCreate, db: Session = Depends(get_db)):
    raw_key, hashed, prefix = generate_api_key()
    key = ApiKey(name=payload.name, hashed_key=hashed, key_prefix=prefix)
    db.add(key)
    db.commit()
    db.refresh(key)

    return ApiKeyCreated(
        id=key.id,
        name=key.name,
        key_prefix=key.key_prefix,
        is_active=key.is_active,
        created_at=key.created_at,
        last_used_at=key.last_used_at,
        api_key=raw_key,
    )


@router.patch("/{key_id}/revoke", response_model=ApiKeyOut)
def revoke_api_key(key_id: int, db: Session = Depends(get_db)):
    key = db.query(ApiKey).filter(ApiKey.id == key_id).first()
    if not key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    key.is_active = False
    db.commit()
    db.refresh(key)
    return key


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_api_key(key_id: int, db: Session = Depends(get_db)):
    key = db.query(ApiKey).filter(ApiKey.id == key_id).first()
    if not key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    db.delete(key)
    db.commit()
