from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.email == email.strip().lower())
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: int) -> User | None:
        return await self.session.get(User, user_id)

    async def create(
        self,
        *,
        email: str,
        hashed_password: str,
        full_name: str | None,
        role: str = "customer",
    ) -> User:
        user = User(
            email=email.strip().lower(),
            hashed_password=hashed_password,
            full_name=full_name.strip() if full_name else None,
            role=role,
        )
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def update_profile(self, user: User, full_name: str | None) -> User:
        user.full_name = full_name.strip() if full_name else None
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def update_password(self, user: User, hashed_password: str) -> None:
        user.hashed_password = hashed_password
        user.token_version += 1
        user.password_reset_token_hash = None
        user.password_reset_expires_at = None
        await self.session.commit()

    async def register_failed_login(
        self,
        user: User,
        *,
        max_attempts: int,
        lock_minutes: int,
    ) -> None:
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= max_attempts:
            user.locked_until = datetime.now(UTC) + timedelta(minutes=lock_minutes)
            user.failed_login_attempts = 0
        await self.session.commit()

    async def clear_failed_login(self, user: User) -> None:
        user.failed_login_attempts = 0
        user.locked_until = None
        await self.session.commit()

    async def set_verification_token(self, user: User, token_hash: str) -> None:
        user.verification_token_hash = token_hash
        await self.session.commit()

    async def verify_email(self, user: User) -> None:
        user.is_email_verified = True
        user.verification_token_hash = None
        await self.session.commit()

    async def get_by_verification_token_hash(self, token_hash: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.verification_token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def set_password_reset(
        self,
        user: User,
        *,
        token_hash: str,
        expires_at: datetime,
    ) -> None:
        user.password_reset_token_hash = token_hash
        user.password_reset_expires_at = expires_at
        await self.session.commit()

    async def get_by_password_reset_token_hash(self, token_hash: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.password_reset_token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def list_users(
        self,
        *,
        page: int,
        page_size: int,
        role: str | None = None,
        search: str | None = None,
    ) -> tuple[list[User], int]:
        conditions = [User.is_deleted.is_(False)]
        if role:
            conditions.append(User.role == role)
        if search and search.strip():
            pattern = f"%{search.strip()}%"
            conditions.append(
                or_(
                    User.full_name.ilike(pattern),
                    User.email.ilike(pattern),
                )
            )
        total = int(
            (
                await self.session.execute(
                    select(func.count(User.id)).where(*conditions)
                )
            ).scalar_one()
        )
        result = await self.session.execute(
            select(User)
            .where(*conditions)
            .order_by(User.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def update_managed_user(
        self,
        user: User,
        *,
        email: str | None = None,
        full_name: str | None = None,
        hashed_password: str | None = None,
    ) -> User:
        if email is not None:
            user.email = email.strip().lower()
        if full_name is not None:
            user.full_name = full_name.strip()
        if hashed_password is not None:
            user.hashed_password = hashed_password
            user.token_version += 1
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def set_role(self, user: User, role: str) -> User:
        user.role = role
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def set_status(self, user: User, is_active: bool) -> User:
        user.is_active = is_active
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def soft_delete(self, user: User) -> User:
        user.is_deleted = True
        user.is_active = False
        user.token_version += 1
        user.verification_token_hash = None
        user.password_reset_token_hash = None
        user.password_reset_expires_at = None
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def count_users(self) -> int:
        return int(
            (
                await self.session.execute(
                    select(func.count(User.id)).where(User.is_deleted.is_(False))
                )
            ).scalar_one()
        )
