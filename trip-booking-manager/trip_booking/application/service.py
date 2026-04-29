import uuid
from typing import Any
from trip_booking.domain.domain import ProcessState, OutboxEvent
from trip_booking.application.ports import TripRepository

class TripApplicationService:
    def __init__(self, repository: TripRepository):
        self.repository = repository

    def initialize_trip(self, destination: str, traveler_id: str) -> str:
        state = ProcessState(destination=destination, traveler_id=traveler_id)
        outbox_event = state.handle_initialization()
        if outbox_event:
            self.repository.save_with_outbox(state, outbox_event)
        else:
            self.repository.save(state)
        return str(state.id)

    def approve_trip(self, booking_id: str, approved: bool) -> None:
        booking_uuid = uuid.UUID(booking_id)
        state = self.repository.get_by_id(booking_uuid)
        if not state:
            raise ValueError(f"Trip not found: {booking_id}")
            
        outbox_evt = state.handle_approval(approved)
        if outbox_evt:
            self.repository.save_with_outbox(state, outbox_evt)
        else:
            self.repository.save(state)

    def process_external_event(self, event_type: str, event: dict[str, Any]) -> None:
        booking_id = event.get("bookingId")
        if not booking_id:
            raise ValueError("No bookingId in event payload")

        booking_uuid = uuid.UUID(booking_id)
        state = self.repository.get_by_id(booking_uuid)
        if not state:
            raise ValueError(f"State not found for bookingId: {booking_id}")
            
        outbox_evt = None
        if event_type == "RouteGeneratedEvent":
            outbox_evt = state.handle_route_generated(event.get("route", {}))
        elif event_type == "FlightBookedEvent":
            outbox_evt = state.handle_flight_booked(event.get("flightConfirmation", ""))
        elif event_type == "FlightCancelledEvent":
            state.handle_flight_cancelled()
        elif event_type == "HotelBookedEvent":
            state.handle_hotel_booked(event.get("hotelConfirmation", ""))
        elif event_type == "HotelFailedEvent":
            outbox_evt = state.handle_hotel_failed(event.get("reason", ""))
            
        if outbox_evt:
            self.repository.save_with_outbox(state, outbox_evt)
        else:
            self.repository.save(state)

    def get_trip(self, booking_id: str) -> ProcessState | None:
        booking_uuid = uuid.UUID(booking_id)
        return self.repository.get_by_id(booking_uuid)
