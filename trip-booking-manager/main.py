from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import SessionLocal, init_db
from domain import ProcessManagerDomain, ProcessState, OutboxEvent
from relay import start_relay
from consumer import start_consumer

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
    start_relay()
    start_consumer()

@app.post("/trips")
def create_trip(req: TripRequest, db: Session = Depends(get_db)):
    state = ProcessState(
        status="Initialized",
        destination=req.destination,
        traveler_id=req.travelerId
    )
    db.add(state)
    db.flush()
    
    outbound_command = ProcessManagerDomain.handle_initialization(state)
    outbox_evt = OutboxEvent(
        aggregate_id=state.id,
        event_type=outbound_command["event_type"],
        payload=outbound_command["payload"]
    )
    db.add(outbox_evt)
    db.commit()
    
    return {"bookingId": str(state.id), "status": state.status}

@app.get("/trips/{booking_id}")
def get_trip(booking_id: str, db: Session = Depends(get_db)):
    state = db.query(ProcessState).filter(ProcessState.id == booking_id).first()
    if not state:
        raise HTTPException(status_code=404, detail="Trip not found")
    return {
        "bookingId": str(state.id),
        "status": state.status,
        "destination": state.destination,
        "current_route": state.current_route,
        "rejected_routes": state.rejected_routes
    }

@app.post("/trips/{booking_id}/approval")
def approve_trip(booking_id: str, req: ApprovalRequest, db: Session = Depends(get_db)):
    state = db.query(ProcessState).filter(ProcessState.id == booking_id).first()
    if not state:
        raise HTTPException(status_code=404, detail="Trip not found")
        
    if state.status != "AwaitingApproval":
        raise HTTPException(status_code=400, detail=f"Cannot approve in state {state.status}")
        
    outbound_command = ProcessManagerDomain.handle_approval(state, req.approved)
    if outbound_command:
        outbox_evt = OutboxEvent(
            aggregate_id=state.id,
            event_type=outbound_command["event_type"],
            payload=outbound_command["payload"]
        )
        db.add(outbox_evt)
        
    db.commit()
    return {"status": state.status}
