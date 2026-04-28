from dataclasses import dataclass, field
import uuid
from typing import Dict, Any, Optional, List

@dataclass
class ProcessState:
    destination: str
    traveler_id: str
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    status: str = "Initialized"
    current_route: Optional[Dict[str, Any]] = None
    rejected_routes: List[str] = field(default_factory=list)
    flight_confirmation: Optional[str] = None

@dataclass
class OutboxEvent:
    aggregate_id: uuid.UUID
    event_type: str
    payload: Dict[str, Any]
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    published: bool = False

class ProcessManagerDomain:
    @staticmethod
    def handle_initialization(state: ProcessState) -> Dict[str, Any]:
        state.status = "Routing"
        return {
            "event_type": "CalculateRouteCommand",
            "payload": {
                "bookingId": str(state.id),
                "destination": state.destination,
                "travelerId": state.traveler_id,
                "rejectedRoutes": state.rejected_routes or []
            }
        }
    
    @staticmethod
    def handle_route_generated(state: ProcessState, route: Dict[str, Any]) -> Dict[str, Any]:
        state.status = "AwaitingApproval"
        state.current_route = route
        return {
            "event_type": "RequestEmployeeApprovalCommand",
            "payload": {
                "bookingId": str(state.id),
                "travelerId": state.traveler_id,
                "proposedRoute": route
            }
        }
        
    @staticmethod
    def handle_approval(state: ProcessState, approved: bool) -> Optional[Dict[str, Any]]:
        if approved:
            state.status = "BookingFlights"
            return {
                "event_type": "BookFlightCommand",
                "payload": {
                    "bookingId": str(state.id),
                    "travelerId": state.traveler_id,
                    "routeId": state.current_route["routeId"]
                }
            }
        else:
            state.status = "Routing"
            rejected_route_id = state.current_route.get("routeId")
            
            # Since ProcessState is now a pure dataclass, we don't need to worry about SQLAlchemy JSONB mutation tracking here!
            if not state.rejected_routes:
                state.rejected_routes = []
                
            if rejected_route_id:
                state.rejected_routes.append(rejected_route_id)
            state.current_route = None
            
            return {
                "event_type": "CalculateRouteCommand",
                "payload": {
                    "bookingId": str(state.id),
                    "destination": state.destination,
                    "travelerId": state.traveler_id,
                    "rejectedRoutes": state.rejected_routes
                }
            }
            
    @staticmethod
    def handle_flight_booked(state: ProcessState, flight_confirmation: str) -> Dict[str, Any]:
        state.status = "BookingHotels"
        state.flight_confirmation = flight_confirmation
        return {
            "event_type": "BookHotelCommand",
            "payload": {
                "bookingId": str(state.id),
                "destination": state.destination
            }
        }
        
    @staticmethod
    def handle_hotel_booked(state: ProcessState, hotel_confirmation: str) -> None:
        state.status = "Completed"
        
    @staticmethod
    def handle_hotel_failed(state: ProcessState, reason: str) -> Dict[str, Any]:
        state.status = "Compensating"
        return {
            "event_type": "CancelFlightCommand",
            "payload": {
                "bookingId": str(state.id),
                "flightConfirmation": state.flight_confirmation
            }
        }
