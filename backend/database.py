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
from sqlalchemy.pool import QueuePool

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

def get_engine():
    print(f"[DEBUG] Lazy database engine initialization...")
    print(f"[DEBUG] Conectando ao banco em: {DATABASE_URL}")
    try:
        # Check if Unix socket fallback is needed
        socket_info = DATABASE_URL.split('@')[-1]
        print(f"DEBUG: Connecting to DB via Unix Socket: {socket_info}")
    except Exception:
        pass

    # ─── Connection Pool Sizing for Cloud Run + Cloud SQL Proxy ──────────────
    # Cloud Run scales horizontally (multiple instances). Each instance must
    # hold a pool sized for its actual concurrent workload while keeping the
    # total across all instances below Cloud SQL's max_connections limit.
    #
    # Current sizing (as of 2026-06-10):
    #   pool_size=15, max_overflow=15  →  up to 30 connections per container
    #
    # Formula:  (pool_size + max_overflow) × max_concurrent_instances < max_connections
    # E.g.:     30 × 3 instances = 90 < 100 Cloud SQL limit — safe at low scale.
    #
    # "Mesa de Conferência" issues multiple concurrent DB requests per page
    # load (kanban board + dashboard + user context). A pool of 5 caused
    # pool_timeout errors under normal UAT traffic. Raised to 15/15 to give
    # each container headroom for those burst requests.
    #
    # If horizontal scaling increases beyond 3 simultaneous containers,
    # revisit this value or configure pgBouncer on the Cloud SQL side.
    # ─────────────────────────────────────────────────────────────────────────
    try:
        return create_engine(
            SQLALCHEMY_DATABASE_URL,
            poolclass=QueuePool,
            pool_size=15,          # Max persistent connections per process instance
            max_overflow=15,       # Max burst connections beyond pool_size (total: 30/instance)
            pool_timeout=30,       # Raise after 30s if no connection is available
                                   # (prevents requests hanging indefinitely under load)
            pool_pre_ping=True,    # Verify connections are alive before use (catches stale sockets)
            pool_recycle=1800,     # Recycle connections after 30 min (tighter for Cloud SQL)
            connect_args={
                "connect_timeout": 10,  # Socket-level TCP timeout in seconds
            },
            echo=os.getenv("SQL_ECHO", "false").lower() == "true",
        )
    except Exception as e:
        print(f"[ERROR] Failed to create database engine: {e}")
        try:
            return create_engine("sqlite:///:memory:")
        except Exception:
            return None

class LazyEngine:
    def __init__(self):
        self._real_engine = None

    def _get_real_engine(self):
        if self._real_engine is None:
            self._real_engine = get_engine()
        return self._real_engine

    def __getattr__(self, name):
        return getattr(self._get_real_engine(), name)

    def __repr__(self):
        return repr(self._get_real_engine())

    def __str__(self):
        return str(self._get_real_engine())

# Instantiate the lazy engine
engine = LazyEngine()

class LazySessionLocal:
    def __init__(self):
        self._real_sessionmaker = None

    def _get_real_sessionmaker(self):
        if self._real_sessionmaker is None:
            self._real_sessionmaker = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=engine,
                expire_on_commit=False,  # Prevent lazy loading issues after commit
            )
        return self._real_sessionmaker

    def __call__(self, *args, **kwargs):
        return self._get_real_sessionmaker()(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._get_real_sessionmaker(), name)

# Instantiate the lazy sessionmaker
SessionLocal = LazySessionLocal()


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
