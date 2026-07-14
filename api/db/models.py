"""SQLAlchemy models: jobs, city_cache, users (placeholder).

Mirrors the SQL in the build brief §3.4. JSON columns become JSONB on
Postgres and plain JSON on the SQLite dev fallback. UUIDs are generated
client-side so the same code runs on both backends.

The users table exists only so the schema won't need to change when real
auth/payments are wired in later — nothing reads or writes it in this build.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base

Base = declarative_base()

JSONVariant = JSON().with_variant(JSONB(), "postgresql")


def _uuid() -> str:
    return str(uuid.uuid4())


def _now():
    return datetime.now(timezone.utc)


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True, default=_uuid)
    kind = Column(String(16), nullable=False, default="analyze")  # analyze | compare
    city_name = Column(Text, nullable=False)
    config = Column(JSONVariant, nullable=False, default=dict)
    status = Column(String(16), nullable=False, default="pending")  # pending|running|done|error
    progress = Column(Text, nullable=True)  # human-readable stage; DB-backed so
    # any Cloud Run replica serves it (no in-process state)
    result = Column(JSONVariant, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)
    completed_at = Column(DateTime(timezone=True), nullable=True)


class CityCache(Base):
    __tablename__ = "city_cache"

    city_name = Column(Text, primary_key=True)
    bbox = Column(JSONVariant, nullable=True)
    raw_data = Column(JSONVariant, nullable=False)
    cached_at = Column(DateTime(timezone=True), default=_now)
    # TTL enforced in application code: rows older than CITY_CACHE_TTL_DAYS
    # are treated as stale on read (see engine/cache.py).


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=_uuid)
    email = Column(Text, nullable=True)            # placeholder only
    payment_status = Column(String(32), default="none")  # future Stripe wiring
    created_at = Column(DateTime(timezone=True), default=_now)
