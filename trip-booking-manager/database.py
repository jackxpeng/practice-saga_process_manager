import os
import uuid
from sqlalchemy import create_engine, Column, String, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

class ProcessState(Base):
    __tablename__ = 'process_state'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status = Column(String, nullable=False)
    destination = Column(String, nullable=False)
    traveler_id = Column(String, nullable=False)
    current_route = Column(JSONB, nullable=True)
    rejected_routes = Column(JSONB, nullable=True, default=list)
    flight_confirmation = Column(String, nullable=True)

class OutboxEvent(Base):
    __tablename__ = 'outbox_events'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    aggregate_id = Column(UUID(as_uuid=True), nullable=False)
    event_type = Column(String, nullable=False)
    payload = Column(JSONB, nullable=False)
    published = Column(Boolean, default=False)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://tripuser:trippass@postgres:5432/tripdb")
# Fallback to local test if needed:
# DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://tripuser:trippass@localhost:5432/tripdb")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)
