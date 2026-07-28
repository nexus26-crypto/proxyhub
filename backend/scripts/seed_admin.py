import asyncio
import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.database import AsyncSessionLocal  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models.enums import UserRole  # noqa: E402
from app.models.user import User  # noqa: E402
from app.repositories.user_repository import UserRepository  # noqa: E402


async def seed_admin():
    username = os.getenv("ADMIN_USERNAME", "admin")
    email = os.getenv("ADMIN_EMAIL", "admin@proxyhub.local")
    password = os.getenv("ADMIN_PASSWORD", "admin123")

    async with AsyncSessionLocal() as session:
        repo = UserRepository(session)
        existing = await repo.get_by_username(username)
        if existing:
            print(f"Usuario admin '{username}' ja existe. Nada a fazer.")
            return

        admin = User(
            username=username,
            email=email,
            hashed_password=hash_password(password),
            role=UserRole.ADMIN.value,
        )
        await repo.create(admin)
        print(f"Usuario admin criado: {username} / senha: {password}")


if __name__ == "__main__":
    asyncio.run(seed_admin())
