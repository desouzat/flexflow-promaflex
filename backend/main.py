"""
FlexFlow Main Application
FastAPI application with all routers and middleware.
"""

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
import time

from backend.routers import auth, import_router, kanban, dashboard
from backend.database import engine, Base

# Application metadata
APP_TITLE = "FlexFlow API"
APP_DESCRIPTION = """
FlexFlow - Sistema de Gerenciamento de Pedidos de Compra

## Features

* **Authentication**: JWT-based authentication with multi-tenancy
* **Import Service**: Dynamic Excel/CSV import with margin calculation
* **Kanban Board**: Visual workflow management with state machine
* **Dashboard**: Real-time metrics and analytics
* **Multi-tenancy**: Complete tenant isolation

## Authentication

All endpoints (except `/api/auth/login`) require a valid JWT token in the Authorization header:

```
Authorization: Bearer <your-jwt-token>
```

Get a token by calling `/api/auth/login` with your credentials.
"""
APP_VERSION = "1.0.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # Startup
    print("Starting FlexFlow API...")
    
    # Create database tables (in production, use Alembic migrations)
    # Base.metadata.create_all(bind=engine)
    
    print("FlexFlow API started successfully")
    
    yield
    
    # Shutdown
    print("👋 Shutting down FlexFlow API...")


# Create FastAPI application
app = FastAPI(
    title=APP_TITLE,
    description=APP_DESCRIPTION,
    version=APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)


# ============================================================================
# MIDDLEWARE
# ============================================================================

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # React dev server
        "http://localhost:5173",  # Vite dev server
        "http://localhost:8080",  # Alternative frontend port
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add X-Process-Time header to all responses"""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


# Logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests"""
    print(f"[IN] {request.method} {request.url.path}")
    response = await call_next(request)
    print(f"[OUT] {request.method} {request.url.path} - Status: {response.status_code}")
    return response


# ============================================================================
# EXCEPTION HANDLERS
# ============================================================================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with detailed messages"""
    errors = []
    for error in exc.errors():
        errors.append({
            "field": " -> ".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Validation error",
            "errors": errors
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors"""
    print(f"[ERROR] Unexpected error: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal server error",
            "message": str(exc) if app.debug else "An unexpected error occurred"
        }
    )


# ============================================================================
# ROUTERS
# ============================================================================

# Include all routers
app.include_router(auth.router)
app.include_router(import_router.router)
app.include_router(kanban.router)
app.include_router(dashboard.router)


# ============================================================================
# ROOT ENDPOINTS
# ============================================================================

@app.get("/", tags=["Root"])
async def root():
    """
    Root endpoint - API information
    """
    return {
        "name": APP_TITLE,
        "version": APP_VERSION,
        "status": "running",
        "docs": "/docs",
        "redoc": "/redoc",
        "endpoints": {
            "auth": "/api/auth",
            "import": "/api/import",
            "kanban": "/api/kanban",
            "dashboard": "/api/dashboard"
        }
    }


@app.get("/health", tags=["Root"])
async def health_check():
    """
    Health check endpoint for monitoring
    """
    return {
        "status": "healthy",
        "timestamp": time.time()
    }


@app.get("/api", tags=["Root"])
async def api_info():
    """
    API information and available endpoints
    """
    return {
        "version": APP_VERSION,
        "endpoints": {
            "authentication": {
                "login": "POST /api/auth/login",
                "me": "GET /api/auth/me",
                "logout": "POST /api/auth/logout"
            },
            "import": {
                "upload": "POST /api/import/upload",
                "headers": "POST /api/import/headers",
                "field_types": "GET /api/import/field-types",
                "configs": "GET /api/import/configs",
                "save_config": "POST /api/import/configs",
                "get_config": "GET /api/import/configs/{config_name}",
                "delete_config": "DELETE /api/import/configs/{config_name}"
            },
            "kanban": {
                "board": "GET /api/kanban/board",
                "list_pos": "GET /api/kanban/pos",
                "get_po": "GET /api/kanban/pos/{po_id}",
                "move_status": "POST /api/kanban/move-status",
                "list_items": "GET /api/kanban/items"
            },
            "dashboard": {
                "metrics": "GET /api/dashboard/metrics",
                "summary": "GET /api/dashboard/summary",
                "margin_trend": "GET /api/dashboard/margin-trend",
                "lead_time_distribution": "GET /api/dashboard/lead-time-distribution",
                "top_clients": "GET /api/dashboard/top-clients",
                "status_timeline": "GET /api/dashboard/status-timeline",
                "alerts": "GET /api/dashboard/alerts"
            }
        }
    }


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Enable auto-reload for development
        log_level="info"
    )
