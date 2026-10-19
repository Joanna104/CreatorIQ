
"""Creator profile API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.creator_schemas import CreatorProfileCreate, CreatorProfileRead
from app.api.deps import get_session
from app.db.models import CreatorProfile

router = APIRouter(prefix="/creators", tags=["Creators"])


@router.post(
    "",
    response_model=CreatorProfileRead,
    status_code=status.HTTP_201_CREATED,
)
def create_creator(
    payload: CreatorProfileCreate,
    session: Session = Depends(get_session),
) -> CreatorProfile:
    creator = CreatorProfile(**payload.model_dump())
    session.add(creator)

    try:
        session.commit()
        session.refresh(creator)
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A creator with this email already exists.",
        ) from exc

    return creator


@router.get("/{creator_id}", response_model=CreatorProfileRead)
def get_creator(
    creator_id: int,
    session: Session = Depends(get_session),
) -> CreatorProfile:
    creator = session.get(CreatorProfile, creator_id)

    if creator is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Creator not found.",
        )

    return creator


@router.get("", response_model=list[CreatorProfileRead])
def list_creators(
    session: Session = Depends(get_session),
) -> list[CreatorProfile]:
    statement = select(CreatorProfile).order_by(CreatorProfile.id)
    return list(session.scalars(statement).all())
