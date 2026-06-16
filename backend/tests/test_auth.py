import pytest
from sqlalchemy import select
from app.models.user import User
from app.services.auth import get_or_create_user

@pytest.mark.asyncio
async def test_get_or_create_user(db_session):
    # Test creating a new user
    email = "new_user@example.com"
    role = "Employee"
    department = "HR"
    
    user = await get_or_create_user(db_session, email=email, role=role, department=department)
    assert user.id is not None
    assert user.email == email
    assert user.role == role
    assert user.department == department
    
    # Test getting the existing user (should not create duplicate)
    user2 = await get_or_create_user(db_session, email=email, role="Manager", department="Finance")
    assert user2.id == user.id
    # Role and department should be updated for existing user in get_or_create_user implementation
    assert user2.role == "Manager"
    assert user2.department == "Finance"

@pytest.mark.asyncio
async def test_me_endpoint(async_client):
    response = await async_client.get("/api/me")
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["role"] == "Admin"
    assert data["department"] == "Engineering"
