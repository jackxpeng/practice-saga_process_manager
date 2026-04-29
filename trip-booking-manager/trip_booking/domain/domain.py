from dataclasses import dataclass, field
import uuid
from typing import Dict, Any, Optional, List
import datetime
from enum import Enum

class TripStatus(str, Enum):
    INITIALIZED = "Initialized"
    ROUTING = "Routing"
    AWAITING_APPROVAL = "AwaitingApproval"
    BOOKING_FLIGHTS = "BookingFlights"
    BOOKING_HOTELS = "BookingHotels"
    COMPLETED = "Completed"
    COMPENSATING = "Compensating"

@dataclass(frozen=True)
class Route:
    route_id: str
    airline: str
    cost: float

@dataclass
class OutboxEvent:
    aggregate_id: uuid.UUID
    event_type: str
    payload: Dict[str, Any]
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    published: bool = False
    created_at: datetime.datetime = field(default_factory=datetime.datetime.utcnow)

@dataclass
class ProcessState:
    destination: str
    traveler_id: str
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    status: TripStatus = TripStatus.INITIALIZED
    current_route: Optional[Route] = None
    rejected_routes: List[str] = field(default_factory=list)
    flight_confirmation: Optional[str] = None
    
    def handle_initialization(self) -> Optional[OutboxEvent]:
        if self.status != TripStatus.INITIALIZED:
            return None # Idempotency
            
        self.status = TripStatus.ROUTING
        return OutboxEvent(
            aggregate_id=self.id,
            event_type="CalculateRouteCommand",
            payload={
                "bookingId": str(self.id),
                "destination": self.destination,
                "travelerId": self.traveler_id,
                "rejectedRoutes": self.rejected_routes or []
            }
        )
        
    def handle_route_generated(self, route_data: Dict[str, Any]) -> Optional[OutboxEvent]:
        if self.status != TripStatus.ROUTING:
            return None # Idempotency
            
        self.status = TripStatus.AWAITING_APPROVAL
        self.current_route = Route(
            route_id=route_data.get("routeId", ""),
            airline=route_data.get("airline", ""),
            cost=route_data.get("cost", 0.0)
        )
        return OutboxEvent(
            aggregate_id=self.id,
            event_type="RequestEmployeeApprovalCommand",
            payload={
                "bookingId": str(self.id),
                "travelerId": self.traveler_id,
                "proposedRoute": {
                    "routeId": self.current_route.route_id,
                    "airline": self.current_route.airline,
                    "cost": self.current_route.cost
                }
            }
        )
        
    def handle_approval(self, approved: bool) -> Optional[OutboxEvent]:
        if self.status != TripStatus.AWAITING_APPROVAL:
            return None # Idempotency
            
        if approved:
            self.status = TripStatus.BOOKING_FLIGHTS
            return OutboxEvent(
                aggregate_id=self.id,
                event_type="BookFlightCommand",
                payload={
                    "bookingId": str(self.id),
                    "travelerId": self.traveler_id,
                    "routeId": self.current_route.route_id if self.current_route else ""
                }
            )
        else:
            self.status = TripStatus.ROUTING
            rejected_route_id = self.current_route.route_id if self.current_route else None
            
            if not self.rejected_routes:
                self.rejected_routes = []
                
            if rejected_route_id:
                self.rejected_routes.append(rejected_route_id)
            self.current_route = None
            
            return OutboxEvent(
                aggregate_id=self.id,
                event_type="CalculateRouteCommand",
                payload={
                    "bookingId": str(self.id),
                    "destination": self.destination,
                    "travelerId": self.traveler_id,
                    "rejectedRoutes": self.rejected_routes
                }
            )
            
    def handle_flight_booked(self, flight_confirmation: str) -> Optional[OutboxEvent]:
        if self.status != TripStatus.BOOKING_FLIGHTS:
            return None # Idempotency
            
        self.status = TripStatus.BOOKING_HOTELS
        self.flight_confirmation = flight_confirmation
        return OutboxEvent(
            aggregate_id=self.id,
            event_type="BookHotelCommand",
            payload={
                "bookingId": str(self.id),
                "destination": self.destination
            }
        )
        
    def handle_hotel_booked(self, hotel_confirmation: str) -> None:
        if self.status != TripStatus.BOOKING_HOTELS:
            return # Idempotency
        self.status = TripStatus.COMPLETED
        
    def handle_hotel_failed(self, reason: str) -> Optional[OutboxEvent]:
        if self.status != TripStatus.BOOKING_HOTELS:
            return None # Idempotency
            
        self.status = TripStatus.COMPENSATING
        return OutboxEvent(
            aggregate_id=self.id,
            event_type="CancelFlightCommand",
            payload={
                "bookingId": str(self.id),
                "flightConfirmation": self.flight_confirmation
            }
        )
