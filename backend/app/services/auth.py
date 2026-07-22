import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from jwt import InvalidTokenError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.auth import (
    SupportUserCreate,
    SupportUserUpdate,
    UserListResponse,
    UserRegister,
    UserResponse,
)


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = UserRepository(session)

    async def register(self, data: UserRegister) -> User:
        email = str(data.email).strip().lower()
        if await self.repository.get_by_email(email) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email is already registered",
            )
        return await self.repository.create(
            email=email,
            hashed_password=hash_password(data.password),
            full_name=data.full_name,
        )

    async def authenticate(self, email: str, password: str) -> tuple[User, str, str]:
        user = await self.repository.get_by_email(email)
        now = datetime.now(UTC)
        if user is not None and user.locked_until is not None:
            locked_until = user.locked_until
            if locked_until.tzinfo is None:
                locked_until = locked_until.replace(tzinfo=UTC)
            if locked_until > now:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many failed attempts. Try again later.",
                )
        if user is None or not user.is_active or not verify_password(
            password, user.hashed_password
        ):
            if user is not None and user.is_active:
                await self.repository.register_failed_login(
                    user,
                    max_attempts=settings.login_max_attempts,
                    lock_minutes=settings.login_lock_minutes,
                )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        await self.repository.clear_failed_login(user)
        access_token = create_access_token(
            user_id=user.id,
            role=user.role,
            token_version=user.token_version,
        )
        refresh_token = create_refresh_token(
            user_id=user.id,
            role=user.role,
            token_version=user.token_version,
        )
        return user, access_token, refresh_token

    async def refresh(self, refresh_token: str) -> tuple[str, str]:
        credentials_error = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
        try:
            payload = decode_token(refresh_token, "refresh")
            user_id = int(payload.get("sub", ""))
        except (InvalidTokenError, TypeError, ValueError):
            raise credentials_error
        user = await self.repository.get_by_id(user_id)
        if (
            user is None
            or not user.is_active
            or int(payload.get("ver", -1)) != user.token_version
        ):
            raise credentials_error
        return (
            create_access_token(
                user_id=user.id, role=user.role, token_version=user.token_version
            ),
            create_refresh_token(
                user_id=user.id, role=user.role, token_version=user.token_version
            ),
        )

    async def request_email_verification(self, user: User) -> str | None:
        if user.is_email_verified:
            return None
        token = secrets.token_urlsafe(32)
        await self.repository.set_verification_token(user, self._token_hash(token))
        return token

    async def verify_email(self, token: str) -> None:
        user = await self.repository.get_by_verification_token_hash(
            self._token_hash(token)
        )
        if user is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid verification token")
        await self.repository.verify_email(user)

    async def forgot_password(self, email: str) -> str | None:
        user = await self.repository.get_by_email(email)
        if user is None or not user.is_active:
            return None
        token = secrets.token_urlsafe(32)
        await self.repository.set_password_reset(
            user,
            token_hash=self._token_hash(token),
            expires_at=datetime.now(UTC) + timedelta(minutes=30),
        )
        return token

    async def reset_password(self, token: str, new_password: str) -> None:
        user = await self.repository.get_by_password_reset_token_hash(
            self._token_hash(token)
        )
        if user is None or user.password_reset_expires_at is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid reset token")
        expires_at = user.password_reset_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= datetime.now(UTC):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Reset token has expired")
        await self.repository.update_password(user, hash_password(new_password))

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    async def update_profile(self, user: User, full_name: str | None) -> User:
        return await self.repository.update_profile(user, full_name)

    async def change_password(
        self,
        user: User,
        current_password: str,
        new_password: str,
    ) -> None:
        if not verify_password(current_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect",
            )
        if current_password == new_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password must be different",
            )
        await self.repository.update_password(user, hash_password(new_password))

    async def list_users(
        self, page: int, page_size: int, role: str | None = None
    ) -> UserListResponse:
        users, total = await self.repository.list_users(
            page=page,
            page_size=page_size,
            role=role,
        )
        return UserListResponse(
            items=[UserResponse.model_validate(user) for user in users],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=(total + page_size - 1) // page_size,
        )

    async def create_support(self, data: SupportUserCreate) -> User:
        email = str(data.email).strip().lower()
        if await self.repository.get_by_email(email) is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "Email is already registered")
        user = await self.repository.create(
            email=email,
            hashed_password=hash_password(data.password),
            full_name=data.full_name,
            role="support",
        )
        if not data.is_active:
            user = await self.repository.set_status(user, False)
        return user

    async def update_support(self, user_id: int, data: SupportUserUpdate) -> User:
        user = await self.repository.get_by_id(user_id)
        if user is None or user.role != "support":
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Support account not found")
        email = str(data.email).strip().lower() if data.email is not None else None
        if email is not None:
            existing = await self.repository.get_by_email(email)
            if existing is not None and existing.id != user.id:
                raise HTTPException(status.HTTP_409_CONFLICT, "Email is already registered")
        return await self.repository.update_managed_user(
            user,
            email=email,
            full_name=data.full_name,
            hashed_password=hash_password(data.password) if data.password else None,
        )

    async def delete_support(self, user_id: int) -> User:
        user = await self.repository.get_by_id(user_id)
        if user is None or user.role != "support" or user.is_deleted:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Support account not found")
        return await self.repository.soft_delete(user)

    async def set_role(self, user_id: int, role: str) -> User:
        user = await self.repository.get_by_id(user_id)
        if user is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
        return await self.repository.set_role(user, role)

    async def set_status(self, user_id: int, is_active: bool) -> User:
        user = await self.repository.get_by_id(user_id)
        if user is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
        return await self.repository.set_status(user, is_active)
