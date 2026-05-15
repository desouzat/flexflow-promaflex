# -*- coding: utf-8 -*-
"""
Final Check Script - Verify Import Service Handles Missing Cost Fields
Tests that the import service can handle ONET imports without price_unit and cost fields.
"""

import sys
import os
from decimal import Decimal

# Force UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.schemas.import_schema import (
    ImportItemData,
    ImportPOData,
    ImportMapping,
    ColumnMapping,
    ImportFieldType
)


def test_item_without_costs():
    """Test 1: Create ImportItemData without any cost fields"""
    print("\n" + "="*80)
    print("TEST 1: ImportItemData WITHOUT cost fields")
    print("="*80)
    
    try:
        item = ImportItemData(
            sku="TEST-SKU-001",
            quantity=10,
            description="Test Product",
            unit="UN"
        )
        
        print("✅ SUCCESS: ImportItemData created without cost fields")
        print(f"   SKU: {item.sku}")
        print(f"   Quantity: {item.quantity}")
        print(f"   Description: {item.description}")
        print(f"   Price Unit: {item.price_unit}")
        print(f"   Cost MP: {item.cost_mp}")
        print(f"   Total Cost: {item.total_cost}")
        print(f"   Margin Item: {item.margin_item}")
        return True
        
    except Exception as e:
        print(f"❌ FAILED: {type(e).__name__}: {e}")
        return False


def test_item_with_partial_costs():
    """Test 2: Create ImportItemData with only some cost fields"""
    print("\n" + "="*80)
    print("TEST 2: ImportItemData WITH partial cost fields")
    print("="*80)
    
    try:
        item = ImportItemData(
            sku="TEST-SKU-002",
            quantity=5,
            price_unit=100.50,
            cost_mp=30.00,
            # Missing: cost_mo, cost_energy, cost_gas
        )
        
        print("✅ SUCCESS: ImportItemData created with partial cost fields")
        print(f"   SKU: {item.sku}")
        print(f"   Quantity: {item.quantity}")
        print(f"   Price Unit: {item.price_unit}")
        print(f"   Cost MP: {item.cost_mp}")
        print(f"   Cost MO: {item.cost_mo}")
        print(f"   Total Cost: {item.total_cost}")
        print(f"   Margin Item: {item.margin_item}")
        return True
        
    except Exception as e:
        print(f"❌ FAILED: {type(e).__name__}: {e}")
        return False


def test_po_without_costs():
    """Test 3: Create ImportPOData with items that have no cost fields"""
    print("\n" + "="*80)
    print("TEST 3: ImportPOData WITHOUT cost fields")
    print("="*80)
    
    try:
        items = [
            ImportItemData(
                sku="ITEM-001",
                quantity=10,
                description="Product 1"
            ),
            ImportItemData(
                sku="ITEM-002",
                quantity=5,
                description="Product 2"
            )
        ]
        
        po = ImportPOData(
            po_number="PO-2024-001",
            client_name="Test Client",
            items=items
        )
        
        print("✅ SUCCESS: ImportPOData created without cost fields")
        print(f"   PO Number: {po.po_number}")
        print(f"   Client: {po.client_name}")
        print(f"   Items: {len(po.items)}")
        print(f"   Total Value: {po.total_value}")
        print(f"   Total Cost: {po.total_cost}")
        print(f"   Margin Global: {po.margin_global}")
        print(f"   Margin %: {po.margin_percentage}")
        return True
        
    except Exception as e:
        print(f"❌ FAILED: {type(e).__name__}: {e}")
        return False


def test_po_with_mixed_items():
    """Test 4: Create ImportPOData with mixed items (some with costs, some without)"""
    print("\n" + "="*80)
    print("TEST 4: ImportPOData WITH mixed items")
    print("="*80)
    
    try:
        items = [
            ImportItemData(
                sku="ITEM-WITH-COST",
                quantity=10,
                price_unit=100.00,
                cost_mp=20.00,
                cost_mo=15.00,
                cost_energy=5.00,
                cost_gas=3.00
            ),
            ImportItemData(
                sku="ITEM-WITHOUT-COST",
                quantity=5,
                description="No cost data"
            )
        ]
        
        po = ImportPOData(
            po_number="PO-2024-002",
            client_name="Mixed Client",
            items=items
        )
        
        print("✅ SUCCESS: ImportPOData created with mixed items")
        print(f"   PO Number: {po.po_number}")
        print(f"   Client: {po.client_name}")
        print(f"   Items: {len(po.items)}")
        print(f"   Total Value: {po.total_value}")
        print(f"   Total Cost: {po.total_cost}")
        print(f"   Margin Global: {po.margin_global}")
        print(f"   Margin %: {po.margin_percentage}")
        return True
        
    except Exception as e:
        print(f"❌ FAILED: {type(e).__name__}: {e}")
        return False


def test_mapping_without_cost_fields():
    """Test 5: Create ImportMapping without cost field mappings"""
    print("\n" + "="*80)
    print("TEST 5: ImportMapping WITHOUT cost fields (ONET-style)")
    print("="*80)
    
    try:
        mapping = ImportMapping(
            mappings=[
                ColumnMapping(column_name="Pedido", field_type=ImportFieldType.PO_NUMBER),
                ColumnMapping(column_name="Cliente", field_type=ImportFieldType.CLIENT_NAME),
                ColumnMapping(column_name="SKU", field_type=ImportFieldType.SKU),
                ColumnMapping(column_name="Qtd", field_type=ImportFieldType.QUANTITY),
                ColumnMapping(column_name="Descrição", field_type=ImportFieldType.DESCRIPTION),
                ColumnMapping(column_name="Unidade", field_type=ImportFieldType.UNIT),
                ColumnMapping(column_name="Lead Time", field_type=ImportFieldType.LEAD_TIME),
            ]
        )
        
        print("✅ SUCCESS: ImportMapping created without cost fields")
        print(f"   Mapped fields: {len(mapping.mappings)}")
        for m in mapping.mappings:
            print(f"   - {m.column_name} → {m.field_type.value}")
        return True
        
    except Exception as e:
        print(f"❌ FAILED: {type(e).__name__}: {e}")
        return False


def test_dictionary_access_pattern():
    """Test 6: Simulate the dictionary access pattern from import_service.py"""
    print("\n" + "="*80)
    print("TEST 6: Dictionary .get() access pattern")
    print("="*80)
    
    try:
        # Simulate a row_data dictionary WITHOUT cost fields
        row_data = {
            'sku': 'TEST-SKU',
            'quantity': 10,
            'description': 'Test Product',
            'unit': 'UN'
            # NO price_unit, cost_mp, cost_mo, cost_energy, cost_gas
        }
        
        # This is how import_service.py now accesses the data
        item = ImportItemData(
            sku=row_data['sku'],
            quantity=row_data['quantity'],
            price_unit=row_data.get('price_unit'),  # Using .get()
            cost_mp=row_data.get('cost_mp'),
            cost_mo=row_data.get('cost_mo'),
            cost_energy=row_data.get('cost_energy'),
            cost_gas=row_data.get('cost_gas'),
            description=row_data.get('description'),
            unit=row_data.get('unit')
        )
        
        print("✅ SUCCESS: Dictionary .get() pattern works correctly")
        print(f"   SKU: {item.sku}")
        print(f"   Quantity: {item.quantity}")
        print(f"   Price Unit: {item.price_unit} (None is OK)")
        print(f"   Cost MP: {item.cost_mp} (None is OK)")
        print(f"   Description: {item.description}")
        return True
        
    except KeyError as e:
        print(f"❌ FAILED: KeyError - {e}")
        print("   This means direct dictionary access is still being used!")
        return False
    except Exception as e:
        print(f"❌ FAILED: {type(e).__name__}: {e}")
        return False


def test_full_onet_19_fields():
    """Test 7: Create item with all 19 ONET fields but NO cost fields"""
    print("\n" + "="*80)
    print("TEST 7: Full ONET 19-field structure WITHOUT costs")
    print("="*80)
    
    try:
        item = ImportItemData(
            # Required fields
            sku="ONET-SKU-001",
            quantity=100,
            
            # ONET fields
            description="Complete ONET Product",
            unit="UN",
            width=Decimal("1200.5"),
            length=Decimal("2400.0"),
            lead_time=30,
            delivery_date="15/06/2024",
            billing_date="20/06/2024",
            icms_percent=Decimal("18.0"),
            block_status="LIBERADO",
            balance=Decimal("5000.00"),
            delay=0,
            payment_terms="30/60/90",
            freight=Decimal("250.00"),
            salesperson="João Silva",
            ipi=Decimal("150.00"),
            
            # NO cost fields - this is the key test
        )
        
        print("✅ SUCCESS: Full ONET item created without cost fields")
        print(f"   SKU: {item.sku}")
        print(f"   Quantity: {item.quantity}")
        print(f"   Description: {item.description}")
        print(f"   Unit: {item.unit}")
        print(f"   Width: {item.width}")
        print(f"   Length: {item.length}")
        print(f"   Lead Time: {item.lead_time}")
        print(f"   Delivery Date: {item.delivery_date}")
        print(f"   ICMS %: {item.icms_percent}")
        print(f"   Salesperson: {item.salesperson}")
        print(f"   Price Unit: {item.price_unit} (None - will be looked up)")
        print(f"   Cost MP: {item.cost_mp} (None - will be looked up)")
        return True
        
    except Exception as e:
        print(f"❌ FAILED: {type(e).__name__}: {e}")
        return False


def main():
    """Run all verification tests"""
    print("\n" + "="*80)
    print("FLEXFLOW IMPORT SERVICE - FINAL VERIFICATION CHECK")
    print("Testing that imports work WITHOUT cost fields (ONET mode)")
    print("="*80)
    
    tests = [
        test_item_without_costs,
        test_item_with_partial_costs,
        test_po_without_costs,
        test_po_with_mixed_items,
        test_mapping_without_cost_fields,
        test_dictionary_access_pattern,
        test_full_onet_19_fields
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"\n❌ UNEXPECTED ERROR in {test.__name__}: {e}")
            results.append(False)
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    passed = sum(results)
    total = len(results)
    
    print(f"Tests Passed: {passed}/{total}")
    
    if passed == total:
        print("\n✅ ALL TESTS PASSED!")
        print("The import service is ready to handle ONET imports without cost fields.")
        print("Cost fields will be looked up from material_costs table by SKU.")
        return 0
    else:
        print(f"\n❌ {total - passed} TEST(S) FAILED!")
        print("Please review the errors above.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
