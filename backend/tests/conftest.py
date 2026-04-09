"""
Shared pytest fixtures for the SQL Optimizer backend test suite.

Fixtures here are available to all test modules without explicit imports.
Heavy infrastructure (database, MinIO, Celery) is mocked at module level so
unit tests run completely offline — no Docker required.
"""
from __future__ import annotations

import io
import uuid
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.main import app
from app.api.v1.auth import get_current_user
from app.db.session import get_db


# ── Auth & DB dependency fixtures ────────────────────────────────────────────

@pytest.fixture
def mock_user() -> MagicMock:
    """
    Realistic fake User ORM instance for dependency injection in endpoint tests.
    All attributes that appear in UserResponse are explicitly set so Pydantic
    model_validate() succeeds without hitting a real database.
    """
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "alice@example.com"
    user.full_name = "Alice Test"
    user.created_at = datetime.now(timezone.utc)
    return user


@pytest.fixture
def mock_db() -> AsyncMock:
    """
    Fresh async DB session mock.

    * add()     is synchronous in SQLAlchemy → MagicMock
    * execute() returns a plain MagicMock so callers can chain .scalars(),
      .first(), .all() synchronously without hitting AsyncMock's auto-coroutine
      wrapping on child attributes.
    * refresh() side_effect simulates the DB populating server_default columns
      (id, created_at) so Pydantic model_validate() succeeds without a real DB.
    """
    db = AsyncMock()
    db.add = MagicMock()

    # Return a plain MagicMock so result.scalars(), result.first(), result.all()
    # are regular callables — not coroutines.
    db.execute = AsyncMock(return_value=MagicMock())

    async def _refresh_sets_server_defaults(obj: object) -> None:
        if not getattr(obj, "id", None):
            obj.id = uuid.uuid4()
        if not getattr(obj, "created_at", None):
            obj.created_at = datetime.now(timezone.utc)

    db.refresh.side_effect = _refresh_sets_server_defaults
    return db


@pytest.fixture
def auth_override(mock_user: MagicMock):
    """
    Override get_current_user for the duration of the test.

    Usage::

        async def test_something(self, auth_override, mock_user):
            ...

    The override is removed automatically after the test via the yield teardown.
    """
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield mock_user
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def db_override(mock_db: AsyncMock):
    """
    Override get_db for the duration of the test.

    Yields the same mock_db instance so tests can introspect calls:

        assert db_override.commit.called
    """
    async def _override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = _override_get_db
    yield mock_db
    app.dependency_overrides.pop(get_db, None)

# ── FastAPI test client ───────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture
def sample_ddl() -> str:
    """Minimal, well-formed DDL used across multiple parser tests."""
    return """
    CREATE TABLE users (
        id SERIAL PRIMARY KEY,
        email VARCHAR(255) NOT NULL UNIQUE,
        full_name VARCHAR(100),
        created_at TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE orders (
        id SERIAL PRIMARY KEY,
        user_id INT NOT NULL REFERENCES users(id),
        total DECIMAL(10, 2),
        status VARCHAR(50) DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE order_items (
        id SERIAL PRIMARY KEY,
        order_id INT NOT NULL REFERENCES orders(id),
        product_id INT NOT NULL REFERENCES products(id),
        quantity INT NOT NULL,
        unit_price DECIMAL(10, 2)
    );
    """


@pytest.fixture
def ddl_with_data_statements(sample_ddl: str) -> bytes:
    """DDL with forbidden INSERT / COPY / VALUES mixed in — used for sanitise tests."""
    dirty = (
        sample_ddl
        + "\n"
        + "INSERT INTO users (email) VALUES ('alice@example.com');\n"
        + "COPY users FROM '/tmp/users.csv';\n"
        + "VALUES (1, 2, 3);\n"
        + "-- safe comment\n"
        + "CREATE INDEX idx_orders_user ON orders(user_id);\n"
    )
    return dirty.encode("utf-8")


@pytest.fixture
def broken_ddl() -> str:
    """DDL where one table is syntactically broken — tests partial-success path."""
    return """
    CREATE TABLE products (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        price DECIMAL(10, 2)
    );

    CREATE TABLE @@BROKEN (
        this is not valid sql %%%
    );

    CREATE TABLE categories (
        id SERIAL PRIMARY KEY,
        label VARCHAR(100)
    );
    """
