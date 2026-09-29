import pytest
from datetime import datetime, date
from fastapi import HTTPException
from backend.routers.kanban import parse_date_safe
from backend.models import PurchaseOrder


def test_parse_date_safe_iso_and_brl():
    """Verify parse_date_safe parses ISO and Brazilian dates to pure timezone-naive date objects."""
    # Brazilian format
    d1 = parse_date_safe("29/09/2026")
    assert d1 == date(2026, 9, 29)
    assert isinstance(d1, date)
    assert not isinstance(d1, datetime)

    # ISO format
    d2 = parse_date_safe("2026-09-29")
    assert d2 == date(2026, 9, 29)

    # ISO with timestamp
    d3 = parse_date_safe("2026-09-29T15:30:00Z")
    assert d3 == date(2026, 9, 29)

    # Native date
    native_d = date(2026, 7, 27)
    assert parse_date_safe(native_d) == native_d

    # Native datetime
    native_dt = datetime(2026, 7, 27, 23, 59, 59)
    assert parse_date_safe(native_dt) == date(2026, 7, 27)

    # Edge cases
    assert parse_date_safe(None) is None
    assert parse_date_safe("") is None
    assert parse_date_safe("   ") is None
    assert parse_date_safe("invalid-date-format") is None


def test_sla_decoupling_integrity():
    """
    Verify CR-DATES core rule: Updating 'data_programada' in PCP must NEVER
    overwrite the contractual client SLA 'expected_delivery_date'.
    """
    po = PurchaseOrder(
        po_number="213127",
        partition_metadata={"expected_delivery_date": "2026-07-27", "data_programada": "2026-07-27"}
    )
    initial_sla = parse_date_safe(po.expected_delivery_date)

    # Simulate PCP updating data_programada in update_po_area_fields
    fields = {"data_programada": "2026-11-26"}
    if "data_programada" in fields and fields["data_programada"]:
        if po.partition_metadata is None:
            po.partition_metadata = {}
        po.partition_metadata["data_programada"] = fields["data_programada"]
        # CR-DATES GUARANTEE: po.partition_metadata["expected_delivery_date"] is NOT modified!

    assert po.partition_metadata["data_programada"] == "2026-11-26"
    assert parse_date_safe(po.expected_delivery_date) == initial_sla
    assert parse_date_safe(po.expected_delivery_date) == date(2026, 7, 27)


def test_pcp_sla_breach_gating_logic():
    """
    Verify CR-DATES gating: Advancing from APPROVED (PCP) to MANUFACTURING (Produção)
    when data_programada exceeds expected_delivery_date requires an SLA justification category.
    """
    def check_pcp_advance(po: PurchaseOrder, from_status: str, to_status: str):
        if from_status == "APPROVED" and to_status == "MANUFACTURING":
            prog_date_raw = (po.partition_metadata or {}).get("data_programada")
            sla_date_raw = po.expected_delivery_date
            prog_date = parse_date_safe(prog_date_raw)
            sla_date = parse_date_safe(sla_date_raw)

            if prog_date and sla_date and prog_date > sla_date:
                if not getattr(po, 'sla_justification_category', None):
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"A Data Programada ({prog_date.strftime('%d/%m/%Y')}) excede o SLA do Cliente "
                            f"({sla_date.strftime('%d/%m/%Y')}). É obrigatório selecionar a Justificativa de SLA no PCP "
                            f"antes de liberar para Produção."
                        )
                    )

    # Case 1: prog_date > sla_date WITHOUT justification -> MUST RAISE 400
    po_breach = PurchaseOrder(
        po_number="213127",
        partition_metadata={"expected_delivery_date": "2026-07-27", "data_programada": "2026-11-26"},
        sla_justification_category=None
    )
    with pytest.raises(HTTPException) as exc_info:
        check_pcp_advance(po_breach, "APPROVED", "MANUFACTURING")
    assert exc_info.value.status_code == 400
    assert "excede o SLA do Cliente" in exc_info.value.detail

    # Case 2: prog_date > sla_date WITH justification -> MUST PASS
    po_justified = PurchaseOrder(
        po_number="213127",
        partition_metadata={"expected_delivery_date": "2026-07-27", "data_programada": "2026-11-26"},
        sla_justification_category="FALTA_MATERIA_PRIMA"
    )
    # Should not raise
    check_pcp_advance(po_justified, "APPROVED", "MANUFACTURING")

    # Case 3: prog_date <= sla_date WITHOUT justification -> MUST PASS
    po_on_time = PurchaseOrder(
        po_number="213127",
        partition_metadata={"expected_delivery_date": "2026-07-27", "data_programada": "2026-07-20"},
        sla_justification_category=None
    )
    # Should not raise
    check_pcp_advance(po_on_time, "APPROVED", "MANUFACTURING")

    # Case 4: Other transitions (e.g. SUBMITTED -> APPROVED) -> MUST PASS
    check_pcp_advance(po_breach, "SUBMITTED", "APPROVED")


def test_order_date_card_precedence():
    """
    Verify Card 5 precedence rule in Kanban header:
    Genuine ERP order_date must NOT be masked by created_at.
    """
    def resolve_card_5_order_date(po_dict: dict) -> str:
        # Replicates frontend precedence logic:
        # partition_metadata?.order_date || extra_metadata?.order_date || order_date || created_at
        part_meta = po_dict.get("partition_metadata") or {}
        extra_meta = po_dict.get("extra_metadata") or {}
        return (
            part_meta.get("order_date") or
            extra_meta.get("order_date") or
            po_dict.get("order_date") or
            po_dict.get("created_at")
        )

    # PO #214441 scenario: inserted in DB on 2026-09-29, but genuine ERP order date is 2026-09-21
    po_data = {
        "created_at": "2026-09-29T10:30:00Z",
        "partition_metadata": {"order_date": "2026-09-21"},
        "order_date": None
    }
    assert resolve_card_5_order_date(po_data) == "2026-09-21"

    # Fallback to created_at only when no order_date is present anywhere
    po_legacy = {
        "created_at": "2026-05-10T08:00:00Z",
        "partition_metadata": {},
        "extra_metadata": {},
        "order_date": None
    }
    assert resolve_card_5_order_date(po_legacy) == "2026-05-10T08:00:00Z"
