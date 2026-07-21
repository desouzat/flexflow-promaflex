"""
FlexFlow Main Application
FastAPI application with all routers and middleware.
"""

# ── openpyxl 'biltinId' typo patch ───────────────────────────────────────────
# Some Excel files produced by older versions of Excel or third-party tools
# use the misspelled attribute 'biltinId' instead of the correct 'builtinId'.
# openpyxl raises a TypeError when it encounters this typo during parsing.
# This patch intercepts the _NamedCellStyle constructor and silently corrects
# the spelling before openpyxl processes it.
# Must be applied BEFORE any router or service imports that load openpyxl.
try:
    from openpyxl.styles.named_styles import _NamedCellStyle
    _original_named_cell_style_init = _NamedCellStyle.__init__

    def _patched_named_cell_style_init(self, *args, **kwargs):
        if 'biltinId' in kwargs:
            kwargs['builtinId'] = kwargs.pop('biltinId')
        _original_named_cell_style_init(self, *args, **kwargs)

    _NamedCellStyle.__init__ = _patched_named_cell_style_init
except ImportError:
    pass  # openpyxl not installed — patch not needed
# ─────────────────────────────────────────────────────────────────────────────

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
import time

from backend.routers import auth, import_router, kanban, dashboard, costs, workshop, partition, users, support, dashboard_router, settings
from backend.routers import reports  # FF-HARDENING-012.2: CSV export router
from backend.database import engine, Base
from backend.middleware import AuthenticationMiddleware, TenantIsolationMiddleware

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
    from datetime import datetime
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    print(f"{timestamp} Starting FlexFlow API...")
    
    # Define background schema initialization to prevent blocking startup
    def run_db_init_sync():
        from sqlalchemy import text
        print("[DEBUG] Starting background DB schema initialization...")

        # ── _run_ddl_step ────────────────────────────────────────────────────
        # Each DDL step acquires a raw DBAPI connection via engine.connect(),
        # executes its SQL, then unconditionally calls conn.rollback() on any
        # error and conn.close() in the finally block.
        #
        # WHY NOT engine.begin()? engine.begin() is a context manager whose
        # __exit__ calls rollback() internally — but if that internal rollback
        # raises (which psycopg2 does when the connection is in an aborted
        # transaction state after a DuplicateColumn DDL error), the exception
        # is silently swallowed and the connection is returned to the pool in
        # a dirty "idle in transaction (aborted)" state. pool_pre_ping only
        # sends SELECT 1, which succeeds even on aborted connections, so the
        # dirty slot is never detected and permanently occupies the pool.
        #
        # The explicit try/except/finally below guarantees:
        #   1. conn.rollback() is called in the except branch (resets state)
        #   2. conn.close() is called in the finally branch (returns to pool)
        #   3. If rollback() itself raises, the error is logged but close()
        #      still executes because it is in the finally block, not nested
        #      inside except.
        # ────────────────────────────────────────────────────────────────────
        def _run_ddl_step(step_name: str, statements: list):
            conn = None
            try:
                conn = engine.connect()
                for sql in statements:
                    conn.execute(text(sql))
                conn.commit()
                print(f"Successfully {step_name}.")
            except Exception as e:
                print(f"{step_name} skipped/failed (likely already exists): {e}")
                if conn is not None:
                    try:
                        conn.rollback()
                    except Exception as rb_err:
                        print(f"[WARN] rollback failed during '{step_name}': {rb_err}")
            finally:
                if conn is not None:
                    try:
                        conn.close()
                    except Exception as cl_err:
                        print(f"[WARN] conn.close() failed during '{step_name}': {cl_err}")

        # Step 1 — DDL column migration (expected to fail gracefully on re-deploy)
        _run_ddl_step(
            "added 'area' column to users table",
            ["ALTER TABLE users ADD COLUMN area VARCHAR(100)"]
        )

        # Step 2 — client_preferences table + index
        _run_ddl_step(
            "initialized client_preferences table",
            [
                """
                CREATE TABLE IF NOT EXISTS client_preferences (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                    client_name VARCHAR(255) NOT NULL,
                    business_unit VARCHAR(100) NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT unique_tenant_client UNIQUE (tenant_id, client_name)
                );
                """,
                "CREATE INDEX IF NOT EXISTS idx_client_preference_tenant_id ON client_preferences(tenant_id);"
            ]
        )

        # Step 3 — SupportTickets table + indexes
        _run_ddl_step(
            "initialized SupportTickets table",
            [
                """
                CREATE TABLE IF NOT EXISTS "SupportTickets" (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    ticket_id VARCHAR(50) UNIQUE NOT NULL,
                    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    description TEXT NOT NULL,
                    attachment_path VARCHAR(500),
                    status VARCHAR(50) DEFAULT 'OPEN' NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    resolved_at TIMESTAMP WITH TIME ZONE,
                    CONSTRAINT ck_support_ticket_status CHECK (status IN ('OPEN', 'IN_PROGRESS', 'RESOLVED', 'CLOSED'))
                );
                """,
                "CREATE INDEX IF NOT EXISTS idx_support_ticket_ticket_id ON \"SupportTickets\"(ticket_id);",
                "CREATE INDEX IF NOT EXISTS idx_support_ticket_user_id ON \"SupportTickets\"(user_id);",
                "CREATE INDEX IF NOT EXISTS idx_support_ticket_status ON \"SupportTickets\"(status);",
                "CREATE INDEX IF NOT EXISTS idx_support_ticket_created_at ON \"SupportTickets\"(created_at);"
            ]
        )

        # Step 4 — GlobalConfig table + indexes
        _run_ddl_step(
            "initialized GlobalConfig table",
            [
                """
                CREATE TABLE IF NOT EXISTS "GlobalConfig" (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                    config_key VARCHAR(100) NOT NULL,
                    config_value VARCHAR(500) NOT NULL,
                    config_type VARCHAR(50) DEFAULT 'str' NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_by UUID REFERENCES users(id) ON DELETE SET NULL,
                    CONSTRAINT unique_tenant_config UNIQUE (tenant_id, config_key)
                );
                """,
                "CREATE INDEX IF NOT EXISTS idx_global_config_tenant_id ON \"GlobalConfig\"(tenant_id);",
                "CREATE INDEX IF NOT EXISTS idx_global_config_key ON \"GlobalConfig\"(config_key);"
            ]
        )

        # Step 5 — FF-HARDENING-012.2: Recreate check_po_status_macro to include BILLING
        # The two ALTER TABLE statements are wrapped individually so that if the DROP
        # fails for any reason, the connection is rolled back before the ADD is attempted.
        # On re-deploy (constraint already correct) the DROP succeeds silently and the
        # ADD also succeeds — total operation is fully idempotent.
        _run_ddl_step(
            "alter_status_constraint_billing: dropped old check_po_status_macro constraint",
            [
                "ALTER TABLE purchase_orders DROP CONSTRAINT IF EXISTS check_po_status_macro"
            ]
        )
        _run_ddl_step(
            "alter_status_constraint_billing: recreated check_po_status_macro with BILLING",
            [
                """ALTER TABLE purchase_orders ADD CONSTRAINT check_po_status_macro CHECK (
                    status_macro IN (
                        'DRAFT', 'SUBMITTED', 'PCP', 'APPROVED', 'MANUFACTURING',
                        'BILLING', 'SHIPPING', 'WAITING_DISPATCH',
                        'ARCHIVED', 'ARCHIVED_PARTITIONED', 'COMPLETED', 'CANCELLED',
                        'WAITING_COMMERCIAL_PARTITION', 'WAITING_MATERIAL', 'ANALISE_CREDITO',
                        'FINANCE'
                    )
                )"""
            ]
        )

        # Step 6 — FF-HARDENING-012.4 Item 1: Final canonical status constraint
        # Drops and recreates check_po_status_macro with the definitive set of statuses
        # for the homologation release. Executed as two separate steps so that a DROP
        # failure never leaves the connection mid-transaction before the ADD attempt.
        # Fully idempotent: safe to re-run on every container startup.
        _run_ddl_step(
            "alter_status_constraint_billing_final: drop old check_po_status_macro",
            [
                "ALTER TABLE purchase_orders DROP CONSTRAINT IF EXISTS check_po_status_macro"
            ]
        )
        _run_ddl_step(
            "alter_status_constraint_billing_final: recreate check_po_status_macro with final canonical list",
            [
                """ALTER TABLE purchase_orders ADD CONSTRAINT check_po_status_macro CHECK (
                    status_macro IN (
                        'DRAFT', 'SUBMITTED', 'PCP', 'APPROVED', 'MANUFACTURING',
                        'BILLING', 'SHIPPING', 'WAITING_DISPATCH',
                        'ARCHIVED', 'ARCHIVED_PARTITIONED', 'COMPLETED', 'CANCELLED',
                        'WAITING_COMMERCIAL_PARTITION', 'FINANCE', 'WAITING_MATERIAL'
                    )
                )"""
            ]
        )  # FF-HARDENING-013 hotfix: added FINANCE + WAITING_MATERIAL (omitted in prior build)

        # Step 7 — staging_sessions table + unique index
        _run_ddl_step(
            "initialized staging_sessions table",
            [
                """
                CREATE TABLE IF NOT EXISTS staging_sessions (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    tenant_id UUID NOT NULL,
                    data JSONB NOT NULL,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_by VARCHAR(255)
                );
                """,
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_staging_session_tenant_id ON staging_sessions(tenant_id);"
            ]
        )

        print("[DEBUG] Background DB schema initialization completed.")

    async def init_db_background():
        import asyncio
        await asyncio.sleep(2)  # Allow port binding to succeed first
        await asyncio.to_thread(run_db_init_sync)

    import asyncio
    asyncio.create_task(init_db_background())

    # ── Automatic S3 background sync DISABLED ────────────────────────────────
    # The BackgroundWorker previously ran S3 sync every 10 minutes on startup.
    # This caused the server to block on financial validation errors during the
    # sync loop, making the API unavailable after boot.
    #
    # S3 synchronization is now STRICTLY MANUAL:
    #   → Users trigger it via the "Sincronizar com ONET (Nuvem)" button
    #   → Endpoint: POST /api/import/sync-s3
    #
    # To re-enable automatic sync in the future, uncomment the block below
    # and ensure the S3 service handles financial validation errors gracefully
    # without propagating exceptions that crash the background loop.
    # ─────────────────────────────────────────────────────────────────────────
    # from backend.services.background_worker import start_background_worker, stop_background_worker
    # try:
    #     await start_background_worker()
    #     timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    #     print(f"{timestamp} Background worker started successfully")
    # except Exception as e:
    #     timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    #     print(f"{timestamp} [WARNING] Background worker failed to start: {e}")
    #     print(f"{timestamp} [WARNING] S3 sync will not be available, but API will continue to work")
    
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    print(f"{timestamp} FlexFlow API started successfully")
    
    yield
    
    # Shutdown
    from datetime import datetime
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    print(f"{timestamp} Shutting down FlexFlow API...")
    # Background worker shutdown also disabled (worker was not started).
    # Uncomment if/when start_background_worker() above is re-enabled.
    # try:
    #     await stop_background_worker()
    # except Exception as e:
    #     timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    #     print(f"{timestamp} [WARNING] Error stopping background worker: {e}")


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

# CORS Middleware (must be first)
# CRITICAL: Cannot use allow_origins=["*"] with allow_credentials=True
# Must specify explicit origins when using credentials
import os

cors_origins_env = os.getenv("CORS_ORIGINS")
app_env = os.getenv("APP_ENV", "development").lower()
is_prod = app_env == "production" or os.getenv("DEBUG", "true").lower() == "false"

if is_prod:
    if cors_origins_env:
        origins = [origin.strip() for origin in cors_origins_env.split(",") if origin.strip()]
    else:
        # Strict fallback to production domain only
        origins = ["https://flexflow.promaflex.com.br"]
else:
    if cors_origins_env:
        origins = [origin.strip() for origin in cors_origins_env.split(",") if origin.strip()]
    else:
        origins = [
            "http://localhost:3000",
            "http://localhost:3001",
            "http://localhost:3002",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:3001",
            "http://127.0.0.1:3002"
        ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Authentication Middleware (validates JWT and injects context)
# MUST come BEFORE TenantIsolationMiddleware
# Excludes /api/auth/login, /api/auth/me, /api/ping and other public paths
app.add_middleware(
    AuthenticationMiddleware,
    exclude_paths=["/api/auth/login", "/api/auth/me", "/api/ping", "/api/uploads/download", "/api/health-check"]
)

# Tenant Isolation Middleware (checks tenant_id in context)
# MUST come AFTER AuthenticationMiddleware
app.add_middleware(
    TenantIsolationMiddleware
)


# Rate limiting and security headers middlewares
from collections import defaultdict
login_rate_limit_records = defaultdict(list)

@app.middleware("http")
async def rate_limit_login_middleware(request: Request, call_next):
    if request.url.path == "/api/auth/login" and request.method == "POST":
        import sys
        import os
        if "pytest" in sys.modules or os.getenv("TESTING") == "true":
            return await call_next(request)
            
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        
        # Clean up timestamps older than 60 seconds
        login_rate_limit_records[client_ip] = [
            t for t in login_rate_limit_records[client_ip] if now - t < 60
        ]
        
        if len(login_rate_limit_records[client_ip]) >= 5:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Muitas tentativas de login. Por favor, tente novamente em 1 minuto."
                }
            )
            
        # Record attempt
        login_rate_limit_records[client_ip].append(now)
        
    return await call_next(request)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:;"
    return response


# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add X-Process-Time header to all responses"""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


# Simple logging middleware - logs method, path, and status code with timestamps
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests with method, path, and status code"""
    from datetime import datetime
    timestamp_request = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    print(f"{timestamp_request} [REQUEST] {request.method} {request.url.path}")
    response = await call_next(request)
    timestamp_response = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    print(f"{timestamp_response} [RESPONSE] {request.method} {request.url.path} - Status: {response.status_code}")
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
    from datetime import datetime
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    print(f"{timestamp} [ERROR] Unexpected error: {str(exc)}")
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
app.include_router(dashboard_router.router)
app.include_router(costs.router)
app.include_router(partition.router)
app.include_router(users.router)
app.include_router(support.router)
app.include_router(settings.router)
app.include_router(reports.router)   # FF-HARDENING-012.2: CSV report export


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
            "dashboard": "/api/dashboard",
            "costs": "/api/costs",
            "partition": "/api/partition"
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


@app.get("/api/ping", tags=["Root"])
async def ping():
    """
    Public connectivity test endpoint - no authentication required
    """
    return {
        "status": "ok",
        "message": "FlexFlow API is reachable",
        "timestamp": time.time()
    }


@app.get("/api/health-check", tags=["Root"])
async def api_health_check():
    """
    Public health check bypass endpoint - does not touch database
    """
    return {
        "status": "ok",
        "database": "bypassed",
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
            },
            "costs": {
                "list_materials": "GET /api/costs/materials",
                "get_material": "GET /api/costs/materials/{sku}",
                "create_material": "POST /api/costs/materials",
                "update_material": "PUT /api/costs/materials/{sku}",
                "delete_material": "DELETE /api/costs/materials/{sku}",
                "settings": "GET /api/costs/settings"
            },
            "partition": {
                "suggest": "POST /api/partition/suggest",
                "execute": "POST /api/partition/execute",
                "pending": "GET /api/partition/pending",
                "history": "GET /api/partition/history/{po_id}",
                "preview": "GET /api/partition/preview/{po_id}"
            }
        }
    }


# ============================================================================
# SAFE FILE DOWNLOAD ENDPOINT
# ============================================================================

@app.get("/api/uploads/download", tags=["Uploads"])
async def download_uploaded_file(path: str):
    """
    Serve uploaded files safely with path traversal protection.
    """
    from fastapi.responses import FileResponse
    from fastapi import HTTPException
    import os
    
    clean_path = path.lstrip("/")
    # Remove 'backend/uploads/' or 'uploads/' prefix if present in path parameter to avoid double nesting
    if clean_path.startswith("backend/uploads/"):
        clean_path = clean_path[len("backend/uploads/"):]
    elif clean_path.startswith("uploads/"):
        clean_path = clean_path[len("uploads/"):]
        
    base_dir = os.path.abspath("backend/uploads")
    file_path = os.path.abspath(os.path.join(base_dir, clean_path))
    
    # Path traversal protection
    if not file_path.startswith(base_dir):
        raise HTTPException(status_code=403, detail="Acesso não autorizado")
        
    if not os.path.exists(file_path) or not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
        
    return FileResponse(file_path, filename=os.path.basename(file_path))


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
    # Trigger reload supervisor validation - May 2026
