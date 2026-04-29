import uuid
from typing import Optional
from sqlalchemy.orm import Session
from trip_booking.domain.domain import ProcessState, OutboxEvent
from trip_booking.application.ports import TripRepository

class SqlAlchemyTripRepository(TripRepository):
    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, booking_id: uuid.UUID) -> Optional[ProcessState]:
        return self.session.query(ProcessState).filter(ProcessState.id == booking_id).first()

    def save(self, state: ProcessState) -> None:
        self.session.add(state)
        self.session.commit()

    def save_with_outbox(self, state: ProcessState, outbox_event: OutboxEvent) -> None:
        self.session.add(state)
        self.session.add(outbox_event)
        self.session.commit()
