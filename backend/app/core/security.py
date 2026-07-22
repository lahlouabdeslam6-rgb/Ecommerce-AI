from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt import InvalidTokenError
from pwdlib import PasswordHash
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.sqlite import get_sqlite_session
from app.models.user import User
from app.repositories.user import UserRepository


password_hash = PasswordHash.recommended()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "customer": {
        "products:read",
        "profile:read",
        "cart:manage",
        "orders:create",
        "orders:read-own",
    },
    "support": {
        "products:read",
        "products:update",
        "profile:read",
        "orders:read",
        "orders:update",
        "support:manage",
    },
    "admin": {"*"},
}


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def create_access_token(*, user_id: int, role: str, token_version: int = 0) -> str:
    expires_at = datetime.now(UTC) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    return jwt.encode(
        {
            "sub": str(user_id),
            "role": role,
            "type": "access",
            "ver": token_version,
            "exp": expires_at,
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token(*, user_id: int, role: str, token_version: int = 0) -> str:
    expires_at = datetime.now(UTC) + timedelta(
        days=settings.refresh_token_expire_days
    )
    return jwt.encode(
        {
            "sub": str(user_id),
            "role": role,
            "type": "refresh",
            "ver": token_version,
            "exp": expires_at,
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_token(token: str, expected_type: str) -> dict[str, object]:
    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    if payload.get("type") != expected_type:
        raise InvalidTokenError("Incorrect token type")
    return payload


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token, "access")
        user_id = int(payload.get("sub", ""))
    except (InvalidTokenError, TypeError, ValueError):
        raise credentials_error

    user = await UserRepository(session).get_by_id(user_id)
    if (
        user is None
        or not user.is_active
        or int(payload.get("ver", -1)) != user.token_version
    ):
        raise credentials_error
    return user


def require_roles(*allowed_roles: str) -> Callable[..., User]:
    async def role_dependency(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role",
            )
        return current_user

    return role_dependency


def require_permission(permission: str) -> Callable[..., User]:
    async def permission_dependency(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        permissions = ROLE_PERMISSIONS.get(current_user.role, set())
        if "*" not in permissions and permission not in permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permission",
            )
        return current_user

    return permission_dependency
