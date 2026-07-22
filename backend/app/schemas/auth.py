from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, min_length=2, max_length=120)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str | None
    role: str
    is_active: bool
    is_email_verified: bool
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=20)


class TokenActionResponse(BaseModel):
    message: str
    dev_token: str | None = None


class EmailActionRequest(BaseModel):
    email: EmailStr


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=20, max_length=300)


class PasswordResetRequest(BaseModel):
    token: str = Field(min_length=20, max_length=300)
    new_password: str = Field(min_length=8, max_length=128)


class PermissionsResponse(BaseModel):
    role: str
    permissions: list[str]


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class UserRoleUpdate(BaseModel):
    role: str = Field(pattern=r"^(customer|support|admin)$")


class UserStatusUpdate(BaseModel):
    is_active: bool


class SupportUserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=120)
    is_active: bool = True


class SupportUserUpdate(BaseModel):
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)
    full_name: str | None = Field(default=None, min_length=2, max_length=120)


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
