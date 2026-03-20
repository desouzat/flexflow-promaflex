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
    "postgresql://flexflow_app:Souza%40123@127.0.0.1:5433/flexflow_prod"
)

# Debug print to verify the correct connection is being used
print(f"[DEBUG] Conectando ao banco em: {SQLALCHEMY_DATABASE_URL}")

# Create SQLAlchemy engine with connection pooling
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,  # Number of connections to maintain in the pool
    max_overflow=20,  # Maximum number of connections that can be created beyond pool_size
    pool_pre_ping=True,  # Verify connections before using them
    pool_recycle=3600,  # Recycle connections after 1 hour
    echo=os.getenv("SQL_ECHO", "false").lower() == "true",  # Log SQL queries if enabled
)

# Create SessionLocal class for database sessions
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,  # Prevent lazy loading issues after commit
)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency function to get database session.
    
    Yields a database session and ensures it's properly closed after use.
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
    finally:
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
