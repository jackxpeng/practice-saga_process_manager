import abc
import uuid
from typing import Optional
from trip_booking.domain.domain import ProcessState, OutboxEvent

class TripRepository(abc.ABC):
    @abc.abstractmethod
    def get_by_id(self, booking_id: uuid.UUID) -> Optional[ProcessState]:
        pass

    @abc.abstractmethod
    def save(self, state: ProcessState) -> None:
        pass

    @abc.abstractmethod
    def save_with_outbox(self, state: ProcessState, outbox_event: OutboxEvent) -> None:
        pass
