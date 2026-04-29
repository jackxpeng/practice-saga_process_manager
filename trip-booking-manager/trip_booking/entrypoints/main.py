from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from trip_booking.infrastructure.database import SessionLocal, init_db
from trip_booking.infrastructure.sql_repository import SqlAlchemyTripRepository
from trip_booking.application.service import TripApplicationService

app = FastAPI()


class TripRequest(BaseModel):
    destination: str
    travelerId: str


class ApprovalRequest(BaseModel):
    approved: bool


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_service(db: Session = Depends(get_db)) -> TripApplicationService:
    repo = SqlAlchemyTripRepository(db)
    return TripApplicationService(repo)


@app.on_event("startup")
def on_startup():
    init_db()


@app.post("/trips")
def create_trip(
    req: TripRequest, service: TripApplicationService = Depends(get_service)
):
    booking_id = service.initialize_trip(req.destination, req.travelerId)
    state = service.get_trip(booking_id)
    return {"bookingId": booking_id, "status": state.status.value}


@app.get("/trips/{booking_id}")
def get_trip(booking_id: str, service: TripApplicationService = Depends(get_service)):
    try:
        state = service.get_trip(booking_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Trip not found")

    if not state:
        raise HTTPException(status_code=404, detail="Trip not found")

    route_dict = None
    if state.current_route:
        route_dict = {
            "routeId": state.current_route.route_id,
            "airline": state.current_route.airline,
            "cost": state.current_route.cost,
        }

    return {
        "bookingId": str(state.id),
        "status": state.status.value,
        "destination": state.destination,
        "current_route": route_dict,
        "rejected_routes": state.rejected_routes,
    }


@app.post("/trips/{booking_id}/approval")
def approve_trip(
    booking_id: str,
    req: ApprovalRequest,
    service: TripApplicationService = Depends(get_service),
):
    try:
        service.approve_trip(booking_id, req.approved)
        state = service.get_trip(booking_id)
        return {"status": state.status.value}
    except ValueError:
        raise HTTPException(status_code=404, detail="Trip not found")
