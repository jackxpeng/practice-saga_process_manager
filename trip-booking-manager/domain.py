from dataclasses import dataclass, field
import uuid
from typing import Dict, Any, Optional, List
import datetime

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
    status: str = "Initialized"
    current_route: Optional[Dict[str, Any]] = None
    rejected_routes: List[str] = field(default_factory=list)
    flight_confirmation: Optional[str] = None
    
    def handle_initialization(self) -> Optional[OutboxEvent]:
        if self.status != "Initialized":
            return None # Idempotency
            
        self.status = "Routing"
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
        
    def handle_route_generated(self, route: Dict[str, Any]) -> Optional[OutboxEvent]:
        if self.status != "Routing":
            return None # Idempotency
            
        self.status = "AwaitingApproval"
        self.current_route = route
        return OutboxEvent(
            aggregate_id=self.id,
            event_type="RequestEmployeeApprovalCommand",
            payload={
                "bookingId": str(self.id),
                "travelerId": self.traveler_id,
                "proposedRoute": route
            }
        )
        
    def handle_approval(self, approved: bool) -> Optional[OutboxEvent]:
        if self.status != "AwaitingApproval":
            return None # Idempotency
            
        if approved:
            self.status = "BookingFlights"
            return OutboxEvent(
                aggregate_id=self.id,
                event_type="BookFlightCommand",
                payload={
                    "bookingId": str(self.id),
                    "travelerId": self.traveler_id,
                    "routeId": self.current_route["routeId"]
                }
            )
        else:
            self.status = "Routing"
            rejected_route_id = self.current_route.get("routeId")
            
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
        if self.status != "BookingFlights":
            return None # Idempotency
            
        self.status = "BookingHotels"
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
        if self.status != "BookingHotels":
            return # Idempotency
        self.status = "Completed"
        
    def handle_hotel_failed(self, reason: str) -> Optional[OutboxEvent]:
        if self.status != "BookingHotels":
            return None # Idempotency
            
        self.status = "Compensating"
        return OutboxEvent(
            aggregate_id=self.id,
            event_type="CancelFlightCommand",
            payload={
                "bookingId": str(self.id),
                "flightConfirmation": self.flight_confirmation
            }
        )
