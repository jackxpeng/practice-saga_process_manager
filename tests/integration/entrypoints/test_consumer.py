import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import trip_booking.entrypoints.consumer as consumer
from trip_booking.infrastructure.database import metadata, start_mappers
from trip_booking.domain.domain import ProcessState, OutboxEvent, TripStatus, CommandType

class FakeMethod:
    def __init__(self, routing_key, delivery_tag):
        self.routing_key = routing_key
        self.delivery_tag = delivery_tag

class FakeChannel:
    def __init__(self):
        self.acked = []
        self.nacked = []

    def basic_ack(self, delivery_tag):
        self.acked.append(delivery_tag)
        
    def basic_nack(self, delivery_tag, requeue=False):
        self.nacked.append((delivery_tag, requeue))

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

@pytest.mark.integration
def test_consumer_route_generated(db_session, TestingSessionLocal):
    consumer.SessionLocal = TestingSessionLocal
    
    state = ProcessState(destination="Paris", traveler_id="emp-789")
    state.status = TripStatus.ROUTING
    db_session.add(state)
    db_session.commit()
    booking_id = str(state.id)
    
    ch = FakeChannel()
    method = FakeMethod(routing_key="RouteGeneratedEvent", delivery_tag=1)
    properties = object()
    
    body = json.dumps({
        "bookingId": booking_id,
        "route": {"routeId": "r-123", "airline": "Delta", "cost": 450.0}
    })
    
    consumer.callback(ch, method, properties, body)
    
    assert ch.acked == [1]
    
    db_session.expire_all()
    import uuid
    booking_uuid = uuid.UUID(booking_id)
    updated_state = db_session.query(ProcessState).filter(ProcessState.id == booking_uuid).first()
    assert updated_state.status == TripStatus.AWAITING_APPROVAL
    assert updated_state.current_route.route_id == "r-123"
    
    outbox_evt = db_session.query(OutboxEvent).filter(
        OutboxEvent.aggregate_id == booking_uuid,
        OutboxEvent.event_type == CommandType.REQUEST_EMPLOYEE_APPROVAL
    ).first()
    assert outbox_evt is not None
