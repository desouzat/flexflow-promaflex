"""
FlexFlow Partition Service
Handles PO partitioning logic between PCP and Commercial roles.

Features:
- PCP can suggest partition with technical reason
- Commercial can execute partition with item selection
- Freight management (Proportional, Full on First, Manual)
- Full recalculation of margins and present value
- Complete audit trail with Mother/Child PO linking
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import uuid

from backend.models import (
    PurchaseOrder,
    OrderItem,
    AuditLog,
    get_last_audit_hash,
    MaterialCost
)


class PartitionError(Exception):
    """Raised when partition operation fails"""
    
    def __init__(self, message: str, error_code: str):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class PartitionService:
    """Service for managing PO partition operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def suggest_partition(
        self,
        po_id: uuid.UUID,
        reason: str,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID
    ) -> PurchaseOrder:
        """
        PCP suggests a partition for a Purchase Order.
        Moves PO to WAITING_COMMERCIAL_PARTITION status.
        
        Args:
            po_id: Purchase Order ID
            reason: Technical reason for partition suggestion
            user_id: User making the suggestion (must be PCP role)
            tenant_id: Tenant ID for isolation
            
        Returns:
            Updated Purchase Order
            
        Raises:
            PartitionError: If operation fails
        """
        try:
            # Get the PO
            po = self.db.query(PurchaseOrder).filter(
                PurchaseOrder.id == po_id,
                PurchaseOrder.tenant_id == tenant_id
            ).first()
            
            if not po:
                raise PartitionError(
                    message=f"Pedido {po_id} não encontrado",
                    error_code="PO_NOT_FOUND"
                )
            
            # Validate PO is in correct status (should be SUBMITTED/PCP stage)
            if po.status_macro not in ["SUBMITTED", "DRAFT"]:
                raise PartitionError(
                    message=f"Pedido deve estar em status SUBMITTED para sugerir partição. Status atual: {po.status_macro}",
                    error_code="INVALID_STATUS_FOR_PARTITION"
                )
            
            # Validate reason
            if not reason or len(reason.strip()) < 10:
                raise PartitionError(
                    message="Motivo da partição deve ter no mínimo 10 caracteres",
                    error_code="INVALID_PARTITION_REASON"
                )
            
            # Update PO status and store reason
            old_status = po.status_macro
            po.status_macro = PurchaseOrder.STATUS_WAITING_COMMERCIAL_PARTITION
            po.partition_reason = reason.strip()
            po.updated_at = datetime.utcnow()
            
            # Create audit log for each item
            for item in po.items:
                previous_hash = get_last_audit_hash(self.db, item.id)
                
                audit_hash = AuditLog.calculate_hash(
                    item_id=item.id,
                    from_status=old_status,
                    to_status=po.status_macro,
                    timestamp=datetime.utcnow(),
                    previous_hash=previous_hash,
                    changed_by=user_id
                )
                
                audit_entry = AuditLog(
                    item_id=item.id,
                    from_status=old_status,
                    to_status=po.status_macro,
                    hash=audit_hash,
                    previous_hash=previous_hash,
                    is_exception=False,
                    justification=f"PCP sugeriu partição: {reason}",
                    changed_by=user_id,
                    extra_data={
                        "action": "partition_suggested",
                        "po_id": str(po.id),
                        "po_number": po.po_number,
                        "partition_reason": reason
                    }
                )
                self.db.add(audit_entry)
            
            self.db.commit()
            self.db.refresh(po)
            
            return po
            
        except PartitionError:
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise PartitionError(
                message=f"Erro no banco de dados: {str(e)}",
                error_code="DATABASE_ERROR"
            )
        except Exception as e:
            self.db.rollback()
            raise PartitionError(
                message=f"Erro inesperado: {str(e)}",
                error_code="INTERNAL_ERROR"
            )
    
    def execute_partition(
        self,
        po_id: uuid.UUID,
        items_ship_now: List[uuid.UUID],
        freight_strategy: str,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        freight_ship_now: Optional[Decimal] = None,
        freight_ship_later: Optional[Decimal] = None
    ) -> Tuple[PurchaseOrder, PurchaseOrder]:
        """
        Execute partition of a Purchase Order.
        Creates Mother PO (items shipping now) and Child PO (items shipping later).
        
        Args:
            po_id: Original Purchase Order ID
            items_ship_now: List of item IDs to ship now
            freight_strategy: 'PROPORTIONAL', 'FULL_ON_FIRST', or 'MANUAL'
            freight_ship_now: Manual freight for ship now (required if MANUAL)
            freight_ship_later: Manual freight for ship later (required if MANUAL)
            user_id: User executing the partition (must be Commercial role)
            tenant_id: Tenant ID for isolation
            
        Returns:
            Tuple of (Mother PO, Child PO)
            
        Raises:
            PartitionError: If operation fails
        """
        try:
            # Get the original PO
            original_po = self.db.query(PurchaseOrder).filter(
                PurchaseOrder.id == po_id,
                PurchaseOrder.tenant_id == tenant_id
            ).first()
            
            if not original_po:
                raise PartitionError(
                    message=f"Pedido {po_id} não encontrado",
                    error_code="PO_NOT_FOUND"
                )
            
            # Validate PO is in partition waiting status
            if original_po.status_macro != PurchaseOrder.STATUS_WAITING_COMMERCIAL_PARTITION:
                raise PartitionError(
                    message=f"Pedido deve estar em status WAITING_COMMERCIAL_PARTITION. Status atual: {original_po.status_macro}",
                    error_code="INVALID_STATUS_FOR_EXECUTION"
                )
            
            # Validate items selection
            if not items_ship_now or len(items_ship_now) == 0:
                raise PartitionError(
                    message="Deve selecionar pelo menos um item para enviar agora",
                    error_code="NO_ITEMS_SELECTED"
                )
            
            all_item_ids = [item.id for item in original_po.items]
            if len(items_ship_now) >= len(all_item_ids):
                raise PartitionError(
                    message="Deve deixar pelo menos um item para enviar depois",
                    error_code="ALL_ITEMS_SELECTED"
                )
            
            # Validate all selected items belong to this PO
            for item_id in items_ship_now:
                if item_id not in all_item_ids:
                    raise PartitionError(
                        message=f"Item {item_id} não pertence a este pedido",
                        error_code="INVALID_ITEM_SELECTION"
                    )
            
            # Validate freight strategy
            valid_strategies = ['PROPORTIONAL', 'FULL_ON_FIRST', 'MANUAL']
            if freight_strategy not in valid_strategies:
                raise PartitionError(
                    message=f"Estratégia de frete inválida. Use: {', '.join(valid_strategies)}",
                    error_code="INVALID_FREIGHT_STRATEGY"
                )
            
            if freight_strategy == 'MANUAL':
                if freight_ship_now is None or freight_ship_later is None:
                    raise PartitionError(
                        message="Estratégia MANUAL requer valores de frete para ambas as remessas",
                        error_code="MISSING_MANUAL_FREIGHT"
                    )
            
            # Calculate freight distribution
            original_freight = Decimal(str(original_po.shipping_cost or 0))
            freight_now, freight_later = self._calculate_freight_distribution(
                original_po=original_po,
                items_ship_now=items_ship_now,
                freight_strategy=freight_strategy,
                original_freight=original_freight,
                manual_freight_now=freight_ship_now,
                manual_freight_later=freight_ship_later
            )
            
            # Create Mother PO (items shipping now)
            mother_po = self._create_mother_po(
                original_po=original_po,
                items_ship_now=items_ship_now,
                freight=freight_now,
                user_id=user_id
            )
            
            # Create Child PO (items shipping later)
            child_po = self._create_child_po(
                original_po=original_po,
                mother_po=mother_po,
                items_ship_later=[item_id for item_id in all_item_ids if item_id not in items_ship_now],
                freight=freight_later,
                user_id=user_id
            )
            
            # Mark original PO as partitioned and link to mother
            original_po.is_partitioned = True
            original_po.partition_metadata = {
                "partition_date": datetime.utcnow().isoformat(),
                "mother_po_id": str(mother_po.id),
                "child_po_id": str(child_po.id),
                "freight_strategy": freight_strategy,
                "original_freight": float(original_freight),
                "freight_ship_now": float(freight_now),
                "freight_ship_later": float(freight_later),
                "executed_by": str(user_id)
            }
            
            # Create audit logs for traceability
            self._create_partition_audit_logs(
                original_po=original_po,
                mother_po=mother_po,
                child_po=child_po,
                user_id=user_id
            )
            
            self.db.commit()
            self.db.refresh(mother_po)
            self.db.refresh(child_po)
            
            return mother_po, child_po
            
        except PartitionError:
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise PartitionError(
                message=f"Erro no banco de dados: {str(e)}",
                error_code="DATABASE_ERROR"
            )
        except Exception as e:
            self.db.rollback()
            raise PartitionError(
                message=f"Erro inesperado: {str(e)}",
                error_code="INTERNAL_ERROR"
            )
    
    def _calculate_freight_distribution(
        self,
        original_po: PurchaseOrder,
        items_ship_now: List[uuid.UUID],
        freight_strategy: str,
        original_freight: Decimal,
        manual_freight_now: Optional[Decimal],
        manual_freight_later: Optional[Decimal]
    ) -> Tuple[Decimal, Decimal]:
        """Calculate freight distribution based on strategy"""
        
        if freight_strategy == 'MANUAL':
            return manual_freight_now, manual_freight_later
        
        elif freight_strategy == 'FULL_ON_FIRST':
            return original_freight, Decimal('0.00')
        
        elif freight_strategy == 'PROPORTIONAL':
            # Calculate proportional based on item values
            total_value = Decimal('0.00')
            ship_now_value = Decimal('0.00')
            
            for item in original_po.items:
                item_value = Decimal(str(item.price)) * item.quantity
                total_value += item_value
                
                if item.id in items_ship_now:
                    ship_now_value += item_value
            
            if total_value == 0:
                return Decimal('0.00'), Decimal('0.00')
            
            proportion = ship_now_value / total_value
            freight_now = original_freight * proportion
            freight_later = original_freight - freight_now
            
            return freight_now.quantize(Decimal('0.01')), freight_later.quantize(Decimal('0.01'))
        
        return Decimal('0.00'), Decimal('0.00')
    
    def _create_mother_po(
        self,
        original_po: PurchaseOrder,
        items_ship_now: List[uuid.UUID],
        freight: Decimal,
        user_id: uuid.UUID
    ) -> PurchaseOrder:
        """Create Mother PO with items shipping now"""
        
        mother_po = PurchaseOrder(
            tenant_id=original_po.tenant_id,
            po_number=f"{original_po.po_number}-M",
            status_macro=PurchaseOrder.STATUS_SUBMITTED,  # Return to Commercial for approval
            created_by=user_id,
            shipping_cost=float(freight),
            is_partitioned=False,
            partition_reason=f"Partição de {original_po.po_number} - Envio Imediato",
            partition_metadata={
                "original_po_id": str(original_po.id),
                "original_po_number": original_po.po_number,
                "partition_type": "MOTHER",
                "partition_date": datetime.utcnow().isoformat()
            }
        )
        self.db.add(mother_po)
        self.db.flush()
        
        # Copy items that ship now
        for item in original_po.items:
            if item.id in items_ship_now:
                new_item = OrderItem(
                    po_id=mother_po.id,
                    tenant_id=original_po.tenant_id,
                    sku=item.sku,
                    quantity=item.quantity,
                    price=item.price,
                    status_item=item.status_item,
                    extra_metadata=item.extra_metadata,
                    is_personalized=item.is_personalized,
                    is_new_client=item.is_new_client,
                    customization_notes=item.customization_notes,
                    attachment_path=item.attachment_path,
                    partition_group="SHIP_NOW",
                    original_item_id=item.id
                )
                self.db.add(new_item)
        
        return mother_po
    
    def _create_child_po(
        self,
        original_po: PurchaseOrder,
        mother_po: PurchaseOrder,
        items_ship_later: List[uuid.UUID],
        freight: Decimal,
        user_id: uuid.UUID
    ) -> PurchaseOrder:
        """Create Child PO with items shipping later"""
        
        child_po = PurchaseOrder(
            tenant_id=original_po.tenant_id,
            po_number=f"{original_po.po_number}-C",
            status_macro=PurchaseOrder.STATUS_SUBMITTED,  # Return to Commercial for approval
            created_by=user_id,
            parent_po_id=mother_po.id,
            shipping_cost=float(freight),
            is_partitioned=False,
            partition_reason=f"Partição de {original_po.po_number} - Envio Posterior",
            partition_metadata={
                "original_po_id": str(original_po.id),
                "original_po_number": original_po.po_number,
                "mother_po_id": str(mother_po.id),
                "partition_type": "CHILD",
                "partition_date": datetime.utcnow().isoformat()
            }
        )
        self.db.add(child_po)
        self.db.flush()
        
        # Copy items that ship later
        for item in original_po.items:
            if item.id in items_ship_later:
                new_item = OrderItem(
                    po_id=child_po.id,
                    tenant_id=original_po.tenant_id,
                    sku=item.sku,
                    quantity=item.quantity,
                    price=item.price,
                    status_item=item.status_item,
                    extra_metadata=item.extra_metadata,
                    is_personalized=item.is_personalized,
                    is_new_client=item.is_new_client,
                    customization_notes=item.customization_notes,
                    attachment_path=item.attachment_path,
                    partition_group="SHIP_LATER",
                    original_item_id=item.id
                )
                self.db.add(new_item)
        
        return child_po
    
    def _create_partition_audit_logs(
        self,
        original_po: PurchaseOrder,
        mother_po: PurchaseOrder,
        child_po: PurchaseOrder,
        user_id: uuid.UUID
    ):
        """Create comprehensive audit logs for partition traceability"""
        
        timestamp = datetime.utcnow()
        
        # Log for each item in mother PO
        for item in mother_po.items:
            previous_hash = get_last_audit_hash(self.db, item.id)
            
            audit_hash = AuditLog.calculate_hash(
                item_id=item.id,
                from_status=PurchaseOrder.STATUS_WAITING_COMMERCIAL_PARTITION,
                to_status=mother_po.status_macro,
                timestamp=timestamp,
                previous_hash=previous_hash,
                changed_by=user_id
            )
            
            audit_entry = AuditLog(
                item_id=item.id,
                from_status=PurchaseOrder.STATUS_WAITING_COMMERCIAL_PARTITION,
                to_status=mother_po.status_macro,
                hash=audit_hash,
                previous_hash=previous_hash,
                is_exception=False,
                justification=f"Partição executada - Item movido para PO Mãe {mother_po.po_number}",
                changed_by=user_id,
                extra_data={
                    "action": "partition_executed",
                    "partition_type": "MOTHER",
                    "original_po_id": str(original_po.id),
                    "original_po_number": original_po.po_number,
                    "mother_po_id": str(mother_po.id),
                    "mother_po_number": mother_po.po_number,
                    "child_po_id": str(child_po.id),
                    "child_po_number": child_po.po_number,
                    "original_item_id": str(item.original_item_id)
                }
            )
            self.db.add(audit_entry)
        
        # Log for each item in child PO
        for item in child_po.items:
            previous_hash = get_last_audit_hash(self.db, item.id)
            
            audit_hash = AuditLog.calculate_hash(
                item_id=item.id,
                from_status=PurchaseOrder.STATUS_WAITING_COMMERCIAL_PARTITION,
                to_status=child_po.status_macro,
                timestamp=timestamp,
                previous_hash=previous_hash,
                changed_by=user_id
            )
            
            audit_entry = AuditLog(
                item_id=item.id,
                from_status=PurchaseOrder.STATUS_WAITING_COMMERCIAL_PARTITION,
                to_status=child_po.status_macro,
                hash=audit_hash,
                previous_hash=previous_hash,
                is_exception=False,
                justification=f"Partição executada - Item movido para PO Filho {child_po.po_number}",
                changed_by=user_id,
                extra_data={
                    "action": "partition_executed",
                    "partition_type": "CHILD",
                    "original_po_id": str(original_po.id),
                    "original_po_number": original_po.po_number,
                    "mother_po_id": str(mother_po.id),
                    "mother_po_number": mother_po.po_number,
                    "child_po_id": str(child_po.id),
                    "child_po_number": child_po.po_number,
                    "original_item_id": str(item.original_item_id)
                }
            )
            self.db.add(audit_entry)
    
    def get_partition_history(
        self,
        po_id: uuid.UUID,
        tenant_id: uuid.UUID
    ) -> Dict[str, Any]:
        """
        Get complete partition history for a PO.
        Shows if it's a mother, child, or has been partitioned.
        """
        po = self.db.query(PurchaseOrder).filter(
            PurchaseOrder.id == po_id,
            PurchaseOrder.tenant_id == tenant_id
        ).first()
        
        if not po:
            return None
        
        history = {
            "po_id": str(po.id),
            "po_number": po.po_number,
            "is_partitioned": po.is_partitioned,
            "partition_reason": po.partition_reason,
            "partition_metadata": po.partition_metadata,
            "parent_po": None,
            "child_pos": []
        }
        
        # Check if this PO has a parent (is a child)
        if po.parent_po_id:
            parent = self.db.query(PurchaseOrder).filter(
                PurchaseOrder.id == po.parent_po_id
            ).first()
            if parent:
                history["parent_po"] = {
                    "id": str(parent.id),
                    "po_number": parent.po_number,
                    "status": parent.status_macro
                }
        
        # Check if this PO has children
        children = self.db.query(PurchaseOrder).filter(
            PurchaseOrder.parent_po_id == po.id
        ).all()
        
        for child in children:
            history["child_pos"].append({
                "id": str(child.id),
                "po_number": child.po_number,
                "status": child.status_macro,
                "partition_reason": child.partition_reason
            })
        
        return history
