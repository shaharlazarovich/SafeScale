import os
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://safescale_test:safescale_test@localhost:5433/safescale_test")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_SECURITY_TOKEN", "testing")
os.environ.setdefault("AWS_SESSION_TOKEN", "testing")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ENDPOINT_URL", "http://localhost:4567")
os.environ.setdefault("LOG_LEVEL", "DEBUG")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")
os.environ.setdefault("ENCRYPTION_KEY", "dGVzdGluZy1lbmNyeXB0aW9uLWtleS0xMjM0NTY3OA==")

from app.core.database import Base
from app.core.database import get_db as _get_db
from app.main import app


TEST_DATABASE_URL = os.environ["DATABASE_URL"]

engine_test = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
TestSessionLocal = sessionmaker(engine_test, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session", autouse=True)
async def setup_database():
    """Create all tables before the test session, drop them after."""
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine_test.dispose()


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional database session that rolls back after each test."""
    async with TestSessionLocal() as session:
        async with session.begin():
            yield session
            await session.rollback()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provide an async HTTP test client with a test database session."""

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[_get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def aws_credentials():
    """Return fake AWS credentials for moto / LocalStack."""
    return {
        "aws_access_key_id": "testing",
        "aws_secret_access_key": "testing",
        "region_name": "us-east-1",
    }


@pytest.fixture
def mock_aws(aws_credentials, monkeypatch):
    """Set up moto mocks for key AWS services used in the Auditor.

    Usage in a test:

        def test_something(mock_aws):
            with mock_aws["rds"]():
                client = boto3.client("rds", **mock_aws["credentials"])
                # ... test code
    """
    import moto

    return {
        "credentials": aws_credentials,
        "rds": moto.mock_aws,
        "ec2": moto.mock_aws,
        "elasticache": moto.mock_aws,
        "eks": moto.mock_aws,
        "ecs": moto.mock_aws,
        "elbv2": moto.mock_aws,
        "s3": moto.mock_aws,
        "cloudwatch": moto.mock_aws,
        "sts": moto.mock_aws,
    }
