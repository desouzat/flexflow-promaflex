"""
Purchase Order repository with specialized operations.

This module provides a repository for PurchaseOrder entities with
specialized methods for handling POs and their related items.
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func
from datetime import datetime

from backend.models import PurchaseOrder, POItem, POStatus
from backend.repositories.base_repository import BaseRepository


class PORepository(BaseRepository[PurchaseOrder]):
    """
    Repository for PurchaseOrder operations.
    
    Extends BaseRepository with specialized methods for handling
    purchase orders and their related items, with automatic tenant filtering.
    """
    
    def __init__(self, db: Session, tenant_id: UUID):
        """
        Initialize the PO repository.
        
        Args:
            db: Database session
            tenant_id: UUID of the tenant for filtering operations
        """
        super().__init__(PurchaseOrder, db, tenant_id)
    
    def get_by_id_with_items(self, id: UUID) -> Optional[PurchaseOrder]:
        """
        Get a purchase order by ID with all its items eagerly loaded.
        
        Args:
            id: UUID of the purchase order
            
        Returns:
            PurchaseOrder instance with items loaded, or None if not found
        """
        query = (
            self.db.query(self.model)
            .options(joinedload(PurchaseOrder.items))
            .filter(self.model.id == id)
        )
        return self._apply_tenant_filter(query).first()
    
    def get_all_with_items(
        self,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[PurchaseOrder]:
        """
        Get all purchase orders with their items eagerly loaded.
        
        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            filters: Optional dictionary of field:value filters
            
        Returns:
            List of PurchaseOrder instances with items loaded
        """
        query = (
            self.db.query(self.model)
            .options(joinedload(PurchaseOrder.items))
        )
        query = self._apply_tenant_filter(query)
        
        # Apply additional filters if provided
        if filters:
            for field, value in filters.items():
                if hasattr(self.model, field):
                    query = query.filter(getattr(self.model, field) == value)
        
        return query.offset(skip).limit(limit).all()
    
    def get_by_po_number(self, po_number: str) -> Optional[PurchaseOrder]:
        """
        Get a purchase order by its PO number.
        
        Args:
            po_number: The purchase order number
            
        Returns:
            PurchaseOrder instance if found, None otherwise
        """
        return self.get_by_field("po_number", po_number)
    
    def get_by_status(
        self,
        status: POStatus,
        skip: int = 0,
        limit: int = 100
    ) -> List[PurchaseOrder]:
        """
        Get purchase orders by status.
        
        Args:
            status: The PO status to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of PurchaseOrder instances
        """
        return self.get_many_by_field("status", status, skip, limit)
    
    def get_by_supplier(
        self,
        supplier_id: UUID,
        skip: int = 0,
        limit: int = 100
    ) -> List[PurchaseOrder]:
        """
        Get purchase orders for a specific supplier.
        
        Args:
            supplier_id: UUID of the supplier
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of PurchaseOrder instances
        """
        return self.get_many_by_field("supplier_id", supplier_id, skip, limit)
    
    def get_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        skip: int = 0,
        limit: int = 100
    ) -> List[PurchaseOrder]:
        """
        Get purchase orders within a date range.
        
        Args:
            start_date: Start of the date range
            end_date: End of the date range
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of PurchaseOrder instances
        """
        query = self.db.query(self.model).filter(
            and_(
                self.model.order_date >= start_date,
                self.model.order_date <= end_date
            )
        )
        query = self._apply_tenant_filter(query)
        
        return query.offset(skip).limit(limit).all()
    
    def get_pending_delivery(
        self,
        skip: int = 0,
        limit: int = 100
    ) -> List[PurchaseOrder]:
        """
        Get purchase orders pending delivery (approved but not received).
        
        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of PurchaseOrder instances
        """
        query = self.db.query(self.model).filter(
            self.model.status.in_([POStatus.APPROVED, POStatus.PARTIALLY_RECEIVED])
        )
        query = self._apply_tenant_filter(query)
        
        return query.offset(skip).limit(limit).all()
    
    def search_by_text(
        self,
        search_text: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[PurchaseOrder]:
        """
        Search purchase orders by text in po_number or notes.
        
        Args:
            search_text: Text to search for
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of PurchaseOrder instances matching the search
        """
        search_pattern = f"%{search_text}%"
        query = self.db.query(self.model).filter(
            or_(
                self.model.po_number.ilike(search_pattern),
                self.model.notes.ilike(search_pattern)
            )
        )
        query = self._apply_tenant_filter(query)
        
        return query.offset(skip).limit(limit).all()
    
    def get_total_value_by_status(self, status: POStatus) -> float:
        """
        Calculate total value of purchase orders by status.
        
        Args:
            status: The PO status to filter by
            
        Returns:
            Total value as float
        """
        query = (
            self.db.query(func.sum(self.model.total_value))
            .filter(self.model.status == status)
        )
        query = self._apply_tenant_filter(query)
        
        result = query.scalar()
        return float(result) if result else 0.0
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about purchase orders for the tenant.
        
        Returns:
            Dictionary with statistics including counts by status and total values
        """
        base_query = self.db.query(self.model)
        base_query = self._apply_tenant_filter(base_query)
        
        stats = {
            "total_count": base_query.count(),
            "by_status": {},
            "total_value": 0.0,
            "value_by_status": {}
        }
        
        # Count and sum by status
        for status in POStatus:
            status_query = base_query.filter(self.model.status == status)
            count = status_query.count()
            total = status_query.with_entities(
                func.sum(self.model.total_value)
            ).scalar()
            
            stats["by_status"][status.value] = count
            stats["value_by_status"][status.value] = float(total) if total else 0.0
        
        # Calculate total value
        total_value = base_query.with_entities(
            func.sum(self.model.total_value)
        ).scalar()
        stats["total_value"] = float(total_value) if total_value else 0.0
        
        return stats
    
    def create_with_items(
        self,
        po_data: Dict[str, Any],
        items_data: List[Dict[str, Any]]
    ) -> PurchaseOrder:
        """
        Create a purchase order with its items in a single transaction.
        
        Args:
            po_data: Dictionary with PurchaseOrder fields
            items_data: List of dictionaries with POItem fields
            
        Returns:
            Created PurchaseOrder instance with items
        """
        # Create PO instance
        po = PurchaseOrder(**po_data)
        po.tenant_id = self.tenant_id
        
        # Create item instances
        items = []
        for item_data in items_data:
            item = POItem(**item_data)
            item.tenant_id = self.tenant_id
            items.append(item)
        
        # Associate items with PO
        po.items = items
        
        # Save to database
        self.db.add(po)
        self.db.commit()
        self.db.refresh(po)
        
        return po
    
    def update_with_items(
        self,
        po_id: UUID,
        po_data: Dict[str, Any],
        items_data: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[PurchaseOrder]:
        """
        Update a purchase order and optionally replace its items.
        
        Args:
            po_id: UUID of the purchase order to update
            po_data: Dictionary with PurchaseOrder fields to update
            items_data: Optional list of dictionaries with POItem fields
                       If provided, existing items will be replaced
            
        Returns:
            Updated PurchaseOrder instance if found, None otherwise
        """
        po = self.get_by_id_with_items(po_id)
        if not po:
            return None
        
        # Update PO fields
        for field, value in po_data.items():
            if hasattr(po, field) and field not in ["id", "tenant_id", "items"]:
                setattr(po, field, value)
        
        # Replace items if provided
        if items_data is not None:
            # Delete existing items
            for item in po.items:
                self.db.delete(item)
            
            # Create new items
            new_items = []
            for item_data in items_data:
                item = POItem(**item_data)
                item.tenant_id = self.tenant_id
                item.purchase_order_id = po.id
                new_items.append(item)
            
            po.items = new_items
        
        self.db.commit()
        self.db.refresh(po)
        
        return po
    
    def delete_with_items(self, po_id: UUID) -> bool:
        """
        Delete a purchase order and all its items.
        
        Args:
            po_id: UUID of the purchase order to delete
            
        Returns:
            True if deleted, False if not found
        """
        po = self.get_by_id_with_items(po_id)
        if not po:
            return False
        
        # Items will be deleted automatically due to cascade
        self.db.delete(po)
        self.db.commit()
        
        return True
