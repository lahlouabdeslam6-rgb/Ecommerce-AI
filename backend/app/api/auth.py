from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    ROLE_PERMISSIONS,
    get_current_user,
    require_roles,
)
from app.db.sqlite import get_sqlite_session
from app.models.user import User
from app.schemas.auth import (
    PasswordChange,
    EmailActionRequest,
    PasswordResetRequest,
    PermissionsResponse,
    ProfileUpdate,
    RefreshTokenRequest,
    TokenActionResponse,
    TokenResponse,
    UserRegister,
    UserResponse,
    VerifyEmailRequest,
)
from app.services.auth import AuthService


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    data: UserRegister,
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> User:
    return await AuthService(session).register(data)


@router.post("/login", response_model=TokenResponse)
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> TokenResponse:
    _, access_token, refresh_token = await AuthService(session).authenticate(
        form.username, form.password
    )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    data: RefreshTokenRequest,
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> TokenResponse:
    access_token, new_refresh_token = await AuthService(session).refresh(
        data.refresh_token
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
    )


@router.post("/request-email-verification", response_model=TokenActionResponse)
async def request_email_verification(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> TokenActionResponse:
    token = await AuthService(session).request_email_verification(current_user)
    return TokenActionResponse(
        message="Email already verified" if token is None else "Verification created",
        dev_token=token if settings.environment == "development" else None,
    )


@router.post("/verify-email", response_model=TokenActionResponse)
async def verify_email(
    data: VerifyEmailRequest,
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> TokenActionResponse:
    await AuthService(session).verify_email(data.token)
    return TokenActionResponse(message="Email verified")


@router.post("/forgot-password", response_model=TokenActionResponse)
async def forgot_password(
    data: EmailActionRequest,
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> TokenActionResponse:
    token = await AuthService(session).forgot_password(str(data.email))
    return TokenActionResponse(
        message="If the account exists, a reset request was created",
        dev_token=token if settings.environment == "development" else None,
    )


@router.post("/reset-password", response_model=TokenActionResponse)
async def reset_password(
    data: PasswordResetRequest,
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> TokenActionResponse:
    await AuthService(session).reset_password(data.token, data.new_password)
    return TokenActionResponse(message="Password updated")


@router.get("/me", response_model=UserResponse)
async def me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_me(
    data: ProfileUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> User:
    return await AuthService(session).update_profile(current_user, data.full_name)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    data: PasswordChange,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_sqlite_session)],
) -> None:
    await AuthService(session).change_password(
        current_user,
        data.current_password,
        data.new_password,
    )


@router.get("/permissions", response_model=PermissionsResponse)
async def permissions(
    current_user: Annotated[User, Depends(get_current_user)],
) -> PermissionsResponse:
    permissions_for_role = sorted(ROLE_PERMISSIONS.get(current_user.role, set()))
    return PermissionsResponse(
        role=current_user.role,
        permissions=permissions_for_role,
    )


@router.get("/admin-check")
async def admin_check(
    _: Annotated[User, Depends(require_roles("admin"))],
) -> dict[str, str]:
    return {"message": "Admin access granted"}
