from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import SessionLocal, init_db
from domain import ProcessState, OutboxEvent

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

@app.on_event("startup")
def on_startup():
    init_db()

@app.post("/trips")
def create_trip(req: TripRequest, db: Session = Depends(get_db)):
    state = ProcessState(
        destination=req.destination,
        traveler_id=req.travelerId
    )
    db.add(state)
    db.flush()
    
    outbox_evt = state.handle_initialization()
    if outbox_evt:
        db.add(outbox_evt)
    db.commit()
    
    return {"bookingId": str(state.id), "status": state.status.value}

@app.get("/trips/{booking_id}")
def get_trip(booking_id: str, db: Session = Depends(get_db)):
    state = db.query(ProcessState).filter(ProcessState.id == booking_id).first()
    if not state:
        raise HTTPException(status_code=404, detail="Trip not found")
        
    route_dict = None
    if state.current_route:
        route_dict = {
            "routeId": state.current_route.route_id,
            "airline": state.current_route.airline,
            "cost": state.current_route.cost
        }
        
    return {
        "bookingId": str(state.id),
        "status": state.status.value,
        "destination": state.destination,
        "current_route": route_dict,
        "rejected_routes": state.rejected_routes
    }

@app.post("/trips/{booking_id}/approval")
def approve_trip(booking_id: str, req: ApprovalRequest, db: Session = Depends(get_db)):
    state = db.query(ProcessState).filter(ProcessState.id == booking_id).first()
    if not state:
        raise HTTPException(status_code=404, detail="Trip not found")
        
    outbox_evt = state.handle_approval(req.approved)
    if outbox_evt:
        db.add(outbox_evt)
        
    db.commit()
    return {"status": state.status.value}
