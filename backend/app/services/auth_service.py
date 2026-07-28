import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, UnauthorizedError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginRequest, TokenResponse, UserCreate


class AuthService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = UserRepository(session)

    async def register(self, data: UserCreate) -> User:
        if await self.repo.get_by_username(data.username):
            raise ConflictError("Username already exists")
        if await self.repo.get_by_email(data.email):
            raise ConflictError("Email already registered")

        user = User(
            username=data.username,
            email=data.email,
            hashed_password=hash_password(data.password),
            role=data.role.value,
        )
        return await self.repo.create(user)

    async def login(self, data: LoginRequest) -> TokenResponse:
        user = await self.repo.get_by_username(data.username)
        if not user or not verify_password(data.password, user.hashed_password):
            raise UnauthorizedError("Invalid username or password")
        if not user.is_active:
            raise UnauthorizedError("User is disabled")

        access = create_access_token(str(user.id), user.role)
        refresh = create_refresh_token(str(user.id), user.role)
        return TokenResponse(access_token=access, refresh_token=refresh)

    async def refresh(self, refresh_token: str) -> TokenResponse:
        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise UnauthorizedError("Invalid refresh token")

        try:
            user_id = uuid.UUID(payload["sub"])
        except (ValueError, KeyError, TypeError):
            raise UnauthorizedError("Invalid refresh token")

        user = await self.repo.get(user_id)
        if not user or not user.is_active:
            raise UnauthorizedError("User not found or disabled")

        access = create_access_token(str(user.id), user.role)
        new_refresh = create_refresh_token(str(user.id), user.role)
        return TokenResponse(access_token=access, refresh_token=new_refresh)
