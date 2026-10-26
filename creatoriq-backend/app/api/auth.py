
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


from app.api.deps import get_session
from app.core.config import get_settings
from app.db.models import UserAccount


router = APIRouter(prefix="/auth", tags=["Authentication"])

password_hash = PasswordHash.recommended()

class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be empty.")
        return value


class RegisterResponse(BaseModel):
    message: str
    email: EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int



@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    payload: RegisterRequest,
    session: Session = Depends(get_session),
):
    email = str(payload.email).strip().lower()

    if payload.password != payload.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Passwords do not match.",
        )

    existing = session.scalar(
        select(UserAccount).where(UserAccount.email == email)
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )


    account = UserAccount(
        name=payload.name.strip(),
        email=email,
        password_hash=password_hash.hash(payload.password),
    )
    session.add(account)

    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        ) from exc

    return RegisterResponse(
        message="Account created successfully.",
        email=email,
    )

@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    session: Session = Depends(get_session),
):
    email = str(payload.email).strip().lower()

    account = session.scalar(
        select(UserAccount).where(UserAccount.email == email)
    )

    # Use the same generic error for unknown emails and wrong passwords.
    if account is None or not password_hash.verify(
        payload.password, account.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    settings = get_settings()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(
        minutes=settings.jwt_access_token_minutes
    )

    access_token = jwt.encode(
        {
            "sub": str(account.id),
            "iat": now,
            "exp": expires_at,
        },
        settings.jwt_secret_key.get_secret_value(),
        algorithm="HS256",
    )

    return LoginResponse(
        access_token=access_token,
        expires_in=settings.jwt_access_token_minutes * 60,
    )
