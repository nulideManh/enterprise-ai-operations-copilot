import asyncio
import socket
from collections.abc import AsyncIterator
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_session
from app.main import app, current_user
from app.models import User

settings = get_settings()

# Helper to check if a port is open
def is_port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False

# Determine test database URL
def get_test_db_url() -> str:
    url = settings.database_url
    # If running outside docker-compose network, replace db host with localhost if port 5432 is open on localhost
    if "@db:" in url and is_port_open("localhost", 5432):
        url = url.replace("@db:", "@localhost:")
    
    # We will use 'copilot_test' as the database name for testing
    if url.endswith("/copilot"):
        url = url.removesuffix("/copilot") + "/copilot_test"
    else:
        # Fallback split
        parts = url.rsplit("/", 1)
        url = parts[0] + "/copilot_test"
    return url

TEST_DATABASE_URL = get_test_db_url()

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_db():
    # To create the test database, we first connect to 'postgres' default database
    admin_url = TEST_DATABASE_URL.rsplit("/", 1)[0] + "/postgres"
    admin_engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    
    # Drop and recreate test database
    async with admin_engine.connect() as conn:
        await conn.execute(text("DROP DATABASE IF EXISTS copilot_test WITH (FORCE)"))
        await conn.execute(text("CREATE DATABASE copilot_test"))
    await admin_engine.dispose()
    
    # Connect to the test database and setup tables & extensions
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    
    yield
    
    # Clean up test database
    await engine.dispose()
    admin_engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    async with admin_engine.connect() as conn:
        await conn.execute(text("DROP DATABASE IF EXISTS copilot_test WITH (FORCE)"))
    await admin_engine.dispose()

@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(TEST_DATABASE_URL)
    AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with AsyncSessionLocal() as session:
        yield session
        await session.rollback()
    
    await engine.dispose()

@pytest_asyncio.fixture(autouse=True)
async def clean_database(db_session: AsyncSession):
    # Truncate all tables to prevent cross-test leakage (since service code commits directly)
    for table in reversed(Base.metadata.sorted_tables):
        await db_session.execute(text(f"TRUNCATE TABLE {table.name} CASCADE"))
    await db_session.commit()

@pytest_asyncio.fixture
async def async_client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    # Override database session dependency
    async def override_get_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    
    # Override current_user to default to a test user
    async def override_current_user() -> User:
        # Check if user already exists
        from sqlalchemy import select
        stmt = select(User).where(User.email == "test@example.com")
        user = (await db_session.execute(stmt)).scalar_one_or_none()
        if not user:
            user = User(
                email="test@example.com",
                role="Admin",
                department="Engineering"
            )
            db_session.add(user)
            await db_session.commit()
            await db_session.refresh(user)
        return user

    app.dependency_overrides[current_user] = override_current_user
    
    # We use transport instead of base_url directly to make async requests work correctly
    async with AsyncClient(
        transport=ASGITransport(app=app), 
        base_url="http://testserver"
    ) as client:
        yield client
        
    app.dependency_overrides.clear()
