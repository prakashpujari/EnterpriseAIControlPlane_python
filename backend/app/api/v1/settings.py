"""
Settings API router for user preferences and configuration.
"""

print("!!! SETTINGS MODULE LOADED")

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.config.database import get_db_session
from app.models.database import User
from app.gateway.auth import get_current_active_user

router = APIRouter(prefix="/settings", tags=["settings"])


class UserSettings(BaseModel):
    """User settings model."""
    notification_preference: Optional[bool] = None
    dark_mode: Optional[bool] = None
    api_access: Optional[bool] = None


class UserSettingsResponse(BaseModel):
    """User settings response model."""
    notification_preference: bool
    dark_mode: bool
    api_access: bool


@router.get("/", response_model=UserSettingsResponse)
async def get_user_settings(
    current_user: User = Depends(get_current_active_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    """
    Get current user's settings.

    Args:
        current_user: Current authenticated user
        db_session: Database session

    Returns:
        User settings
    """
    print("!!! get_user_settings called")
    # For the dev user (when DISABLE_AUTH is true), skip DB refresh
    if getattr(current_user, 'id', None) == "dev-user":
        return UserSettingsResponse(
            notification_preference=current_user.notification_preference,
            dark_mode=current_user.dark_mode,
            api_access=current_user.api_access,
        )

    # For normal auth, refresh the user from database to get latest values
    await db_session.refresh(current_user)

    return UserSettingsResponse(
        notification_preference=current_user.notification_preference,
        dark_mode=current_user.dark_mode,
        api_access=current_user.api_access,
    )


@router.put("/", response_model=UserSettingsResponse)
async def update_user_settings(
    user_settings: UserSettings,
    current_user: User = Depends(get_current_active_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    """
    Update current user's settings.

    Args:
        user_settings: Settings to update
        current_user: Current authenticated user
        db_session: Database session

    Returns:
        Updated user settings
    """
    print("!!! update_user_settings called")
    # Update only the fields that were provided
    if user_settings.notification_preference is not None:
        current_user.notification_preference = user_settings.notification_preference
    if user_settings.dark_mode is not None:
        current_user.dark_mode = user_settings.dark_mode
    if user_settings.api_access is not None:
        current_user.api_access = user_settings.api_access

    # For the dev user (when DISABLE_AUTH is true), skip DB commit
    if getattr(current_user, 'id', None) == "dev-user":
        return UserSettingsResponse(
            notification_preference=current_user.notification_preference,
            dark_mode=current_user.dark_mode,
            api_access=current_user.api_access,
        )

    # For normal auth, save to database
    await db_session.commit()
    await db_session.refresh(current_user)

    return UserSettingsResponse(
        notification_preference=current_user.notification_preference,
        dark_mode=current_user.dark_mode,
        api_access=current_user.api_access,
    )


@router.post("/reset", response_model=UserSettingsResponse)
async def reset_user_settings(
    current_user: User = Depends(get_current_active_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    """
    Reset user settings to defaults.

    Args:
        current_user: Current authenticated user
        db_session: Database session

    Returns:
        Reset user settings
    """
    print("!!! reset_user_settings called")
    current_user.notification_preference = True
    current_user.dark_mode = False
    current_user.api_access = False

    # For the dev user (when DISABLE_AUTH is true), skip DB commit
    if getattr(current_user, 'id', None) == "dev-user":
        return UserSettingsResponse(
            notification_preference=current_user.notification_preference,
            dark_mode=current_user.dark_mode,
            api_access=current_user.api_access,
        )

    # For normal auth, save to database
    await db_session.commit()
    await db_session.refresh(current_user)

    return UserSettingsResponse(
        notification_preference=current_user.notification_preference,
        dark_mode=current_user.dark_mode,
        api_access=current_user.api_access,
    )