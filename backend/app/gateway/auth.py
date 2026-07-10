"""
Authentication module for FastAPI Gateway.
Implements JWT/OAuth2 authentication with role-based claims.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.models.database import User, UserRole
from app.config.database import get_db_session

logger = logging.getLogger(__name__)

# OAuth2 scheme. auto_error=False so a missing token surfaces as a 401 from
# our own logic (and so DISABLE_AUTH can short-circuit before any 403).
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)

# Built-in dev user used when AUTH is disabled for local development.
DEV_USER = User(
    id="dev-user",
    email="dev@example.com",
    full_name="Dev User",
    role="support_engineer",
    department="Development",
    is_active=True,
    notification_preference=True,
    dark_mode=False,
    api_access=False,
)

# Password hashing
pwd_context = CryptContext(schemes=["sha256_crypt", "bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.

    Args:
        data: Payload data (must include 'sub' for user ID)
        expires_delta: Optional expiration delta

    Returns:
        JWT token string
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRATION_MINUTES)

    to_encode.update({"exp": expire, "iat": datetime.utcnow()})

    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY.get_secret_value(),
        algorithm=settings.JWT_ALGORITHM,
    )
    return encoded_jwt


def decode_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate a JWT token.

    Args:
        token: JWT token string

    Returns:
        Decoded token payload

    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY.get_secret_value(),
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError as e:
        logger.warning(f"Token decode error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db_session: AsyncSession = Depends(get_db_session),
) -> User:
    """
    Get the current authenticated user from JWT token.

    Args:
        token: JWT token from OAuth2 scheme
        db_session: Database session (injected via dependency)

    Returns:
        User object

    Raises:
        HTTPException: If user not found or token invalid
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Dev-only auth bypass: return a built-in user so the app is usable
    # locally without a login flow. Gated behind the DISABLE_AUTH setting,
    # which must never be enabled in production.
    if settings.DISABLE_AUTH:
        logger.warning("Auth disabled (DISABLE_AUTH=true) - returning dev user")
        return DEV_USER

    if not token:
        raise credentials_exception

    try:
        payload = decode_token(token)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception

        roles: List[str] = payload.get("roles", [])
        email: str = payload.get("email")

    except JWTError:
        raise credentials_exception

    # Fetch user from database
    from app.models.database import User as UserModel
    from sqlalchemy import select

    result = await db_session.execute(
        select(UserModel).where(UserModel.id == user_id)
    )
    user_row = result.scalar_one_or_none()

    if user_row is None:
        raise credentials_exception

    # Create User object from row
    user = User(
        id=user_row.id,
        email=user_row.email,
        full_name=user_row.full_name,
        role=user_row.role,
        department=user_row.department,
        is_active=user_row.is_active,
        created_at=user_row.created_at,
        last_login=user_row.last_login,
    )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Get the current active user (not disabled).

    Args:
        current_user: User from get_current_user

    Returns:
        Active User object

    Raises:
        HTTPException: If user is disabled
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )
    return current_user


class RoleChecker:
    """
    Role-based access control checker.
    """

    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, current_user: User = Depends(get_current_user)) -> User:
        """
        Check if the current user has one of the allowed roles.

        Args:
            current_user: Authenticated user

        Returns:
            User if authorized

        Raises:
            HTTPException: If user lacks required role
        """
        if current_user.role not in self.allowed_roles:
            logger.warning(
                f"Access denied for user {current_user.id} with role {current_user.role}. "
                f"Required: {self.allowed_roles}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user


def require_role(*roles: str):
    """
    Decorator/factory for role-based access control.

    Usage:
        @app.get("/admin")
        async def admin_endpoint(user: User = Depends(require_role("admin"))):
            ...

    Args:
        *roles: Allowed role names

    Returns:
        RoleChecker instance
    """
    return RoleChecker(list(roles))


# Permission-based access control
class PermissionChecker:
    """
    Fine-grained permission checker.
    """

    def __init__(self, resource: str, action: str):
        self.resource = resource
        self.action = action

    async def __call__(
        self,
        current_user: User = Depends(get_current_active_user),
        db_session = None,
    ) -> User:
        """
        Check if user has permission for resource/action.

        Args:
            current_user: Authenticated user
            db_session: Database session

        Returns:
            User if authorized

        Raises:
            HTTPException: If permission denied
        """
        if db_session is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database session not available",
            )

        # Check role permissions
        from app.models.database import Permission

        result = await db_session.execute(
            "SELECT * FROM permissions WHERE role_id = :role_id AND resource = :resource AND action = :action",
            {"role_id": current_user.role, "resource": self.resource, "action": self.action}
        )
        permission = result.fetchone()

        if permission is None:
            logger.warning(
                f"Permission denied for user {current_user.id}. "
                f"Missing permission: {self.resource}:{self.action}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied",
            )

        return current_user


def require_permission(resource: str, action: str):
    """
    Factory for permission-based access control.

    Args:
        resource: Resource name (e.g., "documents", "users")
        action: Action (e.g., "read", "write", "delete")

    Returns:
        PermissionChecker instance
    """
    return PermissionChecker(resource, action)