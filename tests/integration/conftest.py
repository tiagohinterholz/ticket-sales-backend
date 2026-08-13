from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401 — populates Base.metadata with every table
from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app as fastapi_app

engine = create_engine(settings.DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def _create_schema() -> None:
    # Tables are created once per test session and left in place (not dropped):
    # Seat/Ticket have a circular FK (seat.current_ticket_id <-> ticket.seat_id)
    # that SQLAlchemy's metadata.drop_all cannot order without explicit
    # use_alter naming on the constraints, which is a model-level concern
    # outside this task's scope. create_all is idempotent (checkfirst=True by
    # default), so re-running the suite against the same DB is safe.
    Base.metadata.create_all(engine)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def _override_get_db() -> Generator[Session, None, None]:
        yield db_session

    fastapi_app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(fastapi_app)
    finally:
        fastapi_app.dependency_overrides.pop(get_db, None)
