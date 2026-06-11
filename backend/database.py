"""
Database configuration module for FlexFlow.

This module sets up the SQLAlchemy engine and session factory using
environment variables for database connection configuration.
"""

# CRITICAL: Load environment variables FIRST before any other imports or operations
from dotenv import load_dotenv
from pathlib import Path
import os

# Get the directory where this file is located (backend/)
current_dir = Path(__file__).resolve().parent
env_path = current_dir / '.env'

# Load .env file with explicit path
load_dotenv(dotenv_path=env_path)

# Debug: Check if .env file exists and was loaded
print(f"[DEBUG] Procurando .env em: {env_path}")
print(f"[DEBUG] Arquivo .env existe: {env_path.exists()}")
print(f"[DEBUG] DATABASE_URL carregada: {os.getenv('DATABASE_URL', 'NAO ENCONTRADA')}")

from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from sqlalchemy.pool import NullPool

# Create declarative base for models
Base = declarative_base()

# Database URL from environment variable
# Format: postgresql://user:password@host:port/database
# Fallback updated to use Google Cloud credentials
SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://flexflow_app:Souza%40123@127.0.0.1:5434/flexflow_prod"
)

# Debug print to verify the correct connection is being used
DATABASE_URL = SQLALCHEMY_DATABASE_URL


# ─── Create engine at module load time (not lazily) ─────────────────────────
# The LazyEngine wrapper was creating a new engine proxy on every __getattr__
# call, which caused NullPool to open a fresh TCP connection per flush(),
# destroying transaction continuity between PO and item inserts.
# A direct engine object guarantees all Session operations share one connection.
print(f"[DEBUG] Initializing database engine...")
print(f"[DEBUG] Conectando ao banco em: {SQLALCHEMY_DATABASE_URL}")
try:
    socket_info = SQLALCHEMY_DATABASE_URL.split('@')[-1]
    print(f"DEBUG: Connecting to DB via Unix Socket: {socket_info}")
except Exception:
    pass

try:
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        poolclass=NullPool,        # One connection per session, closed on release
        connect_args={
            "connect_timeout": 10,
        },
        echo=os.getenv("SQL_ECHO", "false").lower() == "true",
    )
except Exception as e:
    print(f"[ERROR] Failed to create database engine: {e}")
    engine = create_engine("sqlite:///:memory:")

# Standard sessionmaker bound to the single stable engine instance
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency function to get database session.

    Yields a database session and ensures it's properly closed after use.
    Includes explicit rollback on exception to prevent dirty connections from
    being returned to the pool — critical for Cloud Run where connection slots
    are limited and a transaction left open blocks all other waiters.

    Typical usage in FastAPI:
        @app.get("/items")
        def read_items(db: Session = Depends(get_db)):
            ...

    Yields:
        Session: SQLAlchemy database session
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        # Roll back any open transaction so the connection is returned to the
        # pool in a clean state. Without this, a failed request may leave the
        # connection in an aborted transaction state, causing subsequent users
        # of that pooled connection to receive unexpected errors.
        db.rollback()
        raise
    finally:
        # Always release the connection back to the pool, even if rollback
        # failed. This is the critical gate that prevents connection leaks.
        db.close()


def init_db() -> None:
    """
    Initialize database by creating all tables.
    
    This should be called on application startup to ensure
    all tables defined in models are created.
    """
    # Import models to register them with Base
    # from backend.models import PurchaseOrder, OrderItem, etc.
    Base.metadata.create_all(bind=engine)


def drop_all_tables() -> None:
    """
    Drop all tables from the database.
    
    WARNING: This will delete all data. Use only in development/testing.
    """
    Base.metadata.drop_all(bind=engine)
