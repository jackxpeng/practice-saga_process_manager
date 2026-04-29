import pytest
import uuid
from typing import Optional
from trip_booking.application.service import TripApplicationService
from trip_booking.application.ports import TripRepository
from trip_booking.domain.domain import ProcessState, OutboxEvent, TripStatus, CommandType

class FakeTripRepository(TripRepository):
    def __init__(self):
        self.states = {}
        self.outbox_events = []

    def get_by_id(self, booking_id: uuid.UUID) -> Optional[ProcessState]:
        return self.states.get(booking_id)

    def save(self, state: ProcessState) -> None:
        self.states[state.id] = state

    def save_with_outbox(self, state: ProcessState, outbox_event: OutboxEvent) -> None:
        self.states[state.id] = state
        self.outbox_events.append(outbox_event)

@pytest.mark.unit
def test_approve_trip():
    repo = FakeTripRepository()
    service = TripApplicationService(repository=repo)
    
    state = ProcessState(destination="Tokyo", traveler_id="emp-xyz")
    state.status = TripStatus.AWAITING_APPROVAL
    repo.states[state.id] = state
    
    service.approve_trip(str(state.id), approved=True)
    
    updated_state = repo.states[state.id]
    assert updated_state.status == TripStatus.BOOKING_FLIGHTS
    
    assert len(repo.outbox_events) == 1
    assert repo.outbox_events[0].event_type == CommandType.BOOK_FLIGHT
    assert repo.outbox_events[0].aggregate_id == state.id
