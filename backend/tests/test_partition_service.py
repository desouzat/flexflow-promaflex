"""
Test Suite for Partition Service
Tests partition logic, freight calculations, and data integrity
"""

import pytest
from decimal import Decimal
from sqlalchemy.orm import Session
import uuid

from backend.services.partition_service import PartitionService, PartitionError
from backend.models import PurchaseOrder, OrderItem, Tenant, User


class TestPartitionService:
    """Test cases for PartitionService"""
    
    def test_suggest_partition_success(self, db_session, sample_po, sample_user):
        """Test successful partition suggestion by PCP"""
        service = PartitionService(db_session)
        
        reason = "Falta de matéria-prima para alguns itens. Prazo incompatível."
        
        result = service.suggest_partition(
            po_id=sample_po.id,
            reason=reason,
            user_id=sample_user.id,
            tenant_id=sample_user.tenant_id
        )
        
        assert result.status_macro == PurchaseOrder.STATUS_WAITING_COMMERCIAL_PARTITION
        assert result.partition_reason == reason
        assert result.id == sample_po.id
    
    def test_suggest_partition_invalid_reason(self, db_session, sample_po, sample_user):
        """Test partition suggestion with invalid reason (too short)"""
        service = PartitionService(db_session)
        
        with pytest.raises(PartitionError) as exc_info:
            service.suggest_partition(
                po_id=sample_po.id,
                reason="Curto",  # Too short
                user_id=sample_user.id,
                tenant_id=sample_user.tenant_id
            )
        
        assert exc_info.value.error_code == "INVALID_PARTITION_REASON"
    
    def test_suggest_partition_invalid_status(self, db_session, sample_user):
        """Test partition suggestion on PO with invalid status"""
        # Create PO in COMPLETED status
        po = PurchaseOrder(
            tenant_id=sample_user.tenant_id,
            po_number="TEST-COMPLETED",
            status_macro=PurchaseOrder.STATUS_COMPLETED,
            created_by=sample_user.id
        )
        db_session.add(po)
        db_session.commit()
        
        service = PartitionService(db_session)
        
        with pytest.raises(PartitionError) as exc_info:
            service.suggest_partition(
                po_id=po.id,
                reason="Valid reason here",
                user_id=sample_user.id,
                tenant_id=sample_user.tenant_id
            )
        
        assert exc_info.value.error_code == "INVALID_STATUS_FOR_PARTITION"
    
    def test_freight_calculation_proportional(self, db_session, sample_po_with_items, sample_user):
        """Test proportional freight calculation"""
        service = PartitionService(db_session)
        
        # Set shipping cost
        sample_po_with_items.shipping_cost = 100.00
        db_session.commit()
        
        # Select first item for ship now
        items_ship_now = [sample_po_with_items.items[0].id]
        
        freight_now, freight_later = service._calculate_freight_distribution(
            original_po=sample_po_with_items,
            items_ship_now=items_ship_now,
            freight_strategy='PROPORTIONAL',
            original_freight=Decimal('100.00'),
            manual_freight_now=None,
            manual_freight_later=None
        )
        
        # Verify freight is split proportionally
        assert freight_now + freight_later == Decimal('100.00')
        assert freight_now > 0
        assert freight_later > 0
    
    def test_freight_calculation_full_on_first(self, db_session, sample_po_with_items, sample_user):
        """Test full freight on first shipment"""
        service = PartitionService(db_session)
        
        items_ship_now = [sample_po_with_items.items[0].id]
        
        freight_now, freight_later = service._calculate_freight_distribution(
            original_po=sample_po_with_items,
            items_ship_now=items_ship_now,
            freight_strategy='FULL_ON_FIRST',
            original_freight=Decimal('100.00'),
            manual_freight_now=None,
            manual_freight_later=None
        )
        
        assert freight_now == Decimal('100.00')
        assert freight_later == Decimal('0.00')
    
    def test_freight_calculation_manual(self, db_session, sample_po_with_items, sample_user):
        """Test manual freight input"""
        service = PartitionService(db_session)
        
        items_ship_now = [sample_po_with_items.items[0].id]
        
        freight_now, freight_later = service._calculate_freight_distribution(
            original_po=sample_po_with_items,
            items_ship_now=items_ship_now,
            freight_strategy='MANUAL',
            original_freight=Decimal('100.00'),
            manual_freight_now=Decimal('60.00'),
            manual_freight_later=Decimal('40.00')
        )
        
        assert freight_now == Decimal('60.00')
        assert freight_later == Decimal('40.00')
    
    def test_execute_partition_success(self, db_session, sample_po_with_items, sample_user):
        """Test successful partition execution"""
        service = PartitionService(db_session)
        
        # First suggest partition
        sample_po_with_items.status_macro = PurchaseOrder.STATUS_WAITING_COMMERCIAL_PARTITION
        sample_po_with_items.partition_reason = "Test reason"
        sample_po_with_items.shipping_cost = 100.00
        db_session.commit()
        
        # Select first item for ship now
        items_ship_now = [sample_po_with_items.items[0].id]
        
        mother_po, child_po = service.execute_partition(
            po_id=sample_po_with_items.id,
            items_ship_now=items_ship_now,
            freight_strategy='PROPORTIONAL',
            user_id=sample_user.id,
            tenant_id=sample_user.tenant_id
        )
        
        # Verify Mother PO
        assert mother_po.po_number == f"{sample_po_with_items.po_number}-M"
        assert len(mother_po.items) == 1
        assert mother_po.status_macro == PurchaseOrder.STATUS_SUBMITTED
        
        # Verify Child PO
        assert child_po.po_number == f"{sample_po_with_items.po_number}-C"
        assert len(child_po.items) == len(sample_po_with_items.items) - 1
        assert child_po.status_macro == PurchaseOrder.STATUS_SUBMITTED
        assert child_po.parent_po_id == mother_po.id
        
        # Verify original PO is marked as partitioned
        db_session.refresh(sample_po_with_items)
        assert sample_po_with_items.is_partitioned == True
    
    def test_execute_partition_no_items_selected(self, db_session, sample_po_with_items, sample_user):
        """Test partition execution with no items selected"""
        service = PartitionService(db_session)
        
        sample_po_with_items.status_macro = PurchaseOrder.STATUS_WAITING_COMMERCIAL_PARTITION
        db_session.commit()
        
        with pytest.raises(PartitionError) as exc_info:
            service.execute_partition(
                po_id=sample_po_with_items.id,
                items_ship_now=[],  # No items
                freight_strategy='PROPORTIONAL',
                user_id=sample_user.id,
                tenant_id=sample_user.tenant_id
            )
        
        assert exc_info.value.error_code == "NO_ITEMS_SELECTED"
    
    def test_execute_partition_all_items_selected(self, db_session, sample_po_with_items, sample_user):
        """Test partition execution with all items selected"""
        service = PartitionService(db_session)
        
        sample_po_with_items.status_macro = PurchaseOrder.STATUS_WAITING_COMMERCIAL_PARTITION
        db_session.commit()
        
        # Select all items
        all_item_ids = [item.id for item in sample_po_with_items.items]
        
        with pytest.raises(PartitionError) as exc_info:
            service.execute_partition(
                po_id=sample_po_with_items.id,
                items_ship_now=all_item_ids,
                freight_strategy='PROPORTIONAL',
                user_id=sample_user.id,
                tenant_id=sample_user.tenant_id
            )
        
        assert exc_info.value.error_code == "ALL_ITEMS_SELECTED"
    
    def test_partition_no_orphan_items(self, db_session, sample_po_with_items, sample_user):
        """Test that partition doesn't create orphan items"""
        service = PartitionService(db_session)
        
        # Setup
        sample_po_with_items.status_macro = PurchaseOrder.STATUS_WAITING_COMMERCIAL_PARTITION
        sample_po_with_items.partition_reason = "Test"
        sample_po_with_items.shipping_cost = 100.00
        db_session.commit()
        
        original_item_count = len(sample_po_with_items.items)
        items_ship_now = [sample_po_with_items.items[0].id]
        
        # Execute partition
        mother_po, child_po = service.execute_partition(
            po_id=sample_po_with_items.id,
            items_ship_now=items_ship_now,
            freight_strategy='PROPORTIONAL',
            user_id=sample_user.id,
            tenant_id=sample_user.tenant_id
        )
        
        # Verify all items are accounted for
        total_new_items = len(mother_po.items) + len(child_po.items)
        assert total_new_items == original_item_count
        
        # Verify all items have original_item_id set
        for item in mother_po.items:
            assert item.original_item_id is not None
            assert item.partition_group == "SHIP_NOW"
        
        for item in child_po.items:
            assert item.original_item_id is not None
            assert item.partition_group == "SHIP_LATER"
    
    def test_get_partition_history(self, db_session, sample_po_with_items, sample_user):
        """Test partition history retrieval"""
        service = PartitionService(db_session)
        
        # Execute partition
        sample_po_with_items.status_macro = PurchaseOrder.STATUS_WAITING_COMMERCIAL_PARTITION
        sample_po_with_items.partition_reason = "Test"
        sample_po_with_items.shipping_cost = 100.00
        db_session.commit()
        
        items_ship_now = [sample_po_with_items.items[0].id]
        
        mother_po, child_po = service.execute_partition(
            po_id=sample_po_with_items.id,
            items_ship_now=items_ship_now,
            freight_strategy='PROPORTIONAL',
            user_id=sample_user.id,
            tenant_id=sample_user.tenant_id
        )
        
        # Get history for mother PO
        history = service.get_partition_history(
            po_id=mother_po.id,
            tenant_id=sample_user.tenant_id
        )
        
        assert history is not None
        assert history['po_id'] == str(mother_po.id)
        assert len(history['child_pos']) == 1
        assert history['child_pos'][0]['id'] == str(child_po.id)


# Fixtures
@pytest.fixture
def db_session():
    """Create a test database session"""
    # This would be implemented with your test database setup
    pass


@pytest.fixture
def sample_tenant(db_session):
    """Create a sample tenant"""
    tenant = Tenant(
        name="Test Company",
        cnpj="12.345.678/0001-90",
        is_active=True
    )
    db_session.add(tenant)
    db_session.commit()
    return tenant


@pytest.fixture
def sample_user(db_session, sample_tenant):
    """Create a sample user"""
    user = User(
        tenant_id=sample_tenant.id,
        name="Test User",
        email="test@example.com",
        hashed_password="hashed",
        role="PCP",
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def sample_po(db_session, sample_tenant, sample_user):
    """Create a sample purchase order"""
    po = PurchaseOrder(
        tenant_id=sample_tenant.id,
        po_number="TEST-001",
        status_macro=PurchaseOrder.STATUS_SUBMITTED,
        created_by=sample_user.id,
        shipping_cost=0.00
    )
    db_session.add(po)
    db_session.commit()
    return po


@pytest.fixture
def sample_po_with_items(db_session, sample_tenant, sample_user):
    """Create a purchase order with items"""
    po = PurchaseOrder(
        tenant_id=sample_tenant.id,
        po_number="TEST-002",
        status_macro=PurchaseOrder.STATUS_SUBMITTED,
        created_by=sample_user.id,
        shipping_cost=100.00
    )
    db_session.add(po)
    db_session.flush()
    
    # Add items
    for i in range(3):
        item = OrderItem(
            po_id=po.id,
            tenant_id=sample_tenant.id,
            sku=f"SKU-{i+1}",
            quantity=10,
            price=100.00,
            status_item=OrderItem.STATUS_PENDING
        )
        db_session.add(item)
    
    db_session.commit()
    db_session.refresh(po)
    return po


if __name__ == "__main__":
    print("Run tests with: pytest backend/tests/test_partition_service.py -v")
