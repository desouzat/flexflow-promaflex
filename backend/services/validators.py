"""
FlexFlow State Validators
=========================
Validation logic for state transitions in the workflow.

HARDENING CLEANUP NOTE (Hardening Step 3 — Task I):
----------------------------------------------------
The original StateValidator class (v1) was removed because:

  1. DEAD CODE: No active router or service currently invokes StateValidator
     or validate_state_transition(). The `workflow_service.py` that imported
     it also references non-existent model symbols (POStatus, POItem,
     POAttachment, customer_name, production_schedule_date, quality_check_passed,
     packing_list_generated, shipping_docs_complete, etc.) — indicating the
     entire workflow_service / validators pair was aspirational scaffolding
     never wired to the live API.

  2. IMPORT ERROR: `from backend.models import PurchaseOrder, POStatus` would
     raise ImportError at startup because `POStatus` was never added to
     models.py (the live code uses string constants like STATUS_DRAFT = "DRAFT").

  3. BROKEN ATTRIBUTE REFERENCES: All validator methods accessed fields that
     do not exist on the current PurchaseOrder ORM model (e.g., po.customer_name,
     po.production_schedule_date, po.quality_check_passed, po.packing_list_generated,
     po.payment_terms_confirmed, po.dispatch_date, po.tracking_number,
     po.expedicao_completed, po.faturamento_completed, po.attachments).

ValidationResult is retained because:
  - It is a lightweight, dependency-free data class.
  - It may be re-used by future workflow validators with no migration cost.
  - The import in workflow_service.py will continue to resolve cleanly.

Next steps:
  - When the workflow API is ready, re-implement StateValidator against
    the actual PurchaseOrder schema and wire it into an active router.
  - Consider using a proper state machine library (e.g., `transitions`)
    to enforce the state graph declaratively.
"""

from typing import Optional


class ValidationResult:
    """
    Result of a state-transition validation check.

    Usage:
        result = ValidationResult(is_valid=True, message="OK")
        if not result:
            raise ValueError(result.message)
    """

    def __init__(
        self,
        is_valid: bool,
        message: str,
        error_code: Optional[str] = None
    ):
        self.is_valid = is_valid
        self.message = message
        self.error_code = error_code

    def __bool__(self) -> bool:
        return self.is_valid

    def __repr__(self) -> str:
        return (
            f"ValidationResult(is_valid={self.is_valid!r}, "
            f"message={self.message!r}, error_code={self.error_code!r})"
        )

    def to_dict(self) -> dict:
        return {
            "is_valid": self.is_valid,
            "message": self.message,
            "error_code": self.error_code
        }
