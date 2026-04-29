import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from trip_booking.infrastructure.sql_repository import SqlAlchemyTripRepository
from trip_booking.infrastructure.database import metadata, start_mappers
from trip_booking.domain.domain import ProcessState, OutboxEvent, TripStatus

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
def test_save_with_outbox(db_session):
    repo = SqlAlchemyTripRepository(session=db_session)
    
    state = ProcessState(destination="Berlin", traveler_id="emp-999")
    outbox_event = OutboxEvent(
        aggregate_id=state.id,
        event_type="TestEvent",
        payload={"foo": "bar"}
    )
    
    repo.save_with_outbox(state, outbox_event)
    
    db_session.expire_all()
    
    saved_state = db_session.query(ProcessState).filter(ProcessState.id == state.id).first()
    assert saved_state is not None
    assert saved_state.destination == "Berlin"
    
    saved_event = db_session.query(OutboxEvent).filter(OutboxEvent.aggregate_id == state.id).first()
    assert saved_event is not None
    assert saved_event.event_type == "TestEvent"
    assert saved_event.payload == {"foo": "bar"}
