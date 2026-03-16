# FlexFlow Workflow & Security Documentation

## Overview
This document describes the authentication, authorization, and workflow state machine implementation for FlexFlow.

## Architecture Components

### 1. Security Layer ([`backend/security.py`](backend/security.py:1))

#### Firebase Authentication Integration
- **FirebaseAuthService**: Integrates with Firebase Admin SDK for token verification
- **TokenPayload**: Represents decoded JWT token with user, tenant, and permission information
- **Permission Checking**: Fine-grained permission-based authorization

#### Key Features:
```python
# Verify Firebase ID token
token_payload = await firebase_auth.verify_token(token)

# Check permissions
if token_payload.has_permission("po.approve_pcp"):
    # User can approve PCP
    pass
```

#### Permission Model:
- `po.create` - Create new POs
- `po.read` - View POs
- `po.update` - Update PO details
- `po.approve_comercial` - Approve COMERCIAL → PCP
- `po.approve_pcp` - Approve PCP → PRODUCAO
- `po.reject_pcp` - Reject PCP → COMERCIAL
- `po.approve_producao` - Approve PRODUCAO → Parallel States
- `po.complete_expedicao` - Complete EXPEDICAO_PENDENTE
- `po.complete_faturamento` - Complete FATURAMENTO_PENDENTE
- `po.approve_despacho` - Complete DESPACHO → CONCLUIDO
- `po.delete` - Delete POs (admin only)
- `po.audit.read` - View audit trail

---

### 2. Middleware Layer ([`backend/middleware.py`](backend/middleware.py:1))

#### AuthenticationMiddleware
Extracts and validates JWT tokens from requests, injecting context into request state.

**Flow:**
1. Extract JWT from `Authorization: Bearer <token>` header
2. Validate token with Firebase
3. Create `RequestContext` with tenant_id, user_id, permissions
4. Inject context into `request.state.context`

#### TenantIsolationMiddleware
Enforces tenant isolation to ensure data security in multi-tenant environment.

#### Helper Functions:
```python
# Get request context
context = get_request_context(request)

# Require specific permission
require_permission(request, "po.approve_pcp")

# Require tenant access
require_tenant_access(request, tenant_id)
```

---

### 3. State Validators ([`backend/services/validators.py`](backend/services/validators.py:1))

Implements validation logic for each state transition according to PromaFlex business rules.

#### Key Validations:

**COMERCIAL → PCP:**
- Must have at least one item
- Customer information complete
- Delivery date set

**PCP → PRODUCAO (CRITICAL):**
- **If any item is personalized, PO MUST have attachments**
- Production schedule defined
- Schedule before delivery date

**PRODUCAO → Parallel States:**
- All items marked as produced
- Quality control passed
- Production notes documented

**EXPEDICAO_PENDENTE Completion:**
- Packing list generated
- Shipping documentation complete

**FATURAMENTO_PENDENTE Completion:**
- Invoice generated and attached
- Payment terms confirmed

**Parallel States → DESPACHO:**
- **BOTH** EXPEDICAO and FATURAMENTO completed

**DESPACHO → CONCLUIDO:**
- Dispatch date recorded
- Tracking number assigned

---

### 4. Workflow Service ([`backend/services/workflow_service.py`](backend/services/workflow_service.py:1))

Implements the state machine with audit trail integration.

#### State Machine Flow:

```
COMERCIAL → PCP → PRODUCAO → ┬→ EXPEDICAO_PENDENTE ┐
                              │                      ├→ DESPACHO → CONCLUIDO
                              └→ FATURAMENTO_PENDENTE┘

Rejection: PCP → COMERCIAL (mandatory)
```

#### Key Methods:

```python
workflow = WorkflowService(db)

# Approve transitions
await workflow.approve_comercial(po_id, context)
await workflow.approve_pcp(po_id, context)
await workflow.approve_producao(po_id, context)

# Reject PCP (returns to COMERCIAL)
await workflow.reject_pcp(po_id, context, reason="Missing specs")

# Complete parallel states
await workflow.complete_expedicao(po_id, context)
await workflow.complete_faturamento(po_id, context)

# Complete dispatch
await workflow.complete_despacho(po_id, context)
```

#### Audit Trail Integration:

Every state transition automatically:
1. Validates the transition
2. Creates an audit log entry
3. Calculates SHA-256 hash chained to previous record
4. Records user, timestamp, validation results, IP address

**Hash Chain Structure:**
```python
hash_data = {
    "previous_hash": previous_audit.current_hash,
    "tenant_id": tenant_id,
    "entity_id": po_id,
    "action": "state_transition",
    "user_id": user_id,
    "changes": {"status": {"from": "PCP", "to": "PRODUCAO"}},
    "metadata": {...},
    "timestamp": "2024-01-15T10:30:00Z"
}
current_hash = SHA256(hash_data)
```

#### Audit Chain Verification:

```python
# Verify audit trail integrity
verification = workflow.verify_audit_chain(po_id, tenant_id)

# Returns:
{
    "is_valid": True,
    "total_records": 5,
    "verified_records": 5,
    "broken_at": None,
    "details": [...]
}

# Get workflow history
history = workflow.get_workflow_history(po_id, tenant_id)
```

---

## Usage Examples

### 1. Setting Up Middleware in FastAPI

```python
from fastapi import FastAPI
from backend.middleware import AuthenticationMiddleware, TenantIsolationMiddleware

app = FastAPI()

# Add middleware (order matters - authentication first)
app.add_middleware(TenantIsolationMiddleware)
app.add_middleware(AuthenticationMiddleware, exclude_paths=["/health", "/docs"])
```

### 2. Creating a Protected Endpoint

```python
from fastapi import Request, HTTPException
from backend.middleware import get_request_context, require_permission

@app.post("/api/pos/{po_id}/approve-comercial")
async def approve_comercial(request: Request, po_id: str):
    # Get authenticated context
    context = get_request_context(request)
    
    # Check permission
    require_permission(request, "po.approve_comercial")
    
    # Perform workflow transition
    workflow = WorkflowService(db)
    updated_po = await workflow.approve_comercial(po_id, context)
    
    return {"status": "success", "po": updated_po}
```

### 3. Complete Workflow Example

```python
from backend.services.workflow_service import WorkflowService, WorkflowTransitionError

async def process_order_workflow(po_id: str, context: RequestContext, db: Session):
    workflow = WorkflowService(db)
    
    try:
        # 1. Commercial approval
        po = await workflow.approve_comercial(po_id, context)
        print(f"Status: {po.status}")  # PCP
        
        # 2. PCP approval (requires attachments for personalized items)
        po = await workflow.approve_pcp(po_id, context)
        print(f"Status: {po.status}")  # PRODUCAO
        
        # 3. Production completion
        po = await workflow.approve_producao(po_id, context)
        print(f"Status: {po.status}")  # EXPEDICAO_PENDENTE
        
        # 4. Complete shipping preparation
        po = await workflow.complete_expedicao(po_id, context)
        print(f"Expedicao completed: {po.expedicao_completed}")
        
        # 5. Complete invoicing
        po = await workflow.complete_faturamento(po_id, context)
        print(f"Status: {po.status}")  # DESPACHO (auto-transition)
        
        # 6. Complete dispatch
        po = await workflow.complete_despacho(po_id, context)
        print(f"Status: {po.status}")  # CONCLUIDO
        
    except WorkflowTransitionError as e:
        print(f"Transition failed: {e.message}")
        print(f"Error code: {e.error_code}")
        if e.validation_result:
            print(f"Validation: {e.validation_result.message}")
```

### 4. PCP Rejection Example

```python
async def reject_order_from_pcp(po_id: str, context: RequestContext, db: Session):
    workflow = WorkflowService(db)
    
    try:
        # Reject PCP - returns to COMERCIAL
        po = await workflow.reject_pcp(
            po_id=po_id,
            context=context,
            reason="Customer specifications incomplete. Missing technical drawings for custom items."
        )
        
        print(f"Status: {po.status}")  # COMERCIAL
        
        # Check audit trail
        history = workflow.get_workflow_history(po_id, context.tenant_id)
        for entry in history:
            print(f"{entry['timestamp']}: {entry['from_status']} → {entry['to_status']}")
            print(f"  Reason: {entry['reason']}")
        
    except WorkflowTransitionError as e:
        print(f"Rejection failed: {e.message}")
```

### 5. Creating Users with Permissions

```python
from backend.security import firebase_auth

async def create_pcp_manager():
    user = await firebase_auth.create_user(
        email="pcp.manager@promaflex.com",
        password="secure_password",
        tenant_id="promaflex_001",
        permissions=[
            "po.read",
            "po.approve_pcp",
            "po.reject_pcp",
            "po.audit.read"
        ],
        role="pcp_manager",
        display_name="PCP Manager"
    )
    return user
```

---

## State Machine Diagram

```
┌─────────────┐
│  COMERCIAL  │ (Initial State)
└──────┬──────┘
       │ Approve: Basic PO data validated
       ▼
┌─────────────┐
│     PCP     │ (Planning & Control)
└──────┬──────┘
       │ Approve: Personalized items must have attachments
       │ Reject: Returns to COMERCIAL
       ▼
┌─────────────┐
│  PRODUCAO   │ (Production)
└──────┬──────┘
       │ Approve: Production completed
       │
       ├──────────────────┬──────────────────┐
       │                  │                  │
       ▼                  ▼                  ▼
┌──────────────┐   ┌──────────────┐   (Both must complete)
│  EXPEDICAO   │   │ FATURAMENTO  │
│  _PENDENTE   │   │  _PENDENTE   │
└──────┬───────┘   └──────┬───────┘
       │                  │
       └────────┬─────────┘
                │ Both completed
                ▼
         ┌─────────────┐
         │  DESPACHO   │ (Dispatch)
         └──────┬──────┘
                │ Complete: Goods dispatched
                ▼
         ┌─────────────┐
         │  CONCLUIDO  │ (Completed - Final State)
         └─────────────┘
```

---

## Testing

Run the test suite:

```bash
# Run all workflow tests
pytest backend/test_workflow.py -v

# Run specific test class
pytest backend/test_workflow.py::TestWorkflowService -v

# Run with coverage
pytest backend/test_workflow.py --cov=backend/services --cov-report=html
```

Test coverage includes:
- ✅ State validation logic
- ✅ Workflow transitions
- ✅ Parallel states handling
- ✅ PCP rejection flow
- ✅ Audit trail creation
- ✅ Hash chain integrity
- ✅ Permission checking

---

## Security Considerations

### Multi-Tenancy
- All queries automatically filtered by `tenant_id`
- Middleware enforces tenant isolation
- Cross-tenant access blocked at middleware level

### Authentication
- Firebase Admin SDK for token verification
- Tokens checked for revocation
- Expired tokens rejected automatically

### Authorization
- Permission-based (not role-based) for flexibility
- Fine-grained permissions per action
- Permissions stored in JWT custom claims

### Audit Trail
- Immutable audit log with hash chaining
- SHA-256 ensures integrity
- Any tampering breaks the chain
- IP address and user tracked for all actions

---

## Environment Variables

Required environment variables:

```bash
# Firebase Configuration
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_CREDENTIALS_PATH=/path/to/serviceAccountKey.json

# Optional: Firebase Emulator (for development)
FIREBASE_AUTH_EMULATOR=true
FIREBASE_AUTH_EMULATOR_HOST=localhost:9099

# Database
DATABASE_URL=postgresql://user:pass@localhost/flexflow
```

---

## PromaFlex-Specific Rules

### Critical Business Rules Implemented:

1. **Personalized Items Validation**: PCP cannot approve if any item is personalized without attachments
2. **Mandatory PCP Rejection Path**: PCP rejections ALWAYS return to COMERCIAL
3. **Parallel States**: EXPEDICAO and FATURAMENTO must both complete before DESPACHO
4. **Permission-Based Authorization**: Fine-grained permissions for custom user profiles
5. **Audit Granularity**: State transitions with full validation messages in metadata

---

## Next Steps

1. **API Endpoints**: Create FastAPI routes using the workflow service
2. **Frontend Integration**: Connect React/Vue frontend to workflow API
3. **Notifications**: Add email/webhook notifications on state transitions
4. **Reports**: Generate workflow analytics and bottleneck reports
5. **Mobile App**: Extend API for mobile production tracking

---

## Support

For questions or issues:
- Review the state machine design: [`plans/state-machine-design.md`](plans/state-machine-design.md:1)
- Check test examples: [`backend/test_workflow.py`](backend/test_workflow.py:1)
- Refer to models: [`backend/models.py`](backend/models.py:1)
