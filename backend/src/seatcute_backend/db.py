"""SQLAlchemy engine/session plumbing and ORM models.

Deliberately dialect-agnostic: no SQLite-specific types, JSON columns, or
raw SQL anywhere here or in sql_store.py. Swapping SQLite for
Postgres/MySQL/etc. later is a DATABASE_URL + driver-package change --
nothing in this module or the store built on it needs to change.
Timestamps are epoch milliseconds stored as BigInteger (a plain 32-bit
Integer overflows well within a normal service's lifetime).
"""

from sqlalchemy import BigInteger, Boolean, Column, Integer, String, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import StaticPool

Base = declarative_base()


class ConfigRow(Base):
    __tablename__ = "config"

    size = Column(Integer, primary_key=True)
    count = Column(Integer, nullable=False)
    turnover_minutes = Column(Integer, nullable=False)


class CounterRow(Base):
    """Next label index per size (e.g. the "#3" in "2-Seat #3"), persisted
    so restarting the process never reuses (or collides with) a label."""

    __tablename__ = "counters"

    size = Column(Integer, primary_key=True)
    next_index = Column(Integer, nullable=False)


class TableRow(Base):
    __tablename__ = "tables"

    id = Column(String, primary_key=True)
    size = Column(Integer, nullable=False, index=True)
    label = Column(String, nullable=False)
    status = Column(String, nullable=False, default="available")
    occupied_at = Column(BigInteger, nullable=True)
    party_name = Column(String, nullable=True)
    party_phone = Column(String, nullable=True)
    pending_removal = Column(Boolean, nullable=False, default=False)


class QueueEntryRow(Base):
    __tablename__ = "queue_entries"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    party_size = Column(Integer, nullable=False)
    queue_size = Column(Integer, nullable=False, index=True)
    joined_at = Column(BigInteger, nullable=False)


def make_engine(database_url: str) -> Engine:
    connect_args = {}
    engine_kwargs = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        if ":memory:" in database_url:
            # A plain in-memory SQLite DB is per-connection; StaticPool pins
            # this engine to a single connection so every session shares the
            # same DB instead of each seeing its own empty one.
            engine_kwargs["poolclass"] = StaticPool
    return create_engine(database_url, connect_args=connect_args, **engine_kwargs)


def init_db(engine: Engine) -> None:
    Base.metadata.create_all(engine)
