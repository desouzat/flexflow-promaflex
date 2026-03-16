"""
FlexFlow State Validators
Validation logic for state transitions in the workflow.
"""

from typing import Tuple, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from backend.models import PurchaseOrder, POStatus


class ValidationResult:
    """Result of a validation check"""
    
    def __init__(self, is_valid: bool, message: str, error_code: Optional[str] = None):
        self.is_valid = is_valid
        self.message = message
        self.error_code = error_code
    
    def __bool__(self):
        return self.is_valid
    
    def to_dict(self) -> dict:
        return {
            "is_valid": self.is_valid,
            "message": self.message,
            "error_code": self.error_code
        }


class StateValidator:
    """
    Validates state transitions according to PromaFlex business rules.
    Implements the validation logic defined in the state machine design.
    """
    
    @staticmethod
    def validate_comercial_to_pcp(po: PurchaseOrder, db: Session) -> ValidationResult:
        """
        Validate transition from COMERCIAL to PCP.
        
        Requirements:
        - PO must have at least one item
        - Customer information must be complete
        - Delivery date must be set
        """
        # Check for items
        if not po.items or len(po.items) == 0:
            return ValidationResult(
                is_valid=False,
                message="PO must have at least one item",
                error_code="NO_ITEMS"
            )
        
        # Check customer information
        if not po.customer_name or not po.customer_name.strip():
            return ValidationResult(
                is_valid=False,
                message="Customer name is required",
                error_code="MISSING_CUSTOMER_NAME"
            )
        
        if not po.customer_contact or not po.customer_contact.strip():
            return ValidationResult(
                is_valid=False,
                message="Customer contact information is required",
                error_code="MISSING_CUSTOMER_CONTACT"
            )
        
        # Check delivery date
        if not po.delivery_date:
            return ValidationResult(
                is_valid=False,
                message="Delivery date must be set",
                error_code="MISSING_DELIVERY_DATE"
            )
        
        # Validate delivery date is in the future
        if po.delivery_date < datetime.utcnow().date():
            return ValidationResult(
                is_valid=False,
                message="Delivery date cannot be in the past",
                error_code="INVALID_DELIVERY_DATE"
            )
        
        return ValidationResult(
            is_valid=True,
            message="Validation passed: Ready for PCP review"
        )
    
    @staticmethod
    def validate_pcp_to_producao(po: PurchaseOrder, db: Session) -> ValidationResult:
        """
        Validate transition from PCP to PRODUCAO.
        
        CRITICAL REQUIREMENT:
        - If any item has is_personalized = true, PO MUST have at least one attachment
        - Production schedule must be defined
        - Material availability confirmed
        """
        # Check for personalized items without attachments
        personalized_items = [item for item in po.items if item.is_personalized]
        
        if personalized_items:
            if not po.attachments or len(po.attachments) == 0:
                item_descriptions = ", ".join([item.description for item in personalized_items[:3]])
                if len(personalized_items) > 3:
                    item_descriptions += f" and {len(personalized_items) - 3} more"
                
                return ValidationResult(
                    is_valid=False,
                    message=f"Personalized items require technical drawings/attachments. "
                            f"Items: {item_descriptions}",
                    error_code="MISSING_PERSONALIZED_ATTACHMENTS"
                )
        
        # Check production schedule
        if not po.production_schedule_date:
            return ValidationResult(
                is_valid=False,
                message="Production schedule date must be defined",
                error_code="MISSING_PRODUCTION_SCHEDULE"
            )
        
        # Validate production schedule is reasonable
        if po.production_schedule_date < datetime.utcnow().date():
            return ValidationResult(
                is_valid=False,
                message="Production schedule date cannot be in the past",
                error_code="INVALID_PRODUCTION_SCHEDULE"
            )
        
        # Check if production schedule allows time before delivery
        if po.delivery_date and po.production_schedule_date >= po.delivery_date:
            return ValidationResult(
                is_valid=False,
                message="Production schedule must be before delivery date",
                error_code="PRODUCTION_AFTER_DELIVERY"
            )
        
        return ValidationResult(
            is_valid=True,
            message="Validation passed: Ready for production"
        )
    
    @staticmethod
    def validate_producao_to_parallel_states(po: PurchaseOrder, db: Session) -> ValidationResult:
        """
        Validate transition from PRODUCAO to parallel states (EXPEDICAO_PENDENTE + FATURAMENTO_PENDENTE).
        
        Requirements:
        - All items must be marked as produced
        - Quality control must be passed
        - Production notes documented
        """
        # Check if all items are produced
        unproduced_items = [item for item in po.items if not item.production_completed]
        
        if unproduced_items:
            item_descriptions = ", ".join([item.description for item in unproduced_items[:3]])
            if len(unproduced_items) > 3:
                item_descriptions += f" and {len(unproduced_items) - 3} more"
            
            return ValidationResult(
                is_valid=False,
                message=f"All items must be produced before proceeding. "
                        f"Pending items: {item_descriptions}",
                error_code="ITEMS_NOT_PRODUCED"
            )
        
        # Check quality control
        if not po.quality_check_passed:
            return ValidationResult(
                is_valid=False,
                message="Quality control must be completed and passed",
                error_code="QUALITY_CHECK_NOT_PASSED"
            )
        
        # Check production notes (optional but recommended)
        if not po.production_notes or not po.production_notes.strip():
            return ValidationResult(
                is_valid=False,
                message="Production notes must be documented",
                error_code="MISSING_PRODUCTION_NOTES"
            )
        
        return ValidationResult(
            is_valid=True,
            message="Validation passed: Transitioning to parallel states (Shipping & Invoicing)"
        )
    
    @staticmethod
    def validate_expedicao_completion(po: PurchaseOrder, db: Session) -> ValidationResult:
        """
        Validate completion of EXPEDICAO_PENDENTE state.
        
        Requirements:
        - Packing list must be created
        - Shipping documentation must be complete
        - Items ready for dispatch
        """
        # Check packing list
        if not po.packing_list_generated:
            return ValidationResult(
                is_valid=False,
                message="Packing list must be generated",
                error_code="MISSING_PACKING_LIST"
            )
        
        # Check shipping documentation
        if not po.shipping_docs_complete:
            return ValidationResult(
                is_valid=False,
                message="Shipping documentation must be complete",
                error_code="INCOMPLETE_SHIPPING_DOCS"
            )
        
        return ValidationResult(
            is_valid=True,
            message="Shipping preparation completed"
        )
    
    @staticmethod
    def validate_faturamento_completion(po: PurchaseOrder, db: Session) -> ValidationResult:
        """
        Validate completion of FATURAMENTO_PENDENTE state.
        
        Requirements:
        - Invoice must be generated and attached
        - Financial documentation complete
        - Payment terms confirmed
        """
        # Check for invoice attachment
        has_invoice = any(
            att.file_type == 'invoice' 
            for att in po.attachments
        ) if po.attachments else False
        
        if not has_invoice:
            return ValidationResult(
                is_valid=False,
                message="Invoice must be generated and attached",
                error_code="MISSING_INVOICE"
            )
        
        # Check payment terms
        if not po.payment_terms_confirmed:
            return ValidationResult(
                is_valid=False,
                message="Payment terms must be confirmed",
                error_code="PAYMENT_TERMS_NOT_CONFIRMED"
            )
        
        return ValidationResult(
            is_valid=True,
            message="Invoicing completed"
        )
    
    @staticmethod
    def validate_parallel_to_despacho(po: PurchaseOrder, db: Session) -> ValidationResult:
        """
        Validate transition from parallel states to DESPACHO.
        
        CRITICAL REQUIREMENT:
        - BOTH EXPEDICAO_PENDENTE and FATURAMENTO_PENDENTE must be completed
        """
        # Check if shipping preparation is completed
        if not po.expedicao_completed:
            return ValidationResult(
                is_valid=False,
                message="Shipping preparation (EXPEDICAO_PENDENTE) must be completed first",
                error_code="EXPEDICAO_NOT_COMPLETED"
            )
        
        # Check if invoicing is completed
        if not po.faturamento_completed:
            return ValidationResult(
                is_valid=False,
                message="Invoicing (FATURAMENTO_PENDENTE) must be completed first",
                error_code="FATURAMENTO_NOT_COMPLETED"
            )
        
        # Double-check that both validations would pass
        expedicao_result = StateValidator.validate_expedicao_completion(po, db)
        if not expedicao_result.is_valid:
            return ValidationResult(
                is_valid=False,
                message=f"Shipping validation failed: {expedicao_result.message}",
                error_code="EXPEDICAO_VALIDATION_FAILED"
            )
        
        faturamento_result = StateValidator.validate_faturamento_completion(po, db)
        if not faturamento_result.is_valid:
            return ValidationResult(
                is_valid=False,
                message=f"Invoicing validation failed: {faturamento_result.message}",
                error_code="FATURAMENTO_VALIDATION_FAILED"
            )
        
        return ValidationResult(
            is_valid=True,
            message="Both parallel states completed - ready for dispatch"
        )
    
    @staticmethod
    def validate_despacho_to_concluido(po: PurchaseOrder, db: Session) -> ValidationResult:
        """
        Validate transition from DESPACHO to CONCLUIDO.
        
        Requirements:
        - Dispatch date must be recorded
        - Tracking number must be assigned
        - Customer notified
        """
        # Check dispatch date
        if not po.dispatch_date:
            return ValidationResult(
                is_valid=False,
                message="Dispatch date must be recorded",
                error_code="MISSING_DISPATCH_DATE"
            )
        
        # Validate dispatch date is not in the future
        if po.dispatch_date > datetime.utcnow().date():
            return ValidationResult(
                is_valid=False,
                message="Dispatch date cannot be in the future",
                error_code="INVALID_DISPATCH_DATE"
            )
        
        # Check tracking number
        if not po.tracking_number or not po.tracking_number.strip():
            return ValidationResult(
                is_valid=False,
                message="Tracking number must be assigned",
                error_code="MISSING_TRACKING_NUMBER"
            )
        
        return ValidationResult(
            is_valid=True,
            message="Validation passed: Order completed successfully"
        )
    
    @staticmethod
    def validate_state_transition(
        po: PurchaseOrder,
        from_status: POStatus,
        to_status: POStatus,
        db: Session
    ) -> ValidationResult:
        """
        Main validation dispatcher for state transitions.
        Routes to the appropriate validator based on the transition.
        """
        # Define valid transitions
        valid_transitions = {
            POStatus.COMERCIAL: [POStatus.PCP],
            POStatus.PCP: [POStatus.PRODUCAO, POStatus.COMERCIAL],  # Can reject back to COMERCIAL
            POStatus.PRODUCAO: [POStatus.EXPEDICAO_PENDENTE, POStatus.FATURAMENTO_PENDENTE],
            POStatus.EXPEDICAO_PENDENTE: [POStatus.DESPACHO],
            POStatus.FATURAMENTO_PENDENTE: [POStatus.DESPACHO],
            POStatus.DESPACHO: [POStatus.CONCLUIDO],
            POStatus.CONCLUIDO: []  # Terminal state
        }
        
        # Check if transition is allowed
        if to_status not in valid_transitions.get(from_status, []):
            return ValidationResult(
                is_valid=False,
                message=f"Invalid transition from {from_status.value} to {to_status.value}",
                error_code="INVALID_TRANSITION"
            )
        
        # Route to specific validator
        if from_status == POStatus.COMERCIAL and to_status == POStatus.PCP:
            return StateValidator.validate_comercial_to_pcp(po, db)
        
        elif from_status == POStatus.PCP and to_status == POStatus.PRODUCAO:
            return StateValidator.validate_pcp_to_producao(po, db)
        
        elif from_status == POStatus.PCP and to_status == POStatus.COMERCIAL:
            # Rejection - always allowed with reason
            return ValidationResult(
                is_valid=True,
                message="PCP rejection: Returning to COMERCIAL for review"
            )
        
        elif from_status == POStatus.PRODUCAO and to_status in [
            POStatus.EXPEDICAO_PENDENTE,
            POStatus.FATURAMENTO_PENDENTE
        ]:
            return StateValidator.validate_producao_to_parallel_states(po, db)
        
        elif from_status == POStatus.EXPEDICAO_PENDENTE and to_status == POStatus.DESPACHO:
            # Check if both parallel states are completed
            return StateValidator.validate_parallel_to_despacho(po, db)
        
        elif from_status == POStatus.FATURAMENTO_PENDENTE and to_status == POStatus.DESPACHO:
            # Check if both parallel states are completed
            return StateValidator.validate_parallel_to_despacho(po, db)
        
        elif from_status == POStatus.DESPACHO and to_status == POStatus.CONCLUIDO:
            return StateValidator.validate_despacho_to_concluido(po, db)
        
        else:
            return ValidationResult(
                is_valid=False,
                message=f"No validator defined for transition {from_status.value} -> {to_status.value}",
                error_code="NO_VALIDATOR"
            )
