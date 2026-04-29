import sys
import os
import json
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure imports work from trip-booking-manager
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../trip-booking-manager')))

from trip_booking.entrypoints.main import app, get_db
import trip_booking.entrypoints.consumer as consumer
from trip_booking.infrastructure.database import metadata, start_mappers
from trip_booking.domain.domain import ProcessState, OutboxEvent, TripStatus

from sqlalchemy.pool import StaticPool

@pytest.fixture(scope="module")
def sqlite_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    start_mappers()
    # Create tables in the in-memory database
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

def test_api_create_trip(client, db_session):
    response = client.post("/trips", json={"destination": "Seattle", "travelerId": "emp-123"})
    assert response.status_code == 200
    
    data = response.json()
    assert "bookingId" in data
    
    # Verify DB State
    db_session.expire_all()
    import uuid
    booking_uuid = uuid.UUID(data["bookingId"])
    state = db_session.query(ProcessState).filter(ProcessState.id == booking_uuid).first()
    assert state is not None
    assert state.status == TripStatus.ROUTING
    
    outbox_evt = db_session.query(OutboxEvent).filter(OutboxEvent.aggregate_id == state.id).first()
    assert outbox_evt is not None
    assert outbox_evt.event_type == "CalculateRouteCommand"
    assert outbox_evt.payload["destination"] == "Seattle"

def test_consumer_route_generated(db_session, TestingSessionLocal):
    # Patch the consumer to use our sqlite sessionmaker
    consumer.SessionLocal = TestingSessionLocal
    
    # 1. Setup DB with a trip in ROUTING state
    state = ProcessState(destination="Paris", traveler_id="emp-789")
    state.status = TripStatus.ROUTING
    db_session.add(state)
    db_session.commit()
    booking_id = str(state.id)
    
    # 2. Mock RabbitMQ channel and method
    ch = MagicMock()
    method = MagicMock()
    method.routing_key = "RouteGeneratedEvent"
    method.delivery_tag = 1
    properties = MagicMock()
    
    # 3. Create Event Payload
    body = json.dumps({
        "bookingId": booking_id,
        "route": {"routeId": "r-123", "airline": "Delta", "cost": 450.0}
    })
    
    # 4. Invoke callback directly (No real RabbitMQ!)
    consumer.callback(ch, method, properties, body)
    
    # 5. Verify basic_ack was called
    ch.basic_ack.assert_called_once_with(delivery_tag=1)
    
    # 6. Verify Database was updated properly
    db_session.expire_all()
    import uuid
    booking_uuid = uuid.UUID(booking_id)
    updated_state = db_session.query(ProcessState).filter(ProcessState.id == booking_uuid).first()
    assert updated_state.status == TripStatus.AWAITING_APPROVAL
    assert updated_state.current_route.route_id == "r-123"
    
    # 7. Verify Outbox Event was appended
    outbox_evt = db_session.query(OutboxEvent).filter(
        OutboxEvent.aggregate_id == booking_uuid,
        OutboxEvent.event_type == "RequestEmployeeApprovalCommand"
    ).first()
    assert outbox_evt is not None
