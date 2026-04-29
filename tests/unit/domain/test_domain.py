import pytest
from trip_booking.domain.domain import ProcessState, TripStatus, CommandType

@pytest.mark.unit
def test_happy_path():
    state = ProcessState(destination="Seattle", traveler_id="emp-123")
    assert state.status == TripStatus.INITIALIZED

    # 1. Initialization
    evt = state.handle_initialization()
    assert state.status == TripStatus.ROUTING
    assert evt is not None
    assert evt.event_type == CommandType.CALCULATE_ROUTE
    assert evt.payload["destination"] == "Seattle"

    # 2. Route Generated
    route_data = {"routeId": "route-001", "airline": "Delta", "cost": 350.0}
    evt = state.handle_route_generated(route_data)
    assert state.status == TripStatus.AWAITING_APPROVAL
    assert evt is not None
    assert evt.event_type == CommandType.REQUEST_EMPLOYEE_APPROVAL
    assert evt.payload["proposedRoute"]["routeId"] == "route-001"

    # 3. Employee Approves
    evt = state.handle_approval(True)
    assert state.status == TripStatus.BOOKING_FLIGHTS
    assert evt is not None
    assert evt.event_type == CommandType.BOOK_FLIGHT
    assert evt.payload["routeId"] == "route-001"

    # 4. Flight Booked
    evt = state.handle_flight_booked("FLIGHT-CONF-ABC")
    assert state.status == TripStatus.BOOKING_HOTELS
    assert evt is not None
    assert evt.event_type == CommandType.BOOK_HOTEL

    # 5. Hotel Booked
    evt = state.handle_hotel_booked("HOTEL-CONF-XYZ")
    assert state.status == TripStatus.COMPLETED
    assert evt is None


@pytest.mark.unit
def test_rejection_loop():
    state = ProcessState(destination="New York", traveler_id="emp-456")
    state.handle_initialization()

    route_data = {"routeId": "bad-route-99", "airline": "Spirit", "cost": 50.0}
    state.handle_route_generated(route_data)

    # Reject the route
    evt = state.handle_approval(False)

    assert state.status == TripStatus.ROUTING
    assert "bad-route-99" in state.rejected_routes
    assert evt is not None
    assert evt.event_type == CommandType.CALCULATE_ROUTE
    assert "bad-route-99" in evt.payload["rejectedRoutes"]


@pytest.mark.unit
def test_idempotency():
    state = ProcessState(destination="London", traveler_id="emp-789")
    state.handle_initialization()

    route_data = {"routeId": "route-111", "airline": "BA", "cost": 800.0}

    # First call - should transition and return event
    evt1 = state.handle_route_generated(route_data)
    assert state.status == TripStatus.AWAITING_APPROVAL
    assert evt1 is not None

    # Second call - should be ignored (idempotent)
    evt2 = state.handle_route_generated(route_data)
    assert state.status == TripStatus.AWAITING_APPROVAL
    assert evt2 is None
