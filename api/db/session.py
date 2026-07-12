"""Database connection. Neon Postgres via DATABASE_URL; SQLite fallback for dev.

Driver choice per the build brief: sync SQLAlchemy + psycopg2-binary (the
engine code is fully synchronous and jobs run in worker threads, so an async
driver would buy nothing).
"""
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

if DATABASE_URL:
    # Neon gives postgres:// URLs; SQLAlchemy 2.x needs postgresql://
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=5)
else:
    print("[db] DATABASE_URL not set — using local SQLite (dev only)")
    engine = create_engine(
        "sqlite:///urbanpulse_dev.db",
        connect_args={"check_same_thread": False},
    )

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db():
    from .models import Base
    Base.metadata.create_all(engine)
