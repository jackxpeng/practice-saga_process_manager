import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from trip_booking.entrypoints.main import app, get_db
from trip_booking.infrastructure.database import metadata, start_mappers
from trip_booking.domain.domain import ProcessState, OutboxEvent, TripStatus, CommandType

@pytest.fixture(scope="module")
def sqlite_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    start_mappers()
    metadata.create_all(engine)
    return engine

@pytest.fixture
def TestingSessionLocal(sqlite_engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=sqlite_engine)

@pytest.fixture
def db_session(TestingSessionLocal):
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()

@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()

@pytest.mark.integration
def test_api_create_trip(client, db_session):
    response = client.post("/trips", json={"destination": "Seattle", "travelerId": "emp-123"})
    assert response.status_code == 200
    
    data = response.json()
    assert "bookingId" in data
    
    db_session.expire_all()
    import uuid
    booking_uuid = uuid.UUID(data["bookingId"])
    state = db_session.query(ProcessState).filter(ProcessState.id == booking_uuid).first()
    assert state is not None
    assert state.status == TripStatus.ROUTING
    
    outbox_evt = db_session.query(OutboxEvent).filter(OutboxEvent.aggregate_id == state.id).first()
    assert outbox_evt is not None
    assert outbox_evt.event_type == CommandType.CALCULATE_ROUTE
    assert outbox_evt.payload["destination"] == "Seattle"
