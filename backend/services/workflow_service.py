"""
FlexFlow Workflow Service
Implements the state machine for Purchase Order workflow with audit trail integration.
"""

import hashlib
import json
from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from backend.models import (
    PurchaseOrder,
    POStatus,
    AuditLog,
    POItem,
    POAttachment
)
from backend.repositories.po_repository import PORepository
from backend.services.validators import StateValidator, ValidationResult
from backend.middleware import RequestContext


class WorkflowTransitionError(Exception):
    """Raised when a workflow transition fails"""
    
    def __init__(self, message: str, error_code: str, validation_result: Optional[ValidationResult] = None):
        self.message = message
        self.error_code = error_code
        self.validation_result = validation_result
        super().__init__(self.message)


class WorkflowService:
    """
    Service for managing Purchase Order workflow state transitions.
    Integrates validation, audit trail, and SHA-256 hash chaining.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.po_repository = PORepository(db)
        self.validator = StateValidator()
    
    async def transition_state(
        self,
        po_id: str,
        to_status: POStatus,
        context: RequestContext,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> PurchaseOrder:
        """
        Transition a Purchase Order to a new state.
        
        Args:
            po_id: Purchase Order ID
            to_status: Target status
            context: Request context with user and tenant info
            reason: Optional reason for transition (required for rejections)
            metadata: Optional additional metadata
            
        Returns:
            Updated Purchase Order
            
        Raises:
            WorkflowTransitionError: If transition is invalid or validation fails
        """
        try:
            # Get the PO
            po = self.po_repository.get_by_id(po_id, context.tenant_id)
            if not po:
                raise WorkflowTransitionError(
                    message=f"Purchase Order {po_id} not found",
                    error_code="PO_NOT_FOUND"
                )
            
            from_status = po.status
            
            # Check if already in target state
            if from_status == to_status:
                raise WorkflowTransitionError(
                    message=f"Purchase Order is already in {to_status.value} state",
                    error_code="ALREADY_IN_STATE"
                )
            
            # Validate the transition
            validation_result = self.validator.validate_state_transition(
                po=po,
                from_status=from_status,
                to_status=to_status,
                db=self.db
            )
            
            if not validation_result.is_valid:
                raise WorkflowTransitionError(
                    message=validation_result.message,
                    error_code=validation_result.error_code or "VALIDATION_FAILED",
                    validation_result=validation_result
                )
            
            # Handle special cases for parallel states
            if to_status == POStatus.EXPEDICAO_PENDENTE:
                # Also transition to FATURAMENTO_PENDENTE
                po.status = POStatus.EXPEDICAO_PENDENTE
                # Note: In a real implementation, you might want to track both states separately
                # For now, we'll use flags to track completion
                po.expedicao_completed = False
                po.faturamento_completed = False
            
            elif to_status == POStatus.FATURAMENTO_PENDENTE:
                # This should happen automatically with EXPEDICAO_PENDENTE
                # But allow manual transition if needed
                po.status = POStatus.FATURAMENTO_PENDENTE
                po.expedicao_completed = False
                po.faturamento_completed = False
            
            else:
                # Normal state transition
                po.status = to_status
            
            # Update timestamp
            po.updated_at = datetime.utcnow()
            
            # Create audit log entry
            audit_log = await self._create_audit_log(
                po=po,
                from_status=from_status,
                to_status=to_status,
                context=context,
                validation_result=validation_result,
                reason=reason,
                metadata=metadata
            )
            
            # Commit changes
            self.db.commit()
            self.db.refresh(po)
            
            return po
            
        except WorkflowTransitionError:
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise WorkflowTransitionError(
                message=f"Database error during transition: {str(e)}",
                error_code="DATABASE_ERROR"
            )
        except Exception as e:
            self.db.rollback()
            raise WorkflowTransitionError(
                message=f"Unexpected error during transition: {str(e)}",
                error_code="INTERNAL_ERROR"
            )
    
    async def approve_comercial(
        self,
        po_id: str,
        context: RequestContext,
        metadata: Optional[Dict[str, Any]] = None
    ) -> PurchaseOrder:
        """Approve COMERCIAL and transition to PCP"""
        return await self.transition_state(
            po_id=po_id,
            to_status=POStatus.PCP,
            context=context,
            reason="Approved by commercial team",
            metadata=metadata
        )
    
    async def approve_pcp(
        self,
        po_id: str,
        context: RequestContext,
        metadata: Optional[Dict[str, Any]] = None
    ) -> PurchaseOrder:
        """Approve PCP and transition to PRODUCAO"""
        return await self.transition_state(
            po_id=po_id,
            to_status=POStatus.PRODUCAO,
            context=context,
            reason="Approved by PCP team",
            metadata=metadata
        )
    
    async def reject_pcp(
        self,
        po_id: str,
        context: RequestContext,
        reason: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> PurchaseOrder:
        """
        Reject PCP and return to COMERCIAL.
        MANDATORY: PCP rejections always return to COMERCIAL.
        """
        if not reason or not reason.strip():
            raise WorkflowTransitionError(
                message="Rejection reason is required",
                error_code="MISSING_REJECTION_REASON"
            )
        
        return await self.transition_state(
            po_id=po_id,
            to_status=POStatus.COMERCIAL,
            context=context,
            reason=f"PCP Rejection: {reason}",
            metadata=metadata
        )
    
    async def approve_producao(
        self,
        po_id: str,
        context: RequestContext,
        metadata: Optional[Dict[str, Any]] = None
    ) -> PurchaseOrder:
        """
        Approve PRODUCAO and transition to parallel states.
        This initiates both EXPEDICAO_PENDENTE and FATURAMENTO_PENDENTE.
        """
        po = await self.transition_state(
            po_id=po_id,
            to_status=POStatus.EXPEDICAO_PENDENTE,
            context=context,
            reason="Production completed - transitioning to parallel states",
            metadata=metadata
        )
        
        # Set both parallel state flags
        po.expedicao_completed = False
        po.faturamento_completed = False
        self.db.commit()
        self.db.refresh(po)
        
        return po
    
    async def complete_expedicao(
        self,
        po_id: str,
        context: RequestContext,
        metadata: Optional[Dict[str, Any]] = None
    ) -> PurchaseOrder:
        """
        Complete EXPEDICAO_PENDENTE state.
        If FATURAMENTO_PENDENTE is also complete, transition to DESPACHO.
        """
        try:
            po = self.po_repository.get_by_id(po_id, context.tenant_id)
            if not po:
                raise WorkflowTransitionError(
                    message=f"Purchase Order {po_id} not found",
                    error_code="PO_NOT_FOUND"
                )
            
            # Validate expedicao completion
            validation_result = self.validator.validate_expedicao_completion(po, self.db)
            if not validation_result.is_valid:
                raise WorkflowTransitionError(
                    message=validation_result.message,
                    error_code=validation_result.error_code or "VALIDATION_FAILED",
                    validation_result=validation_result
                )
            
            # Mark expedicao as completed
            po.expedicao_completed = True
            po.updated_at = datetime.utcnow()
            
            # Create audit log
            await self._create_audit_log(
                po=po,
                from_status=po.status,
                to_status=po.status,  # Same state, just marking completion
                context=context,
                validation_result=validation_result,
                reason="EXPEDICAO_PENDENTE completed",
                metadata={**(metadata or {}), "parallel_state_completion": "expedicao"}
            )
            
            # Check if both parallel states are complete
            if po.expedicao_completed and po.faturamento_completed:
                # Transition to DESPACHO
                return await self.transition_state(
                    po_id=po_id,
                    to_status=POStatus.DESPACHO,
                    context=context,
                    reason="Both parallel states completed",
                    metadata=metadata
                )
            
            self.db.commit()
            self.db.refresh(po)
            return po
            
        except WorkflowTransitionError:
            self.db.rollback()
            raise
        except Exception as e:
            self.db.rollback()
            raise WorkflowTransitionError(
                message=f"Error completing expedicao: {str(e)}",
                error_code="INTERNAL_ERROR"
            )
    
    async def complete_faturamento(
        self,
        po_id: str,
        context: RequestContext,
        metadata: Optional[Dict[str, Any]] = None
    ) -> PurchaseOrder:
        """
        Complete FATURAMENTO_PENDENTE state.
        If EXPEDICAO_PENDENTE is also complete, transition to DESPACHO.
        """
        try:
            po = self.po_repository.get_by_id(po_id, context.tenant_id)
            if not po:
                raise WorkflowTransitionError(
                    message=f"Purchase Order {po_id} not found",
                    error_code="PO_NOT_FOUND"
                )
            
            # Validate faturamento completion
            validation_result = self.validator.validate_faturamento_completion(po, self.db)
            if not validation_result.is_valid:
                raise WorkflowTransitionError(
                    message=validation_result.message,
                    error_code=validation_result.error_code or "VALIDATION_FAILED",
                    validation_result=validation_result
                )
            
            # Mark faturamento as completed
            po.faturamento_completed = True
            po.updated_at = datetime.utcnow()
            
            # Create audit log
            await self._create_audit_log(
                po=po,
                from_status=po.status,
                to_status=po.status,  # Same state, just marking completion
                context=context,
                validation_result=validation_result,
                reason="FATURAMENTO_PENDENTE completed",
                metadata={**(metadata or {}), "parallel_state_completion": "faturamento"}
            )
            
            # Check if both parallel states are complete
            if po.expedicao_completed and po.faturamento_completed:
                # Transition to DESPACHO
                return await self.transition_state(
                    po_id=po_id,
                    to_status=POStatus.DESPACHO,
                    context=context,
                    reason="Both parallel states completed",
                    metadata=metadata
                )
            
            self.db.commit()
            self.db.refresh(po)
            return po
            
        except WorkflowTransitionError:
            self.db.rollback()
            raise
        except Exception as e:
            self.db.rollback()
            raise WorkflowTransitionError(
                message=f"Error completing faturamento: {str(e)}",
                error_code="INTERNAL_ERROR"
            )
    
    async def complete_despacho(
        self,
        po_id: str,
        context: RequestContext,
        metadata: Optional[Dict[str, Any]] = None
    ) -> PurchaseOrder:
        """Complete DESPACHO and transition to CONCLUIDO"""
        return await self.transition_state(
            po_id=po_id,
            to_status=POStatus.CONCLUIDO,
            context=context,
            reason="Order dispatched and completed",
            metadata=metadata
        )
    
    async def _create_audit_log(
        self,
        po: PurchaseOrder,
        from_status: POStatus,
        to_status: POStatus,
        context: RequestContext,
        validation_result: ValidationResult,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AuditLog:
        """
        Create an audit log entry with SHA-256 hash chaining.
        
        The hash chain ensures audit trail integrity:
        - Each audit record includes the hash of the previous record
        - Any tampering breaks the chain
        - Provides cryptographic proof of audit trail integrity
        """
        # Get the previous audit log for this PO to chain hashes
        previous_audit = (
            self.db.query(AuditLog)
            .filter(
                AuditLog.tenant_id == context.tenant_id,
                AuditLog.entity_type == "purchase_order",
                AuditLog.entity_id == po.id
            )
            .order_by(AuditLog.created_at.desc())
            .first()
        )
        
        previous_hash = previous_audit.current_hash if previous_audit else "genesis"
        
        # Prepare changes dictionary
        changes = {
            "status": {
                "from": from_status.value,
                "to": to_status.value
            }
        }
        
        # Prepare metadata
        audit_metadata = {
            "validation_passed": validation_result.is_valid,
            "validation_message": validation_result.message,
            "validation_error_code": validation_result.error_code,
            "ip_address": context.ip_address,
            "reason": reason,
            **(metadata or {})
        }
        
        # Create audit log entry
        audit_log = AuditLog(
            tenant_id=context.tenant_id,
            entity_type="purchase_order",
            entity_id=po.id,
            action="state_transition",
            user_id=context.user_id,
            changes=changes,
            metadata=audit_metadata,
            previous_hash=previous_hash
        )
        
        # Calculate current hash (SHA-256)
        # Hash includes: previous_hash + tenant_id + entity_id + action + changes + timestamp
        hash_data = {
            "previous_hash": previous_hash,
            "tenant_id": audit_log.tenant_id,
            "entity_type": audit_log.entity_type,
            "entity_id": audit_log.entity_id,
            "action": audit_log.action,
            "user_id": audit_log.user_id,
            "changes": audit_log.changes,
            "metadata": audit_log.metadata,
            "timestamp": audit_log.created_at.isoformat()
        }
        
        hash_string = json.dumps(hash_data, sort_keys=True, default=str)
        current_hash = hashlib.sha256(hash_string.encode()).hexdigest()
        
        audit_log.current_hash = current_hash
        
        # Save audit log
        self.db.add(audit_log)
        self.db.flush()  # Flush to get the ID without committing
        
        return audit_log
    
    def verify_audit_chain(self, po_id: str, tenant_id: str) -> Dict[str, Any]:
        """
        Verify the integrity of the audit chain for a Purchase Order.
        
        Returns:
            Dictionary with verification results:
            - is_valid: bool
            - total_records: int
            - verified_records: int
            - broken_at: Optional[int] (index where chain breaks)
            - details: List of verification details
        """
        # Get all audit logs for this PO in chronological order
        audit_logs = (
            self.db.query(AuditLog)
            .filter(
                AuditLog.tenant_id == tenant_id,
                AuditLog.entity_type == "purchase_order",
                AuditLog.entity_id == po_id
            )
            .order_by(AuditLog.created_at.asc())
            .all()
        )
        
        if not audit_logs:
            return {
                "is_valid": True,
                "total_records": 0,
                "verified_records": 0,
                "broken_at": None,
                "details": []
            }
        
        is_valid = True
        verified_records = 0
        broken_at = None
        details = []
        
        for i, audit_log in enumerate(audit_logs):
            # Verify hash
            hash_data = {
                "previous_hash": audit_log.previous_hash,
                "tenant_id": audit_log.tenant_id,
                "entity_type": audit_log.entity_type,
                "entity_id": audit_log.entity_id,
                "action": audit_log.action,
                "user_id": audit_log.user_id,
                "changes": audit_log.changes,
                "metadata": audit_log.metadata,
                "timestamp": audit_log.created_at.isoformat()
            }
            
            hash_string = json.dumps(hash_data, sort_keys=True, default=str)
            calculated_hash = hashlib.sha256(hash_string.encode()).hexdigest()
            
            is_record_valid = calculated_hash == audit_log.current_hash
            
            if is_record_valid:
                verified_records += 1
            else:
                is_valid = False
                if broken_at is None:
                    broken_at = i
            
            details.append({
                "index": i,
                "audit_id": audit_log.id,
                "timestamp": audit_log.created_at.isoformat(),
                "action": audit_log.action,
                "is_valid": is_record_valid,
                "stored_hash": audit_log.current_hash,
                "calculated_hash": calculated_hash
            })
        
        return {
            "is_valid": is_valid,
            "total_records": len(audit_logs),
            "verified_records": verified_records,
            "broken_at": broken_at,
            "details": details
        }
    
    def get_workflow_history(self, po_id: str, tenant_id: str) -> list[Dict[str, Any]]:
        """
        Get the complete workflow history for a Purchase Order.
        
        Returns:
            List of workflow transitions with details
        """
        audit_logs = (
            self.db.query(AuditLog)
            .filter(
                AuditLog.tenant_id == tenant_id,
                AuditLog.entity_type == "purchase_order",
                AuditLog.entity_id == po_id,
                AuditLog.action == "state_transition"
            )
            .order_by(AuditLog.created_at.asc())
            .all()
        )
        
        history = []
        for audit_log in audit_logs:
            history.append({
                "timestamp": audit_log.created_at.isoformat(),
                "user_id": audit_log.user_id,
                "from_status": audit_log.changes.get("status", {}).get("from"),
                "to_status": audit_log.changes.get("status", {}).get("to"),
                "validation_message": audit_log.metadata.get("validation_message"),
                "reason": audit_log.metadata.get("reason"),
                "ip_address": audit_log.metadata.get("ip_address")
            })
        
        return history
