import sys, os
sys.path.append(os.path.abspath('trip-booking-manager'))
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import start_mappers, metadata
from domain import ProcessState, TripStatus

engine = create_engine("sqlite:///:memory:")
start_mappers()
metadata.create_all(engine)
Session = sessionmaker(bind=engine)
db = Session()

state = ProcessState(destination="Seattle", traveler_id="123")
db.add(state)
db.flush()
print("After flush, status is:", repr(state.status))
print("Equality check:", state.status == TripStatus.INITIALIZED)
evt = state.handle_initialization()
print("After handle, status is:", repr(state.status))
print("Event returned:", evt)
db.commit()

state2 = db.query(ProcessState).first()
print("From DB:", repr(state2.status))
