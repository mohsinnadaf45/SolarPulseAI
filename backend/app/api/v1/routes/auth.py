"""
app/api/v1/routes/auth.py

Authentication endpoints:
  POST /api/v1/auth/token   — login, returns access + refresh tokens
  POST /api/v1/auth/refresh — exchange refresh token for new access token
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.user import RefreshTokenRequest, Token, UserCreate, UserResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/token",
    response_model=Token,
    summary="Login — obtain access and refresh tokens",
)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> Token:
    """
    OAuth2-compatible login endpoint.

    Accepts `username` and `password` as form fields.
    Returns `access_token`, `refresh_token`, and `token_type`.
    """
    result = await db.execute(
        select(User).where(
            or_(User.username == form_data.username, User.email == form_data.username)
        )
    )
    user: User | None = result.scalar_one_or_none()

    if user is None or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account",
        )

    access_token = create_access_token(subject=user.username)
    refresh_token = create_refresh_token(subject=user.username)
    return Token(access_token=access_token, refresh_token=refresh_token)


@router.post(
    "/refresh",
    response_model=Token,
    summary="Refresh access token using a refresh token",
)
async def refresh_token(
    payload: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> Token:
    """
    Exchange a valid refresh token for a new access + refresh token pair.
    """
    try:
        subject = decode_refresh_token(payload.refresh_token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        )

    result = await db.execute(select(User).where(User.username == subject))
    user: User | None = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    new_access = create_access_token(subject=user.username)
    new_refresh = create_refresh_token(subject=user.username)
    return Token(access_token=new_access, refresh_token=new_refresh)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user (development helper)",
)
async def register(
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Create a new user account.

    In production, restrict this endpoint to admin users only.
    """
    # Check username uniqueness
    result = await db.execute(select(User).where(User.username == data.username))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )
    # Check email uniqueness
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    user = User(
        username=data.username,
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
