import os
from sqlalchemy import create_engine, Column, String, Boolean, Table, DateTime, Enum as SQLEnum, JSON, Uuid
from sqlalchemy.types import TypeDecorator
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import registry, sessionmaker
import datetime

from domain import ProcessState, OutboxEvent, TripStatus, Route

mapper_registry = registry()
metadata = mapper_registry.metadata

# Use generic JSON that uses JSONB when on Postgres, so SQLite tests pass
GenericJSON = JSON().with_variant(JSONB, 'postgresql')

# TypeDecorator to convert between the Route Value Object and JSON
class RouteType(TypeDecorator):
    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(JSONB())
        else:
            return dialect.type_descriptor(JSON())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, Route):
            return {"routeId": value.route_id, "airline": value.airline, "cost": value.cost}
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return Route(route_id=value.get("routeId", ""), airline=value.get("airline", ""), cost=value.get("cost", 0.0))


process_state_table = Table(
    "process_state",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column("status", SQLEnum(TripStatus, native_enum=False), nullable=False),
    Column("destination", String, nullable=False),
    Column("traveler_id", String, nullable=False),
    Column("current_route", RouteType, nullable=True),
    Column("rejected_routes", GenericJSON, nullable=True, default=list),
    Column("flight_confirmation", String, nullable=True),
)

outbox_events_table = Table(
    "outbox_events",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column("aggregate_id", Uuid(as_uuid=True), nullable=False),
    Column("event_type", String, nullable=False),
    Column("payload", GenericJSON, nullable=False),
    Column("published", Boolean, default=False),
    Column("created_at", DateTime, nullable=False, default=datetime.datetime.utcnow),
)


def start_mappers():
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
