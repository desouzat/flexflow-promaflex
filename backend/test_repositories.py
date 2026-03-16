"""
Test/Example file to verify repository implementation.

This file demonstrates how to use the repository layer with automatic
tenant filtering. It's not a full test suite, but shows the basic usage.
"""

from uuid import uuid4
from datetime import datetime
from backend.database import SessionLocal, init_db
from backend.models import PurchaseOrder, POItem, POStatus
from backend.repositories import PORepository


def example_usage():
    """
    Example of using the repository layer.
    
    This demonstrates:
    1. Creating a database session
    2. Initializing a repository with tenant_id
    3. Creating a PO with items
    4. Querying with automatic tenant filtering
    5. Updating and deleting operations
    """
    
    # Initialize database (create tables if they don't exist)
    # init_db()  # Uncomment to create tables
    
    # Create a database session
    db = SessionLocal()
    
    try:
        # Simulate tenant context (in real app, this comes from auth)
        tenant_id = uuid4()
        supplier_id = uuid4()
        
        # Initialize repository with tenant context
        po_repo = PORepository(db, tenant_id)
        
        print("=== Example 1: Create PO with Items ===")
        po_data = {
            "po_number": "PO-2024-001",
            "supplier_id": supplier_id,
            "order_date": datetime.now(),
            "status": POStatus.DRAFT,
            "total_value": 1500.00,
            "currency": "USD",
            "notes": "Test purchase order"
        }
        
        items_data = [
            {
                "item_code": "ITEM-001",
                "description": "Widget A",
                "quantity": 10,
                "unit_price": 100.00,
                "total_price": 1000.00
            },
            {
                "item_code": "ITEM-002",
                "description": "Widget B",
                "quantity": 5,
                "unit_price": 100.00,
                "total_price": 500.00
            }
        ]
        
        # Create PO with items (automatic tenant_id assignment)
        po = po_repo.create_with_items(po_data, items_data)
        print(f"Created PO: {po.po_number} with {len(po.items)} items")
        print(f"Tenant ID: {po.tenant_id}")
        
        print("\n=== Example 2: Get PO by ID (with tenant filter) ===")
        # This will only return the PO if it belongs to the tenant
        retrieved_po = po_repo.get_by_id_with_items(po.id)
        if retrieved_po:
            print(f"Retrieved PO: {retrieved_po.po_number}")
            print(f"Items: {len(retrieved_po.items)}")
        
        print("\n=== Example 3: Get PO by Number ===")
        po_by_number = po_repo.get_by_po_number("PO-2024-001")
        if po_by_number:
            print(f"Found PO: {po_by_number.po_number}")
        
        print("\n=== Example 4: Get POs by Status ===")
        draft_pos = po_repo.get_by_status(POStatus.DRAFT)
        print(f"Draft POs: {len(draft_pos)}")
        
        print("\n=== Example 5: Update PO ===")
        updated_po = po_repo.update(
            po.id,
            {"status": POStatus.APPROVED, "notes": "Updated notes"}
        )
        if updated_po:
            print(f"Updated PO status: {updated_po.status}")
        
        print("\n=== Example 6: Get Statistics ===")
        stats = po_repo.get_statistics()
        print(f"Total POs: {stats['total_count']}")
        print(f"Total Value: ${stats['total_value']:.2f}")
        print(f"By Status: {stats['by_status']}")
        
        print("\n=== Example 7: Search by Text ===")
        search_results = po_repo.search_by_text("Widget")
        print(f"Search results: {len(search_results)}")
        
        print("\n=== Example 8: Tenant Isolation Test ===")
        # Create another repository with different tenant_id
        other_tenant_id = uuid4()
        other_repo = PORepository(db, other_tenant_id)
        
        # Try to get the PO created by first tenant
        other_tenant_po = other_repo.get_by_id(po.id)
        if other_tenant_po is None:
            print("✓ Tenant isolation working: Other tenant cannot access PO")
        else:
            print("✗ Tenant isolation failed: Other tenant can access PO")
        
        print("\n=== Example 9: Delete PO ===")
        # Delete the PO (and its items via cascade)
        deleted = po_repo.delete_with_items(po.id)
        if deleted:
            print("✓ PO and items deleted successfully")
        
        # Verify deletion
        deleted_po = po_repo.get_by_id(po.id)
        if deleted_po is None:
            print("✓ PO no longer exists")
        
    finally:
        # Always close the session
        db.close()
        print("\n=== Session closed ===")


def example_base_repository():
    """
    Example of using BaseRepository directly for other models.
    
    This shows how to use the generic repository for any model.
    """
    from backend.repositories.base_repository import BaseRepository
    from backend.models import Supplier
    
    db = SessionLocal()
    tenant_id = uuid4()
    
    try:
        # Create a repository for Supplier model
        supplier_repo = BaseRepository(Supplier, db, tenant_id)
        
        print("\n=== BaseRepository Example ===")
        
        # Create a supplier
        supplier = Supplier(
            name="ACME Corp",
            contact_name="John Doe",
            email="john@acme.com",
            phone="+1234567890"
        )
        
        created_supplier = supplier_repo.create(supplier)
        print(f"Created supplier: {created_supplier.name}")
        print(f"Tenant ID: {created_supplier.tenant_id}")
        
        # Get all suppliers (filtered by tenant)
        all_suppliers = supplier_repo.get_all()
        print(f"Total suppliers for tenant: {len(all_suppliers)}")
        
        # Update supplier
        updated = supplier_repo.update(
            created_supplier.id,
            {"contact_name": "Jane Doe"}
        )
        if updated:
            print(f"Updated contact: {updated.contact_name}")
        
        # Delete supplier
        deleted = supplier_repo.delete(created_supplier.id)
        if deleted:
            print("✓ Supplier deleted")
        
    finally:
        db.close()


if __name__ == "__main__":
    print("FlexFlow Repository Layer - Usage Examples")
    print("=" * 50)
    print("\nNote: Uncomment init_db() to create tables first")
    print("=" * 50)
    
    # Run examples
    example_usage()
    example_base_repository()
    
    print("\n" + "=" * 50)
    print("Examples completed successfully!")
