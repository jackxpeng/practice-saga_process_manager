import os
from sqlalchemy import create_engine, Column, String, Boolean, Table
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import registry, sessionmaker

# Import pure dataclasses from the domain
from domain import ProcessState, OutboxEvent

mapper_registry = registry()
metadata = mapper_registry.metadata

process_state_table = Table(
    "process_state",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("status", String, nullable=False),
    Column("destination", String, nullable=False),
    Column("traveler_id", String, nullable=False),
    Column("current_route", JSONB, nullable=True),
    Column("rejected_routes", JSONB, nullable=True, default=list),
    Column("flight_confirmation", String, nullable=True),
)

outbox_events_table = Table(
    "outbox_events",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("aggregate_id", UUID(as_uuid=True), nullable=False),
    Column("event_type", String, nullable=False),
    Column("payload", JSONB, nullable=False),
    Column("published", Boolean, default=False),
)


# Imperative mapping cleanly links the Tables to the Domain dataclasses
def start_mappers():
    # Only map if not already mapped
    try:
        mapper_registry.map_imperatively(ProcessState, process_state_table)
        mapper_registry.map_imperatively(OutboxEvent, outbox_events_table)
    except Exception:
        pass


DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://tripuser:trippass@trip-postgres:5432/tripdb"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    start_mappers()
    metadata.create_all(bind=engine)
