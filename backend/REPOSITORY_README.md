# FlexFlow Repository Layer

## Overview

The repository layer provides a clean, secure data access interface with **automatic tenant isolation**. All database operations are automatically filtered by `tenant_id`, ensuring complete data separation between tenants.

## Architecture

```
backend/
├── database.py              # SQLAlchemy engine and session configuration
├── models.py                # Database models
└── repositories/
    ├── __init__.py          # Repository exports
    ├── base_repository.py   # Generic CRUD with tenant filtering
    └── po_repository.py     # Specialized PurchaseOrder operations
```

## Key Features

### 🔒 Automatic Tenant Isolation
Every repository operation automatically filters by `tenant_id`. You cannot accidentally access another tenant's data.

### 🎯 Generic CRUD Operations
[`BaseRepository`](backend/repositories/base_repository.py) provides standard operations for any model:
- `create()` - Create with automatic tenant_id assignment
- `get_by_id()` - Get single record (tenant-filtered)
- `get_all()` - Get multiple records with pagination
- `update()` - Update existing record
- `delete()` - Delete record
- `bulk_create()` - Create multiple records
- `count()` - Count records with filters

### 🚀 Specialized Operations
[`PORepository`](backend/repositories/po_repository.py) extends base functionality with PO-specific methods:
- `get_by_id_with_items()` - Eager load PO with items
- `get_by_po_number()` - Find by PO number
- `get_by_status()` - Filter by status
- `get_by_supplier()` - Filter by supplier
- `get_by_date_range()` - Date range queries
- `search_by_text()` - Full-text search
- `get_statistics()` - Aggregate statistics
- `create_with_items()` - Transactional PO+items creation
- `update_with_items()` - Update PO and replace items
- `delete_with_items()` - Cascade delete

## Configuration

### Environment Variables

Configure database connection in [`backend/database.py`](backend/database.py:17):

```bash
# Required
DATABASE_URL=postgresql://user:password@host:port/database

# Optional
SQL_ECHO=true  # Enable SQL query logging (default: false)
```

### Connection Pool Settings

Configured in [`backend/database.py`](backend/database.py:24):
- **pool_size**: 10 connections
- **max_overflow**: 20 additional connections
- **pool_pre_ping**: Verify connections before use
- **pool_recycle**: Recycle connections after 1 hour

## Usage Examples

### Basic Repository Usage

```python
from uuid import uuid4
from backend.database import SessionLocal
from backend.repositories import PORepository
from backend.models import POStatus

# Create database session
db = SessionLocal()

# Get tenant_id from authentication context
tenant_id = uuid4()  # In real app: from JWT token or session

# Initialize repository with tenant context
po_repo = PORepository(db, tenant_id)

# All operations are automatically tenant-filtered
pos = po_repo.get_all(skip=0, limit=10)
```

### Creating a PO with Items

```python
from datetime import datetime

po_data = {
    "po_number": "PO-2024-001",
    "supplier_id": supplier_id,
    "order_date": datetime.now(),
    "status": POStatus.DRAFT,
    "total_value": 1500.00,
    "currency": "USD"
}

items_data = [
    {
        "item_code": "ITEM-001",
        "description": "Widget A",
        "quantity": 10,
        "unit_price": 100.00,
        "total_price": 1000.00
    }
]

# Create in single transaction
po = po_repo.create_with_items(po_data, items_data)
```

### Querying with Filters

```python
# Get by status
draft_pos = po_repo.get_by_status(POStatus.DRAFT)

# Get by supplier
supplier_pos = po_repo.get_by_supplier(supplier_id)

# Date range query
from datetime import datetime, timedelta
start = datetime.now() - timedelta(days=30)
end = datetime.now()
recent_pos = po_repo.get_by_date_range(start, end)

# Text search
results = po_repo.search_by_text("urgent")
```

### Getting Statistics

```python
stats = po_repo.get_statistics()
# Returns:
# {
#     "total_count": 150,
#     "by_status": {
#         "draft": 20,
#         "approved": 80,
#         "received": 50
#     },
#     "total_value": 125000.00,
#     "value_by_status": {
#         "draft": 15000.00,
#         "approved": 60000.00,
#         "received": 50000.00
#     }
# }
```

### Using BaseRepository for Other Models

```python
from backend.repositories.base_repository import BaseRepository
from backend.models import Supplier

# Create repository for any model
supplier_repo = BaseRepository(Supplier, db, tenant_id)

# Use generic CRUD operations
supplier = Supplier(name="ACME Corp", email="contact@acme.com")
created = supplier_repo.create(supplier)

# All operations are tenant-filtered
all_suppliers = supplier_repo.get_all()
supplier = supplier_repo.get_by_id(supplier_id)
updated = supplier_repo.update(supplier_id, {"name": "ACME Corporation"})
deleted = supplier_repo.delete(supplier_id)
```

### Eager Loading Relationships

```python
# Load PO with all items in single query
po = po_repo.get_by_id_with_items(po_id)
for item in po.items:
    print(f"{item.description}: {item.quantity}")

# Get all POs with items
pos = po_repo.get_all_with_items(skip=0, limit=10)
```

## Tenant Isolation

### How It Works

1. **Repository Initialization**: Each repository requires a `tenant_id`
   ```python
   repo = PORepository(db, tenant_id)
   ```

2. **Automatic Filtering**: All queries automatically include tenant filter
   ```python
   # This query:
   po = repo.get_by_id(po_id)
   
   # Becomes:
   # SELECT * FROM purchase_orders 
   # WHERE id = :po_id AND tenant_id = :tenant_id
   ```

3. **Automatic Assignment**: All creates automatically set tenant_id
   ```python
   po = repo.create(po_data)
   # po.tenant_id is automatically set
   ```

### Security Guarantees

✅ **Cannot read** other tenant's data  
✅ **Cannot update** other tenant's data  
✅ **Cannot delete** other tenant's data  
✅ **Cannot create** data for other tenants  

### Testing Tenant Isolation

```python
tenant1_id = uuid4()
tenant2_id = uuid4()

repo1 = PORepository(db, tenant1_id)
repo2 = PORepository(db, tenant2_id)

# Create PO for tenant1
po = repo1.create(po_data)

# Tenant2 cannot access it
po_from_tenant2 = repo2.get_by_id(po.id)
assert po_from_tenant2 is None  # ✓ Isolated
```

## Database Session Management

### Using get_db() Dependency

For FastAPI applications:

```python
from fastapi import Depends
from backend.database import get_db
from sqlalchemy.orm import Session

@app.get("/pos")
def list_pos(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    repo = PORepository(db, current_user.tenant_id)
    return repo.get_all()
```

### Manual Session Management

```python
from backend.database import SessionLocal

db = SessionLocal()
try:
    repo = PORepository(db, tenant_id)
    # ... operations ...
finally:
    db.close()
```

## Database Initialization

### Create Tables

```python
from backend.database import init_db

# Create all tables defined in models
init_db()
```

### Drop All Tables (Development Only)

```python
from backend.database import drop_all_tables

# WARNING: Deletes all data
drop_all_tables()
```

## Best Practices

### ✅ DO

- Always initialize repositories with tenant_id from authenticated user
- Use `get_db()` dependency in FastAPI for automatic session management
- Close sessions in `finally` blocks when managing manually
- Use specialized repository methods when available
- Use `create_with_items()` for transactional operations

### ❌ DON'T

- Don't bypass repositories and query models directly
- Don't hardcode tenant_id values
- Don't forget to close database sessions
- Don't modify tenant_id after object creation
- Don't use raw SQL without tenant filtering

## Error Handling

```python
from sqlalchemy.exc import IntegrityError

try:
    po = repo.create(po_data)
except IntegrityError as e:
    # Handle duplicate po_number, etc.
    db.rollback()
    raise
```

## Performance Tips

1. **Use eager loading** for relationships:
   ```python
   po = repo.get_by_id_with_items(po_id)  # Single query
   ```

2. **Paginate large result sets**:
   ```python
   pos = repo.get_all(skip=0, limit=100)
   ```

3. **Use bulk operations** when possible:
   ```python
   items = repo.bulk_create([item1, item2, item3])
   ```

4. **Filter at database level**:
   ```python
   # Good: Filter in query
   pos = repo.get_by_status(POStatus.DRAFT)
   
   # Bad: Filter in Python
   all_pos = repo.get_all()
   draft_pos = [po for po in all_pos if po.status == POStatus.DRAFT]
   ```

## Testing

Run the example test file:

```bash
python backend/test_repositories.py
```

This demonstrates:
- Creating POs with items
- Querying with various filters
- Tenant isolation verification
- Update and delete operations
- Statistics and aggregations

## Next Steps

After implementing the repository layer:

1. **Service Layer**: Implement business logic using repositories
2. **API Layer**: Create FastAPI endpoints using services
3. **Authentication**: Integrate JWT tokens for tenant_id extraction
4. **Validation**: Add Pydantic schemas for request/response validation
5. **Testing**: Write comprehensive unit and integration tests

## Related Files

- [`backend/models.py`](backend/models.py) - Database models
- [`backend/database.py`](backend/database.py) - Database configuration
- [`backend/repositories/base_repository.py`](backend/repositories/base_repository.py) - Generic repository
- [`backend/repositories/po_repository.py`](backend/repositories/po_repository.py) - PO repository
- [`backend/test_repositories.py`](backend/test_repositories.py) - Usage examples
