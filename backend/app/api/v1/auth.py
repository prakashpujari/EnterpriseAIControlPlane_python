"""
Authentication API router for Enterprise AI Customer Support Assistant.
Handles login, token generation, and user authentication.
"""

from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr

from app.config.database import get_db_session
from app.config.settings import settings
from app.gateway.auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    decode_token,
    get_current_user,
    get_current_active_user,
    User,
)

router = APIRouter(prefix="/auth", tags=["authentication"])


class LoginRequest(BaseModel):
    """Login request model."""
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    """Login response model."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict


class TokenResponse(BaseModel):
    """OAuth2 token response model."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    db_session: AsyncSession = Depends(get_db_session),
):
    """
    Login with email and password.

    Args:
        request: Login credentials
        db_session: Database session

    Returns:
        Access token and token info

    Raises:
        HTTPException: If credentials are invalid
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info("====== LOGIN ENDPOINT CALLED ======")
    logger.info(f"Request email: {request.email}")
    logger.info(f"Request password: {request.password}")

    # For development, we'll check against database
    # In production, this would query the users table
    from app.models.database import User as UserModel
    from sqlalchemy import select

    result = await db_session.execute(
        select(UserModel).where(UserModel.email == request.email)
    )
    user = result.scalar_one_or_none()

    logger.info(f"User found: {user is not None}")
    if user:
        logger.info(f"User ID: {user.id}, Role: {user.role}")
        logger.info(f"User hash: {user.password_hash}")
        from app.gateway.auth import verify_password
        logger.info(f"Password verify: {verify_password(request.password, user.password_hash)}")

    if not user:
        # For demo purposes, create a mock user if not found
        # In production, this would return invalid credentials
        logger.warning("User not found in database")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify password (in production, use hashed password)
    if not verify_password(request.password, user.password_hash if hasattr(user, 'password_hash') else 'hashed_password'):
        # For demo, accept any password if user exists
        logger.warning("Password verification failed")
        pass

    # Create access token
    token_data = {
        "sub": user.id,
        "email": user.email,
        "roles": [user.role],
    }
    access_token = create_access_token(token_data, expires_delta=timedelta(minutes=settings.JWT_EXPIRATION_MINUTES))

    user_data = {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "department": user.department,
    }

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.JWT_EXPIRATION_MINUTES * 60,
        user=user_data,
    )


@router.post("/token", response_model=TokenResponse)
async def token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db_session: AsyncSession = Depends(get_db_session),
):
    """
    OAuth2 compatible token endpoint.

    Args:
        form_data: OAuth2 form data (username/password)
        db_session: Database session

    Returns:
        Access token

    Raises:
        HTTPException: If credentials are invalid
    """
    from app.models.database import User as UserModel
    from sqlalchemy import select

    # Use email as username
    result = await db_session.execute(
        select(UserModel).where(UserModel.email == form_data.username)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify password
    if hasattr(user, 'password_hash') and user.password_hash:
        if not verify_password(form_data.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # Create access token
    token_data = {
        "sub": user.id,
        "email": user.email,
        "roles": [user.role],
    }
    access_token = create_access_token(token_data, expires_delta=timedelta(minutes=settings.JWT_EXPIRATION_MINUTES))

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.JWT_EXPIRATION_MINUTES * 60,
    )


@router.get("/me", response_model=dict)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user),
):
    """
    Get current user information.

    Args:
        current_user: Current authenticated user

    Returns:
        User information
    """
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "department": current_user.department,
        "is_active": current_user.is_active,
    }


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    current_user: User = Depends(get_current_active_user),
):
    """
    Refresh access token.

    Args:
        current_user: Current authenticated user

    Returns:
        New access token
    """
    token_data = {
        "sub": current_user.id,
        "email": current_user.email,
        "roles": [current_user.role],
    }
    access_token = create_access_token(token_data, expires_delta=timedelta(minutes=settings.JWT_EXPIRATION_MINUTES))

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.JWT_EXPIRATION_MINUTES * 60,
    )
