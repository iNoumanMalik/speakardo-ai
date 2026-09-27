"""Memory API (8.1 subset of design §12): list, forget, undo.

Every query is scoped to the current user; another user's memory is a 404.
Edit, export, delete-all and settings arrive with the Memory screen in 8.2.
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from deps import get_current_user
from rate_limit import limiter
from services import memory_store

router = APIRouter()
logger = logging.getLogger(__name__)


def _memory_or_404(db: Session, user: models.User, memory_id: UUID) -> models.Memory:
    memory = memory_store.get_for_user(db, user.id, memory_id)
    if memory is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    return memory


@router.get("", response_model=list[schemas.MemoryResponse])
@limiter.limit("60/minute")
def list_memories(
    request: Request,
    kind: Optional[str] = Query(None, max_length=24),
    category: Optional[str] = Query(None, max_length=16),
    q: Optional[str] = Query(None, max_length=200, description="Text to search for"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _ = request
    rows = memory_store.list_active(db, current_user.id, kind=kind, category=category, q=q)
    logger.info("event=memory_list user_id=%s count=%s", current_user.id, len(rows))
    return rows


@router.delete("/{memory_id}", response_model=schemas.MemoryResponse)
@limiter.limit("60/minute")
def forget_memory(
    request: Request,
    memory_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Forget a memory: hidden now, erased for good after 24 hours (undo works until then)."""
    _ = request
    memory = _memory_or_404(db, current_user, memory_id)
    if memory.status != models.MemoryStatus.DELETED:
        memory_store.forget(db, memory)
        db.commit()
        db.refresh(memory)
    return memory


@router.post("/{memory_id}/undo", response_model=schemas.MemoryUndoResponse)
@limiter.limit("60/minute")
def undo_memory_action(
    request: Request,
    memory_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Reverse the latest save, update or forget of this memory."""
    _ = request
    memory = _memory_or_404(db, current_user, memory_id)
    try:
        undone = memory_store.undo(db, memory)
    except memory_store.NothingToUndo:
        raise HTTPException(status_code=409, detail="Nothing to undo")
    db.commit()
    db.refresh(memory)
    return schemas.MemoryUndoResponse(undone=undone, memory=memory)
