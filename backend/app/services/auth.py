from fastapi import Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def get_or_create_user(
    session: AsyncSession,
    email: str = Header(default="admin@example.com", alias="X-User-Email"),
    role: str = Header(default="Admin", alias="X-User-Role"),
    department: str = Header(default="Engineering", alias="X-User-Department"),
) -> User:
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user:
        user.role = role
        user.department = department
        await session.commit()
        await session.refresh(user)
        return user

    user = User(email=email, role=role, department=department)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user
