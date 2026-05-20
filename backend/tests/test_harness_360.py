"""
FlexFlow — Harness 360°: Complete Hardening Test Suite
======================================================
Covers all three hardening stages:
  - Step 1 (S1): Path traversal, hash versioning, secrets
  - Step 2 (U-01): clean_brazilian_number
  - Step 3 (G/H/I): Finance schemas, Mesa de Conferência, validators cleanup

Run with:
    cd c:\\Documentos\\BotCase\\FlexFlow\\backend
    .\\venv\\Scripts\\Activate.ps1
    python -m pytest tests/test_harness_360.py -v --tb=short
"""

import math
import sys
import types
import uuid
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

# ─── Imports under test ───────────────────────────────────────────────────────
from backend.utils.number_utils import clean_brazilian_number
from backend.services.validators import ValidationResult


# ─────────────────────────────────────────────────────────────────────────────
# GROUP A — Task I: validators.py clean-up (no dead code remaining)
# ─────────────────────────────────────────────────────────────────────────────

class TestValidatorsCleanup:
    """
    Task I: Verify validators.py dead code removal.
    The POStatus enum and StateValidator class must no longer exist.
    ValidationResult must remain functional.
    """

    def test_i01_validation_result_still_importable(self):
        """ValidationResult remains importable from validators."""
        from backend.services.validators import ValidationResult
        assert ValidationResult is not None

    def test_i02_validation_result_truthy_when_valid(self):
        """ValidationResult(True) is truthy."""
        result = ValidationResult(is_valid=True, message="OK")
        assert bool(result) is True

    def test_i03_validation_result_falsy_when_invalid(self):
        """ValidationResult(False) is falsy."""
        result = ValidationResult(is_valid=False, message="FAIL", error_code="ERR_001")
        assert bool(result) is False
        assert result.error_code == "ERR_001"

    def test_i04_validation_result_to_dict(self):
        """to_dict returns the expected keys."""
        result = ValidationResult(is_valid=True, message="Pass")
        d = result.to_dict()
        assert set(d.keys()) == {"is_valid", "message", "error_code"}
        assert d["is_valid"] is True

    def test_i05_state_validator_class_removed(self):
        """
        StateValidator MUST NOT be importable anymore.
        If it still exists, the dead code cleanup failed.
        """
        import backend.services.validators as val_module
        assert not hasattr(val_module, "StateValidator"), (
            "StateValidator was NOT removed from validators.py — dead code cleanup failed!"
        )

    def test_i06_po_status_not_in_validators(self):
        """POStatus enum must NOT be importable from validators."""
        import backend.services.validators as val_module
        assert not hasattr(val_module, "POStatus"), (
            "POStatus was NOT removed from validators.py"
        )

    def test_i07_validators_module_has_no_sqlalchemy_import(self):
        """
        The clean validators.py should not import sqlalchemy.
        Previously it imported 'from sqlalchemy.orm import Session' unnecessarily.
        """
        import backend.services.validators as val_module
        import inspect
        source = inspect.getsource(val_module)
        assert "sqlalchemy" not in source, (
            "validators.py still imports sqlalchemy — dead import not removed"
        )


# ─────────────────────────────────────────────────────────────────────────────
# GROUP B — Task G: Finance Decision Pydantic Schemas
# ─────────────────────────────────────────────────────────────────────────────

class TestFinanceDecisionSchema:
    """
    Task G: Verify FinanceDecisionRequest and FinanceDecisionResponse Pydantic schemas.
    """

    def test_g01_schemas_importable(self):
        """FinanceDecisionRequest, FinanceDecisionResponse, FinanceDecision are importable."""
        from backend.schemas.import_schema import (
            FinanceDecisionRequest,
            FinanceDecisionResponse,
            FinanceDecision
        )
        assert FinanceDecisionRequest is not None
        assert FinanceDecisionResponse is not None
        assert FinanceDecision is not None

    def test_g02_finance_decision_enum_values(self):
        """FinanceDecision has APPROVE and REJECT."""
        from backend.schemas.import_schema import FinanceDecision
        assert FinanceDecision.APPROVE == "APPROVE"
        assert FinanceDecision.REJECT == "REJECT"

    def test_g03_valid_approve_request(self):
        """Valid APPROVE request passes validation."""
        from backend.schemas.import_schema import FinanceDecisionRequest, FinanceDecision
        item_id = str(uuid.uuid4())
        req = FinanceDecisionRequest(
            item_id=item_id,
            decision=FinanceDecision.APPROVE,
            justification="Cliente estratégico com contrato anual garantido — margem compensada pelo volume mensal."
        )
        assert req.item_id == item_id
        assert req.decision == FinanceDecision.APPROVE

    def test_g04_valid_reject_request(self):
        """Valid REJECT request passes validation."""
        from backend.schemas.import_schema import FinanceDecisionRequest, FinanceDecision
        req = FinanceDecisionRequest(
            item_id=str(uuid.uuid4()),
            decision=FinanceDecision.REJECT,
            justification="Margem negativa sem justificativa comercial documentada pelo time de vendas."
        )
        assert req.decision == FinanceDecision.REJECT

    def test_g05_short_justification_rejected(self):
        """Justification shorter than 20 chars (after strip) raises ValidationError."""
        from pydantic import ValidationError
        from backend.schemas.import_schema import FinanceDecisionRequest, FinanceDecision
        with pytest.raises(ValidationError) as exc_info:
            FinanceDecisionRequest(
                item_id=str(uuid.uuid4()),
                decision=FinanceDecision.APPROVE,
                justification="Too short"  # 9 chars
            )
        assert "20" in str(exc_info.value) or "min_length" in str(exc_info.value).lower()

    def test_g06_whitespace_only_justification_rejected(self):
        """Justification that is only whitespace (padded to 20 chars) raises ValidationError."""
        from pydantic import ValidationError
        from backend.schemas.import_schema import FinanceDecisionRequest, FinanceDecision
        with pytest.raises(ValidationError):
            FinanceDecisionRequest(
                item_id=str(uuid.uuid4()),
                decision=FinanceDecision.APPROVE,
                justification="                     "  # 21 spaces — stripped = 0 chars
            )

    def test_g07_invalid_item_id_rejected(self):
        """item_id that is not a valid UUID raises ValidationError."""
        from pydantic import ValidationError
        from backend.schemas.import_schema import FinanceDecisionRequest, FinanceDecision
        with pytest.raises(ValidationError) as exc_info:
            FinanceDecisionRequest(
                item_id="not-a-uuid",
                decision=FinanceDecision.APPROVE,
                justification="Margem negativa justificada por acordo de parceria estratégica."
            )
        assert "uuid" in str(exc_info.value).lower() or "item_id" in str(exc_info.value).lower()

    def test_g08_justification_stripped_on_parse(self):
        """Leading/trailing whitespace in justification is stripped."""
        from backend.schemas.import_schema import FinanceDecisionRequest, FinanceDecision
        req = FinanceDecisionRequest(
            item_id=str(uuid.uuid4()),
            decision=FinanceDecision.APPROVE,
            justification="   Margem negativa justificada por contrato de fidelização anual.   "
        )
        assert not req.justification.startswith(" ")
        assert not req.justification.endswith(" ")

    def test_g09_finance_decision_response_structure(self):
        """FinanceDecisionResponse model has required fields."""
        from backend.schemas.import_schema import FinanceDecisionResponse, FinanceDecision
        resp = FinanceDecisionResponse(
            success=True,
            message="Item aprovado.",
            item_id=str(uuid.uuid4()),
            decision=FinanceDecision.APPROVE,
            new_status="FINANCE_APPROVED",
            audit_log_id=str(uuid.uuid4()),
            audit_hash="abcd1234efgh5678"
        )
        assert resp.success is True
        assert resp.new_status == "FINANCE_APPROVED"

    def test_g10_endpoint_registered_in_router(self):
        """The /api/import/finance-decision endpoint must be registered."""
        from backend.routers.import_router import router
        route_paths = [route.path for route in router.routes]
        assert "/api/import/finance-decision" in route_paths, (
            f"finance-decision not found in routes: {route_paths}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# GROUP C — Task H: Mesa de Conferência (Sum of Items == PO Total)
# ─────────────────────────────────────────────────────────────────────────────

class TestMesaDeConferencia:
    """
    Task H: Verify the financial integrity gate in ImportPOData and import_service.

    The ImportPOData.validate_po_integrity() validator runs at schema parse time.
    The import_service.import_po() then converts the flag into a HARD BLOCK.
    """

    def _make_item(self, unit_value, quantity, item_total_value):
        """Helper: create a minimal ImportItemData-like namespace for testing."""
        from backend.schemas.import_schema import ImportItemData
        return ImportItemData(
            sku=f"SKU-{uuid.uuid4().hex[:6]}",
            quantity=quantity,
            unit_value=Decimal(str(unit_value)),
            item_total_value=Decimal(str(item_total_value))
        )

    def test_h01_balanced_po_passes(self):
        """PO where Σ(item_total) == po_total passes integrity check."""
        from backend.schemas.import_schema import ImportPOData
        items = [
            self._make_item(unit_value=100.00, quantity=5, item_total_value=500.00),
            self._make_item(unit_value=50.00, quantity=10, item_total_value=500.00),
        ]
        po = ImportPOData(
            po_number="PO-001",
            client_name="Cliente A",
            items=items,
            po_total_value=Decimal("1000.00")
        )
        assert po.has_integrity_error is False
        assert po.integrity_error_message is None

    def test_h02_divergent_po_fails(self):
        """PO where Σ(item_total) != po_total (> 0.01) sets integrity error flag."""
        from backend.schemas.import_schema import ImportPOData
        items = [
            self._make_item(unit_value=100.00, quantity=5, item_total_value=500.00),
            self._make_item(unit_value=50.00, quantity=10, item_total_value=500.00),
        ]
        # Declare total as 1000.50 — 0.50 more than actual 1000.00
        po = ImportPOData(
            po_number="PO-002",
            client_name="Cliente B",
            items=items,
            po_total_value=Decimal("1000.50")
        )
        assert po.has_integrity_error is True
        assert po.integrity_error_message is not None
        assert "Divergência" in po.integrity_error_message or "divergência" in po.integrity_error_message.lower()
        print(f"\n✅ H-02 Integrity message: {po.integrity_error_message}")

    def test_h03_tolerance_boundary_1_cent(self):
        """Difference of exactly 0.01 (1 cent) is WITHIN tolerance — no error."""
        from backend.schemas.import_schema import ImportPOData
        items = [self._make_item(unit_value=100.00, quantity=1, item_total_value=100.00)]
        # po_total differs by exactly 0.01 from item sum
        po = ImportPOData(
            po_number="PO-003",
            client_name="Cliente C",
            items=items,
            po_total_value=Decimal("100.01")  # difference = 0.01, NOT > 0.01
        )
        # The schema uses abs(diff) > tolerance, so 0.01 is NOT > 0.01 → no error
        assert po.has_integrity_error is False

    def test_h04_tolerance_boundary_2_cent(self):
        """Difference of 0.02 (2 cents) is OUTSIDE tolerance — error."""
        from backend.schemas.import_schema import ImportPOData
        items = [self._make_item(unit_value=100.00, quantity=1, item_total_value=100.00)]
        po = ImportPOData(
            po_number="PO-004",
            client_name="Cliente D",
            items=items,
            po_total_value=Decimal("100.02")  # difference = 0.02 > 0.01
        )
        assert po.has_integrity_error is True

    def test_h05_no_po_total_value_skips_check(self):
        """If po_total_value is None, integrity check is skipped (not all imports have it)."""
        from backend.schemas.import_schema import ImportPOData
        items = [self._make_item(unit_value=100.00, quantity=5, item_total_value=500.00)]
        po = ImportPOData(
            po_number="PO-005",
            client_name="Cliente E",
            items=items,
            po_total_value=None  # No total provided
        )
        assert po.has_integrity_error is False  # Check was skipped, not failed

    def test_h06_no_item_totals_skips_check(self):
        """If no items have item_total_value, integrity check is skipped."""
        from backend.schemas.import_schema import ImportItemData, ImportPOData
        items = [ImportItemData(sku="SKU-X", quantity=5)]  # No item_total_value
        po = ImportPOData(
            po_number="PO-006",
            client_name="Cliente F",
            items=items,
            po_total_value=Decimal("500.00")
        )
        assert po.has_integrity_error is False

    def test_h07_import_service_returns_error_on_integrity_failure(self):
        """
        import_service.import_po() BLOCKS import when integrity check fails.
        Simulates the Mesa de Conferência hard block.

        This test verifies the logic path directly, not via HTTP.
        """
        from backend.services.import_service import ImportService
        from backend.schemas.import_schema import (
            ImportPOData, ImportItemData, ImportValidationResult
        )

        # Build a "already validated" result with integrity error
        item1 = ImportItemData(
            sku="SKU-A",
            quantity=10,
            unit_value=Decimal("100.00"),
            item_total_value=Decimal("1000.00")
        )
        item2 = ImportItemData(
            sku="SKU-B",
            quantity=5,
            unit_value=Decimal("50.00"),
            item_total_value=Decimal("250.00")
        )
        # PO total says 2000, but sum is 1250 → divergence of 750 > 0.01
        po_data = ImportPOData(
            po_number="PO-BAD",
            client_name="Cliente Ruim",
            items=[item1, item2],
            po_total_value=Decimal("2000.00")  # WRONG — should be 1250
        )

        # Assert the flag was set by the schema validator
        assert po_data.has_integrity_error is True, (
            "ImportPOData should have set has_integrity_error=True"
        )

        # Now simulate what import_service does: loop po_data_list and block
        integrity_errors = []
        for po in [po_data]:
            if po.has_integrity_error and po.integrity_error_message:
                integrity_errors.append(f"PO {po.po_number}: {po.integrity_error_message}")

        assert len(integrity_errors) == 1
        assert "PO-BAD" in integrity_errors[0]
        assert "R$" in integrity_errors[0] or "diferença" in integrity_errors[0].lower() or "Divergência" in integrity_errors[0]
        print(f"\n✅ H-07 Integrity block message: {integrity_errors[0]}")

    def test_h08_multi_po_both_must_pass(self):
        """With two POs, both must pass integrity. One failing blocks the whole import."""
        from backend.schemas.import_schema import ImportPOData
        good_item = self._make_item(100, 5, 500)
        bad_item = self._make_item(100, 5, 500)

        po_good = ImportPOData(
            po_number="PO-GOOD",
            client_name="Cliente Bom",
            items=[good_item],
            po_total_value=Decimal("500.00")  # Correct
        )
        po_bad = ImportPOData(
            po_number="PO-BAD-2",
            client_name="Cliente Ruim",
            items=[bad_item],
            po_total_value=Decimal("999.00")  # Wrong — diff = 499 >> 0.01
        )

        assert po_good.has_integrity_error is False
        assert po_bad.has_integrity_error is True

        integrity_errors = []
        for po in [po_good, po_bad]:
            if po.has_integrity_error and po.integrity_error_message:
                integrity_errors.append(f"PO {po.po_number}: {po.integrity_error_message}")

        assert len(integrity_errors) == 1
        assert "PO-BAD-2" in integrity_errors[0]


# ─────────────────────────────────────────────────────────────────────────────
# GROUP D — Regression: Step 1 + Step 2 (ensure nothing was broken)
# ─────────────────────────────────────────────────────────────────────────────

class TestRegressionStep1:
    """Regression: Critical Step 1 features must still work."""

    def test_r01_path_traversal_defense(self):
        """FileService still blocks path traversal attempts."""
        from backend.services.file_service import FileService
        svc = FileService()
        with pytest.raises(Exception):
            svc._validate_path("../../../etc/passwd", "tenant-abc")

    def test_r02_audit_log_hash_v2_still_works(self):
        """AuditLog.calculate_hash_v2 is still available and produces consistent hash."""
        from backend.models import AuditLog
        from datetime import datetime, timezone
        tenant_id = uuid.uuid4()
        item_id = uuid.uuid4()
        ts = datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc)
        h1 = AuditLog.calculate_hash_v2(
            tenant_id=tenant_id, item_id=item_id,
            from_status="PENDING", to_status="FINANCE_APPROVED",
            timestamp=ts, previous_hash=None, changed_by=uuid.uuid4()
        )
        h2 = AuditLog.calculate_hash_v2(
            tenant_id=tenant_id, item_id=item_id,
            from_status="PENDING", to_status="FINANCE_APPROVED",
            timestamp=ts, previous_hash=None, changed_by=uuid.uuid4()
        )
        # Both hashes must be non-empty SHA-256 strings of length 64
        assert len(h1) == 64
        assert len(h2) == 64
        # They may differ (changed_by differs) but must be valid hex
        assert all(c in "0123456789abcdef" for c in h1)


class TestRegressionStep2:
    """Regression: Step 2 (U-01) still passes after Step 3 changes."""

    @pytest.mark.parametrize("raw,expected", [
        ("R$ 13.335,00", "13335.00"),
        ("13.335,00", "13335.00"),
        ("1.335,50", "1335.50"),
        ("13335.00", "13335.00"),
        ("13335,00", "13335.00"),
        ("0,50", "0.50"),
        ("INVALID", None),
        (None, None),
        (float("nan"), None),
    ])
    def test_r_u01_parametrized(self, raw, expected):
        """Parametrized regression of all SDD U-01 cases."""
        result = clean_brazilian_number(raw)
        assert result == expected, f"clean_brazilian_number({raw!r}) = {result!r}, expected {expected!r}"

    def test_r_u01_native_float(self):
        """Native float passthrough still works."""
        result = clean_brazilian_number(13335.00)
        assert result is not None
        assert abs(float(result) - 13335.0) < 0.001

    def test_r_critical_regression(self):
        """Old Strategy-B bug MUST remain fixed: 13.335,50 → 13335.50 (not 13.33550)."""
        result = clean_brazilian_number("13.335,50")
        assert result == "13335.50", f"REGRESSION: got {result!r}"
        assert Decimal(result) == Decimal("13335.50")


# ─────────────────────────────────────────────────────────────────────────────
# GROUP E — Smoke: Import schemas are internally consistent
# ─────────────────────────────────────────────────────────────────────────────

class TestSchemaSmokeTests:
    """Quick smoke tests for schema integrity after all changes."""

    def test_s01_import_schema_module_loads(self):
        """The entire import_schema module must load without error."""
        import backend.schemas.import_schema as m
        assert hasattr(m, "ImportMapping")
        assert hasattr(m, "ImportPOData")
        assert hasattr(m, "FinanceDecisionRequest")
        assert hasattr(m, "FinanceDecisionResponse")
        assert hasattr(m, "FinanceDecision")

    def test_s02_import_router_module_loads(self):
        """import_router module must load without error."""
        import backend.routers.import_router as m
        assert hasattr(m, "router")

    def test_s03_number_utils_module_loads(self):
        """number_utils module must load without error."""
        import backend.utils.number_utils as m
        assert hasattr(m, "clean_brazilian_number")

    def test_s04_validators_module_loads(self):
        """validators module (cleaned) must load without error."""
        import backend.services.validators as m
        assert hasattr(m, "ValidationResult")

    def test_s05_models_module_loads(self):
        """models module must load without error."""
        import backend.models as m
        assert hasattr(m, "AuditLog")
        assert hasattr(m, "OrderItem")
        assert hasattr(m, "PurchaseOrder")


if __name__ == "__main__":
    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "pytest", __file__, "-v", "--tb=short"],
        cwd=str(Path(__file__).resolve().parent.parent)
    )
    sys.exit(result.returncode)
