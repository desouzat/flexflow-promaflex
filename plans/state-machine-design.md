# FlexFlow State Machine Design

## Overview
This document outlines the state machine logic for the FlexFlow workflow system, managing the transition of Purchase Orders through 6 distinct areas.

## State Flow Diagram

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

**Note:** After PRODUCAO, the workflow splits into two parallel tracks that must both be completed before DESPACHO can proceed.

## State Definitions

### 1. COMERCIAL (Commercial)
**Entry Requirements:** None (initial state)
**Exit Requirements:**
- PO must have at least one item
- Customer information must be complete
- Delivery date must be set

**Actions:**
- Create PO
- Add/Edit items
- Set customer details
- Set delivery expectations

**Transitions:**
- → PCP (on approval)

---

### 2. PCP (Production Planning & Control)
**Entry Requirements:**
- Approved by COMERCIAL

**Exit Requirements:**
- All items must be reviewed
- **CRITICAL:** If any item has `is_personalized = true`, it MUST have at least one attachment
- Production schedule must be defined
- Material availability confirmed

**Actions:**
- Review items
- Upload technical drawings/specifications for personalized items
- Schedule production
- Allocate resources

**Transitions:**
- → PRODUCAO (on approval)
- → COMERCIAL (on rejection - **MANDATORY: Always returns to COMERCIAL**)

---

### 3. PRODUCAO (Production)
**Entry Requirements:**
- Approved by PCP
- All personalized items have attachments

**Exit Requirements:**
- All items marked as produced
- Quality control passed
- Production notes documented

**Actions:**
- Update production status
- Add production notes
- Mark items as completed
- Quality checks

**Transitions:**
- → EXPEDICAO_PENDENTE + FATURAMENTO_PENDENTE (on approval - **parallel states**)

---

### 4. EXPEDICAO_PENDENTE (Shipping Pending)
**Entry Requirements:**
- Approved by PRODUCAO
- All items produced

**Exit Requirements:**
- Packing list created
- Shipping documentation complete
- Items ready for dispatch

**Actions:**
- Create packing list
- Prepare shipping documents
- Verify items for shipping

**Transitions:**
- → DESPACHO (when both EXPEDICAO_PENDENTE and FATURAMENTO_PENDENTE are complete)

**Parallel State:** Works independently alongside FATURAMENTO_PENDENTE

---

### 5. FATURAMENTO_PENDENTE (Invoicing Pending)
**Entry Requirements:**
- Approved by PRODUCAO
- All items produced

**Exit Requirements:**
- Invoice generated and attached
- Financial documentation complete
- Payment terms confirmed

**Actions:**
- Generate invoice
- Upload invoice attachment
- Confirm payment terms
- Financial validation

**Transitions:**
- → DESPACHO (when both EXPEDICAO_PENDENTE and FATURAMENTO_PENDENTE are complete)

**Parallel State:** Works independently alongside EXPEDICAO_PENDENTE

---

### 6. DESPACHO (Dispatch)
**Entry Requirements:**
- **BOTH** EXPEDICAO_PENDENTE and FATURAMENTO_PENDENTE completed
- Invoice attached
- Packing list created

**Exit Requirements:**
- Goods physically dispatched
- Tracking number assigned
- Customer notified

**Actions:**
- Record dispatch date/time
- Add tracking information
- Update delivery status
- Notify customer

**Transitions:**
- → CONCLUIDO (on completion)

---

### 7. CONCLUIDO (Completed)
**Entry Requirements:**
- Approved by DESPACHO
- Goods dispatched

**Exit Requirements:** None (final state)

**Actions:**
- Archive PO
- Generate reports
- Customer feedback (optional)

**Transitions:** None (terminal state)

---

## Validation Rules by State

### COMERCIAL → PCP
```python
def validate_comercial_to_pcp(po: PurchaseOrder) -> tuple[bool, str]:
    if not po.items or len(po.items) == 0:
        return False, "PO must have at least one item"
    
    if not po.customer_name or not po.customer_contact:
        return False, "Customer information is incomplete"
    
    if not po.delivery_date:
        return False, "Delivery date must be set"
    
    return True, "Validation passed"
```

### PCP → PRODUCAO
```python
def validate_pcp_to_producao(po: PurchaseOrder) -> tuple[bool, str]:
    # Check for personalized items without attachments
    for item in po.items:
        if item.is_personalized:
            if not po.attachments or len(po.attachments) == 0:
                return False, f"Personalized item '{item.description}' requires technical drawings/attachments"
    
    if not po.production_schedule_date:
        return False, "Production schedule must be defined"
    
    return True, "Validation passed"
```

### PRODUCAO → EXPEDICAO_PENDENTE + FATURAMENTO_PENDENTE
```python
def validate_producao_to_parallel_states(po: PurchaseOrder) -> tuple[bool, str]:
    # Check if all items are produced
    for item in po.items:
        if not item.production_completed:
            return False, f"Item '{item.description}' production not completed"
    
    if not po.quality_check_passed:
        return False, "Quality control must be completed"
    
    return True, "Validation passed - transitioning to parallel states"
```

### EXPEDICAO_PENDENTE → Complete
```python
def validate_expedicao_completion(po: PurchaseOrder) -> tuple[bool, str]:
    if not po.packing_list_generated:
        return False, "Packing list must be created"
    
    if not po.shipping_docs_complete:
        return False, "Shipping documentation must be complete"
    
    return True, "Shipping preparation completed"
```

### FATURAMENTO_PENDENTE → Complete
```python
def validate_faturamento_completion(po: PurchaseOrder) -> tuple[bool, str]:
    # Check for invoice attachment
    has_invoice = any(att.file_type == 'invoice' for att in po.attachments)
    if not has_invoice:
        return False, "Invoice must be generated and attached"
    
    if not po.payment_terms_confirmed:
        return False, "Payment terms must be confirmed"
    
    return True, "Invoicing completed"
```

### PARALLEL STATES → DESPACHO
```python
def validate_parallel_to_despacho(po: PurchaseOrder) -> tuple[bool, str]:
    # Both parallel states must be completed
    if not po.expedicao_completed:
        return False, "Shipping preparation (EXPEDICAO_PENDENTE) must be completed first"
    
    if not po.faturamento_completed:
        return False, "Invoicing (FATURAMENTO_PENDENTE) must be completed first"
    
    return True, "Both parallel states completed - ready for dispatch"
```

### DESPACHO → CONCLUIDO
```python
def validate_despacho_to_concluido(po: PurchaseOrder) -> tuple[bool, str]:
    if not po.dispatch_date:
        return False, "Dispatch date must be recorded"
    
    if not po.tracking_number:
        return False, "Tracking number must be assigned"
    
    return True, "Validation passed"
```

---

## Audit Trail Integration

Every state transition MUST generate an audit record with:
- Previous state
- New state
- User who performed the action
- Timestamp
- Validation results
- SHA-256 hash chaining (linking to previous audit record)

### Audit Record Structure
```python
{
    "tenant_id": "tenant_123",
    "entity_type": "purchase_order",
    "entity_id": "po_456",
    "action": "state_transition",
    "user_id": "user_789",
    "changes": {
        "status": {
            "from": "COMERCIAL",
            "to": "PCP"
        }
    },
    "metadata": {
        "validation_passed": true,
        "validation_message": "All requirements met",
        "ip_address": "192.168.1.1"
    },
    "previous_hash": "abc123...",
    "current_hash": "def456..."
}
```

---

## Rejection/Rollback Flow

**CRITICAL RULE:** PCP rejections ALWAYS return to COMERCIAL (source of input errors)

**Rejection Rules:**
- **PCP → COMERCIAL** (MANDATORY - commercial review needed for input errors)
- No other rejections allowed in the current implementation

**Rejection Requirements:**
- Reason must be provided (stored in audit metadata)
- Audit trail records the rejection with full context
- State restored to COMERCIAL
- Notification sent to commercial team

---

## Security & Multi-tenancy

### JWT Token Structure
```json
{
  "sub": "user_id_123",
  "tenant_id": "tenant_456",
  "email": "user@example.com",
  "role": "pcp_manager",
  "permissions": ["po.read", "po.approve_pcp"],
  "exp": 1234567890
}
```

### Permission Model (Permission-Based Authorization)
- `po.create` - Create new POs (COMERCIAL)
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

## Implementation Components

### 1. Security Module (`backend/security.py`)
- Firebase Auth integration
- JWT token validation
- Tenant/User context extraction
- Permission checking

### 2. Middleware (`backend/middleware.py`)
- Extract JWT from Authorization header
- Validate token with Firebase
- Inject `tenant_id` and `user_id` into request context
- Handle authentication errors

### 3. Workflow Service (`backend/services/workflow_service.py`)
- State machine implementation
- Validation logic for each transition
- Audit trail integration
- Permission enforcement
- Notification triggers

### 4. State Validators (`backend/services/validators.py`)
- Individual validation functions for each state transition
- Business rule enforcement
- Data integrity checks

---

## Questions for Approval

1. **State Flow:** Does the 6-state flow (COMERCIAL → PCP → PRODUCAO → EXPEDICAO → DESPACHO → CONCLUIDO) match your business process?

2. **PCP Validation:** The critical rule is "PCP cannot approve if item is personalized and has no attachments". Is this the correct interpretation?

3. **Rejection Flow:** Should rejections always go back one state, or should there be flexibility to reject to any previous state?

4. **Permissions:** Should permissions be role-based (e.g., "pcp_manager" role) or permission-based (e.g., "po.approve_pcp" permission)?

## PromaFlex-Specific Adjustments

### ✅ Implemented Changes:
1. **Parallel States:** PRODUCAO splits into EXPEDICAO_PENDENTE and FATURAMENTO_PENDENTE
2. **Mandatory PCP Rejection:** PCP rejections ALWAYS return to COMERCIAL
3. **Permission-Based Authorization:** Fine-grained permissions for custom profiles
4. **Audit Focus:** State transitions with validation messages in metadata

### State Tracking Fields Required in PurchaseOrder Model:
```python
# Add to PurchaseOrder model:
expedicao_completed: bool = False
faturamento_completed: bool = False
packing_list_generated: bool = False
shipping_docs_complete: bool = False
payment_terms_confirmed: bool = False
quality_check_passed: bool = False
```

Ready for implementation with PromaFlex specifications.
