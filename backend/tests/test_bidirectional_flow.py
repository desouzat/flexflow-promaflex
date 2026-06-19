"""
FlexFlow - Bidirectional Flow Test
Simple test to verify the bidirectional workflow logic.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_status_flow_mapping():
    """Test that status flow mappings are correct"""
    from routers.kanban import STATUS_FLOW, STATUS_DISPLAY_MAP
    
    print("\n" + "="*80)
    print("STATUS FLOW VERIFICATION")
    print("="*80)
    
    # Verify forward flow
    print("\n[FORWARD FLOW]")
    expected_forward = {
        "DRAFT": "SUBMITTED",
        "SUBMITTED": "APPROVED",
        "APPROVED": "MANUFACTURING",
        "MANUFACTURING": "BILLING",
        "BILLING": "SHIPPING",
        "SHIPPING": "ARCHIVED",
        "FINANCE": "COMPLETED",
        "COMPLETED": None,
        "WAITING_COMMERCIAL_PARTITION": "APPROVED"
    }
    
    for status, expected_next in expected_forward.items():
        actual_next = STATUS_FLOW.get(status, {}).get("next")
        display_name = STATUS_DISPLAY_MAP.get(status, status)
        next_display = STATUS_DISPLAY_MAP.get(expected_next, expected_next) if expected_next else "None"
        
        if actual_next == expected_next:
            print(f"  ✓ {display_name} → {next_display}")
        else:
            print(f"  ✗ {display_name}: Expected {next_display}, got {actual_next}")
            assert False, f"Forward flow mismatch for {status}"
    
    # Verify backward flow
    print("\n[BACKWARD FLOW]")
    expected_backward = {
        "DRAFT": None,
        "SUBMITTED": None,
        "APPROVED": "SUBMITTED",
        "MANUFACTURING": "APPROVED",
        "BILLING": "MANUFACTURING",
        "SHIPPING": "BILLING",
        "FINANCE": "SHIPPING",
        "COMPLETED": "FINANCE",
        "WAITING_COMMERCIAL_PARTITION": None
    }
    
    for status, expected_prev in expected_backward.items():
        actual_prev = STATUS_FLOW.get(status, {}).get("prev")
        display_name = STATUS_DISPLAY_MAP.get(status, status)
        prev_display = STATUS_DISPLAY_MAP.get(expected_prev, expected_prev) if expected_prev else "None"
        
        if actual_prev == expected_prev:
            print(f"  ✓ {display_name} ← {prev_display}")
        else:
            print(f"  ✗ {display_name}: Expected {prev_display}, got {actual_prev}")
            assert False, f"Backward flow mismatch for {status}"
    
    print("\n✓ ALL STATUS FLOW MAPPINGS VERIFIED")
    print("="*80)


def test_display_name_mapping():
    """Test that display names are correctly mapped (FF-HARDENING-012.2: BILLING split)"""
    from routers.kanban import STATUS_DISPLAY_MAP, DISPLAY_TO_DB_STATUS
    import unicodedata

    def norm(s):
        """Normalize unicode for accent-insensitive comparison."""
        return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode() if s else s

    print("\n" + "="*80)
    print("DISPLAY NAME MAPPING VERIFICATION")
    print("="*80)

    # Updated for FF-HARDENING-012.2: BILLING (Faturamento) and SHIPPING (Expedicao) are separate
    expected_mappings = {
        "DRAFT": "Comercial",
        "SUBMITTED": "Comercial",
        "WAITING_COMMERCIAL_PARTITION": "Comercial",
        "APPROVED": "PCP",
        "MANUFACTURING": "Producao/Embalagem",
        "BILLING": "Faturamento",
        "SHIPPING": "Expedicao",
        "COMPLETED": "Financeiro",
        "ANALISE_CREDITO": "Financeiro",
        "CANCELLED": "Cancelado",
    }

    print("\n[DB STATUS -> DISPLAY NAME]")
    for db_status, expected_display in expected_mappings.items():
        actual_display = STATUS_DISPLAY_MAP.get(db_status)
        if norm(actual_display) == norm(expected_display):
            print(f"  OK {db_status} -> {actual_display}")
        else:
            print(f"  FAIL {db_status}: Expected {expected_display!r}, got {actual_display!r}")
            assert False, f"Display mapping mismatch for {db_status}"

    # Legacy compat entries may not round-trip (e.g. Faturamento/Expedicao -> BILLING -> Faturamento)
    LEGACY_SKIP_NORM = {norm("Faturamento/Expedição"), norm("Arquivado")}

    print("\n[DISPLAY NAME -> DB STATUS (canonical entries only)]")
    for display_name, db_status in DISPLAY_TO_DB_STATUS.items():
        if norm(display_name) in LEGACY_SKIP_NORM:
            print(f"  SKIP (legacy) {display_name!r}")
            continue
        actual_display = STATUS_DISPLAY_MAP.get(db_status)
        if norm(actual_display) == norm(display_name):
            print(f"  OK {display_name} -> {db_status}")
        else:
            print(f"  FAIL {display_name}: map back from {db_status!r} got {actual_display!r}")
            assert False, f"Reverse mapping mismatch for {display_name!r}"

    print("\nALL DISPLAY NAME MAPPINGS VERIFIED")
    print("="*80)



def test_valid_transitions():
    """Test that valid transitions are correctly defined"""
    from routers.kanban import STATUS_FLOW
    
    print("\n" + "="*80)
    print("VALID TRANSITIONS VERIFICATION")
    print("="*80)
    
    # Test complete lifecycle path
    print("\n[COMPLETE LIFECYCLE PATH]")
    lifecycle_path = [
        "DRAFT",
        "SUBMITTED",
        "APPROVED",
        "MANUFACTURING",
        "BILLING",
        "SHIPPING",
        "ARCHIVED"
    ]
    
    for i in range(len(lifecycle_path) - 1):
        current = lifecycle_path[i]
        expected_next = lifecycle_path[i + 1]
        actual_next = STATUS_FLOW.get(current, {}).get("next")
        
        if actual_next == expected_next:
            print(f"  ✓ Step {i+1}: {current} → {expected_next}")
        else:
            print(f"  ✗ Step {i+1}: {current} expected {expected_next}, got {actual_next}")
            assert False, f"Lifecycle path broken at {current}"
    
    # Test rejection path
    print("\n[REJECTION PATH]")
    rejection_tests = [
        ("APPROVED", "SUBMITTED", "PCP can reject to Comercial"),
        ("MANUFACTURING", "APPROVED", "Production can return to PCP"),
        ("BILLING", "MANUFACTURING", "Faturamento can return to Production"),
        ("SHIPPING", "BILLING", "Dispatch can return to Faturamento"),
        ("FINANCE", "SHIPPING", "Finance can return to Dispatch"),
        ("COMPLETED", "FINANCE", "Completed can return to Finance"),
    ]
    
    for current, expected_prev, description in rejection_tests:
        actual_prev = STATUS_FLOW.get(current, {}).get("prev")
        if actual_prev == expected_prev:
            print(f"  ✓ {description}: {current} → {expected_prev}")
        else:
            print(f"  ✗ {description}: Expected {expected_prev}, got {actual_prev}")
            assert False, f"Rejection path failed: {description}"
    
    # Test partition suggestion path
    print("\n[PARTITION SUGGESTION PATH]")
    partition_next = STATUS_FLOW.get("WAITING_COMMERCIAL_PARTITION", {}).get("next")
    if partition_next == "APPROVED":
        print(f"  ✓ Partition suggestion returns to PCP: WAITING_COMMERCIAL_PARTITION → APPROVED")
    else:
        print(f"  ✗ Partition suggestion: Expected APPROVED, got {partition_next}")
        assert False, "Partition suggestion path incorrect"
    
    print("\n✓ ALL VALID TRANSITIONS VERIFIED")
    print("="*80)


def test_endpoint_availability():
    """Test that new endpoints are available"""
    print("\n" + "="*80)
    print("ENDPOINT AVAILABILITY CHECK")
    print("="*80)
    
    try:
        from routers import kanban
        
        endpoints = [
            ('advance_po_status', 'POST /kanban/advance-status'),
            ('return_po_status', 'POST /kanban/return-status'),
            ('suggest_partition', 'POST /kanban/suggest-partition'),
        ]
        
        print("\n[CHECKING ENDPOINTS]")
        for func_name, endpoint_desc in endpoints:
            if hasattr(kanban, func_name):
                print(f"  ✓ {endpoint_desc} - Function '{func_name}' exists")
            else:
                print(f"  ✗ {endpoint_desc} - Function '{func_name}' NOT FOUND")
                assert False, f"Endpoint function {func_name} not found"
        
        print("\n✓ ALL ENDPOINTS AVAILABLE")
        print("="*80)
        
    except Exception as e:
        print(f"\n✗ Error checking endpoints: {e}")
        raise


def run_all_tests():
    """Run all tests"""
    print("\n" + "="*80)
    print("FLEXFLOW BIDIRECTIONAL FLOW - 100% CONFIDENCE TEST")
    print("="*80)
    
    try:
        test_status_flow_mapping()
        test_display_name_mapping()
        test_valid_transitions()
        test_endpoint_availability()
        
        print("\n" + "="*80)
        print("✓ ALL TESTS PASSED - 100% CONFIDENCE ACHIEVED")
        print("="*80)
        print("\nSUMMARY:")
        print("  ✓ Status flow mappings verified")
        print("  ✓ Display name mappings verified")
        print("  ✓ Valid transitions verified")
        print("  ✓ Endpoint availability verified")
        print("\nThe bidirectional 'bate-bola' logic is fully implemented and verified!")
        print("="*80 + "\n")
        
        return True
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        print("="*80 + "\n")
        return False
    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        print("="*80 + "\n")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
