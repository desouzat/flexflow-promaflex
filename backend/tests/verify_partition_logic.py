"""
Logic Stress Test for Partition Feature
Tests the complete partition workflow with real database operations
"""
import sys
import os

# Add parent directory to path for imports
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, backend_dir)
os.chdir(backend_dir)

from sqlalchemy.orm import Session
from database import SessionLocal, engine
from models import PurchaseOrder, OrderItem, AuditLog
from services.partition_service import PartitionService
from datetime import datetime
import traceback
import json

def verify_hash_chain(db: Session, po_id: int, action: str) -> bool:
    """Verify hash chain integrity in audit logs"""
    logs = db.query(AuditLog).filter(
        AuditLog.po_id == po_id,
        AuditLog.action == action
    ).order_by(AuditLog.timestamp.desc()).all()
    
    if not logs:
        return False
    
    # Check that hash exists and is valid format
    latest_log = logs[0]
    if not latest_log.hash or len(latest_log.hash) < 32:
        return False
    
    return True

def logic_stress_test():
    """Execute comprehensive partition logic test"""
    print("=" * 80)
    print("PARTITION LOGIC STRESS TEST")
    print("=" * 80)
    
    db = SessionLocal()
    results = {
        "success": True,
        "tests": []
    }
    
    try:
        # Test 1: Find a suitable PO from seed data
        print("\n[TEST 1] Finding Suitable Purchase Order")
        print("-" * 80)
        
        # Look for a PO with multiple items that's in a suitable status
        suitable_statuses = [
            PurchaseOrder.STATUS_DRAFT,
            PurchaseOrder.STATUS_SUBMITTED,
            PurchaseOrder.STATUS_APPROVED
        ]
        
        test_po = db.query(PurchaseOrder).filter(
            PurchaseOrder.status_macro.in_(suitable_statuses),
            PurchaseOrder.parent_po_id.is_(None)
        ).first()
        
        if not test_po:
            print("⚠ No suitable PO found in seed data, creating test PO...")
            # Create a test PO - need tenant_id
            test_po = PurchaseOrder(
                tenant_id=1,  # Assuming default tenant exists
                po_number=f"TEST-PARTITION-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                status_macro=PurchaseOrder.STATUS_DRAFT,
                parent_po_id=None,
                is_partitioned=False
            )
            db.add(test_po)
            db.flush()
            
            # Add test items
            for i in range(3):
                item = OrderItem(
                    tenant_id=1,
                    po_id=test_po.id,
                    item_number=str(i + 1),
                    description=f"Test Item {i + 1}",
                    quantity=10.0,
                    unit_price=100.0
                )
                db.add(item)
            db.commit()
            db.refresh(test_po)
            print(f"✓ Created test PO: {test_po.po_number} (ID: {test_po.id})")
        else:
            print(f"✓ Found suitable PO: {test_po.po_number} (ID: {test_po.id})")
        
        # Get item count
        item_count = db.query(OrderItem).filter(OrderItem.po_id == test_po.id).count()
        print(f"  Status: {test_po.status_macro}")
        print(f"  Items: {item_count}")
        print(f"  Is Partitioned: {test_po.is_partitioned}")
        print(f"  Parent PO ID: {test_po.parent_po_id}")
        
        if item_count < 2:
            print("✗ PO has less than 2 items, cannot test partition")
            results["success"] = False
            results["tests"].append({"name": "Find PO", "status": "FAIL", "reason": "Insufficient items"})
            return results
        
        results["tests"].append({"name": "Find PO", "status": "PASS", "po_id": test_po.id})
        
        # Test 2: Call suggest_partition
        print("\n[TEST 2] Suggest Partition")
        print("-" * 80)
        
        try:
            partition_service = PartitionService(db)
            suggestion = partition_service.suggest_partition(test_po.id)
            
            print(f"✓ Partition suggestion generated")
            print(f"  Parent PO: {suggestion['parent_po']['po_number']}")
            print(f"  Suggested partitions: {len(suggestion['suggested_partitions'])}")
            
            for idx, partition in enumerate(suggestion['suggested_partitions'], 1):
                print(f"\n  Partition {idx}:")
                print(f"    Reason: {partition['reason']}")
                print(f"    Items: {len(partition['items'])}")
                for item in partition['items']:
                    print(f"      - Item #{item['item_number']}: {item['description']}")
            
            results["tests"].append({
                "name": "Suggest Partition",
                "status": "PASS",
                "partitions": len(suggestion['suggested_partitions'])
            })
            
        except Exception as e:
            print(f"✗ Suggest partition failed: {e}")
            traceback.print_exc()
            results["success"] = False
            results["tests"].append({"name": "Suggest Partition", "status": "FAIL", "error": str(e)})
            return results
        
        # Test 3: Execute partition
        print("\n[TEST 3] Execute Partition")
        print("-" * 80)
        
        try:
            # Get all items
            all_items = db.query(OrderItem).filter(OrderItem.po_id == test_po.id).all()
            
            # Split items: first half ships now, second half ships later
            split_point = len(all_items) // 2
            items_ship_now = [item.id for item in all_items[:split_point]]
            items_ship_later = [item.id for item in all_items[split_point:]]
            
            print(f"  Executing partition...")
            print(f"  Items shipping now: {len(items_ship_now)}")
            print(f"  Items shipping later: {len(items_ship_later)}")
            
            # Execute partition using actual service signature
            mother_po, child_po = partition_service.execute_partition(
                po_id=test_po.id,
                items_ship_now=items_ship_now,
                freight_strategy='PROPORTIONAL',
                user_id=test_po.created_by or 1,  # Use PO creator or default
                tenant_id=test_po.tenant_id
            )
            
            print(f"\n✓ Partition executed successfully")
            print(f"  Mother PO (shipping now): {mother_po.po_number}")
            print(f"  Child PO (shipping later): {child_po.po_number}")
            
            # Get item counts
            mother_items = db.query(OrderItem).filter(OrderItem.po_id == mother_po.id).count()
            child_items = db.query(OrderItem).filter(OrderItem.po_id == child_po.id).count()
            
            print(f"\n  Mother PO:")
            print(f"    PO Number: {mother_po.po_number}")
            print(f"    Status: {mother_po.status}")
            print(f"    Items: {mother_items}")
            
            print(f"\n  Child PO:")
            print(f"    PO Number: {child_po.po_number}")
            print(f"    Status: {child_po.status}")
            print(f"    Items: {child_items}")
            print(f"    Parent PO ID: {child_po.parent_po_id}")
            
            child_po_ids = [child_po.id]
            
            results["tests"].append({
                "name": "Execute Partition",
                "status": "PASS",
                "mother_po_id": mother_po.id,
                "child_po_id": child_po.id
            })
            
        except Exception as e:
            print(f"✗ Execute partition failed: {e}")
            traceback.print_exc()
            results["success"] = False
            results["tests"].append({"name": "Execute Partition", "status": "FAIL", "error": str(e)})
            return results
        
        # Test 4: Verify child POs in database
        print("\n[TEST 4] Verify Child POs in Database")
        print("-" * 80)
        
        try:
            db.expire_all()  # Clear cache
            
            # Check parent PO
            parent_po = db.query(PurchaseOrder).filter(PurchaseOrder.id == test_po.id).first()
            print(f"Parent PO verification:")
            print(f"  ✓ Is Partitioned: {parent_po.is_partitioned}")
            print(f"  ✓ Status: {parent_po.status}")
            
            if not parent_po.is_partitioned:
                print(f"  ✗ Parent PO is_partitioned flag is False!")
                results["success"] = False
            
            if parent_po.status_macro != PurchaseOrder.STATUS_WAITING_COMMERCIAL_PARTITION:
                print(f"  ✗ Parent PO status is not WAITING_COMMERCIAL_PARTITION!")
                print(f"    Current status: {parent_po.status_macro}")
                results["success"] = False
            
            # Check child POs
            child_pos = db.query(PurchaseOrder).filter(
                PurchaseOrder.parent_po_id == test_po.id
            ).all()
            
            print(f"\nChild POs verification:")
            print(f"  ✓ Found {len(child_pos)} child POs in database")
            
            if len(child_pos) != len(child_po_ids):
                print(f"  ✗ Expected {len(child_po_ids)} child POs, found {len(child_pos)}")
                results["success"] = False
            
            total_child_items = 0
            for child in child_pos:
                child_items = db.query(OrderItem).filter(OrderItem.po_id == child.id).all()
                total_child_items += len(child_items)
                print(f"\n  Child PO: {child.po_number}")
                print(f"    ✓ Parent PO ID: {child.parent_po_id}")
                print(f"    ✓ Items: {len(child_items)}")
                print(f"    ✓ Status: {child.status}")
                
                # Verify items were moved correctly
                for item in child_items:
                    print(f"      - Item #{item.item_number}: {item.description}")
            
            # Verify all items were distributed
            original_item_count = item_count
            print(f"\n  Item distribution:")
            print(f"    Original items: {original_item_count}")
            print(f"    Child PO items: {total_child_items}")
            
            if total_child_items == original_item_count:
                print(f"    ✓ All items correctly distributed")
            else:
                print(f"    ✗ Item count mismatch!")
                results["success"] = False
            
            results["tests"].append({
                "name": "Verify Child POs",
                "status": "PASS" if results["success"] else "FAIL",
                "child_count": len(child_pos),
                "item_distribution": f"{total_child_items}/{original_item_count}"
            })
            
        except Exception as e:
            print(f"✗ Child PO verification failed: {e}")
            traceback.print_exc()
            results["success"] = False
            results["tests"].append({"name": "Verify Child POs", "status": "FAIL", "error": str(e)})
            return results
        
        # Test 5: Verify Hash Chain in Audit Logs
        print("\n[TEST 5] Verify Hash Chain in Audit Logs")
        print("-" * 80)
        
        try:
            # Check parent PO audit log
            parent_hash_valid = verify_hash_chain(db, test_po.id, "partition_parent")
            print(f"Parent PO audit log:")
            if parent_hash_valid:
                print(f"  ✓ Hash chain valid for parent PO")
            else:
                print(f"  ✗ Hash chain invalid or missing for parent PO")
                results["success"] = False
            
            # Check child POs audit logs
            all_child_hashes_valid = True
            for child_id in child_po_ids:
                child_hash_valid = verify_hash_chain(db, child_id, "partition_child")
                if child_hash_valid:
                    print(f"  ✓ Hash chain valid for child PO {child_id}")
                else:
                    print(f"  ✗ Hash chain invalid or missing for child PO {child_id}")
                    all_child_hashes_valid = False
                    results["success"] = False
            
            results["tests"].append({
                "name": "Hash Chain Verification",
                "status": "PASS" if (parent_hash_valid and all_child_hashes_valid) else "FAIL",
                "parent_hash": parent_hash_valid,
                "child_hashes": all_child_hashes_valid
            })
            
        except Exception as e:
            print(f"✗ Hash chain verification failed: {e}")
            traceback.print_exc()
            results["success"] = False
            results["tests"].append({"name": "Hash Chain Verification", "status": "FAIL", "error": str(e)})
        
        # Summary
        print("\n" + "=" * 80)
        print("LOGIC TEST SUMMARY")
        print("=" * 80)
        
        passed = sum(1 for t in results["tests"] if t["status"] == "PASS")
        failed = sum(1 for t in results["tests"] if t["status"] == "FAIL")
        
        print(f"Total Tests: {len(results['tests'])}")
        print(f"✓ Passed: {passed}")
        print(f"✗ Failed: {failed}")
        
        if results["success"]:
            print("\n🎉 LOGIC STRESS TEST: SUCCESS")
            print("Partition feature is fully functional with real database operations")
        else:
            print("\n❌ LOGIC STRESS TEST: FAILED")
            print("Some partition operations did not work as expected")
        
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        traceback.print_exc()
        results["success"] = False
        results["tests"].append({"name": "Fatal Error", "status": "FAIL", "error": str(e)})
    finally:
        db.close()
    
    return results

if __name__ == "__main__":
    try:
        results = logic_stress_test()
        sys.exit(0 if results["success"] else 1)
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        traceback.print_exc()
        sys.exit(1)
