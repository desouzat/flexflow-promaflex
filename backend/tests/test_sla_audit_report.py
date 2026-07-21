"""
Tests for the expanded SLA Audit Report (GET /api/reports/po-export).

Strategy:
- Pure-function helpers (_add_business_hours, _sla_label, _compute_stage_times)
  are tested in isolation with no DB or FastAPI dependencies.
- CSV structure smoke test uses an in-memory SQLite DB (same pattern as
  test_sla_calculator.py) to exercise the full route handler.

Run from project root:
    pytest backend/tests/test_sla_audit_report.py -v
"""
from __future__ import annotations

import csv
import io
import uuid
from collections import namedtuple
from datetime import datetime, timedelta, timezone

import pytest

# ── Import pure helpers directly ─────────────────────────────────────────────
from backend.routers.reports import (
    _add_business_hours,
    _compute_stage_times,
    _sla_label,
)

DEFAULT_CONFIG = {
    "sla_total_hours": 240,
    "sla_start_hour": 8,
    "sla_end_hour": 18,
    "sla_working_days": "Mon-Fri",
}

# Monday 2026-07-20 09:00 UTC (weekday == 0)
MONDAY_9AM = datetime(2026, 7, 20, 9, 0, 0)


# ════════════════════════════════════════════════════════════════════════════
# Tests: _add_business_hours — forward projection
# ════════════════════════════════════════════════════════════════════════════
class TestAddBusinessHours:
    def test_same_day_within_window(self):
        """Adding 2h at 09:00 Mon → 11:00 same day."""
        result = _add_business_hours(MONDAY_9AM, 2.0, DEFAULT_CONFIG)
        assert result == datetime(2026, 7, 20, 11, 0, 0)

    def test_spills_into_next_day(self):
        """Adding 10h at 09:00 Mon: 9h finishes Mon 18:00, remaining 1h → Tue 09:00."""
        result = _add_business_hours(MONDAY_9AM, 10.0, DEFAULT_CONFIG)
        assert result == datetime(2026, 7, 21, 9, 0, 0)

    def test_ends_exactly_at_close(self):
        """Adding exactly 9h at 09:00 → 18:00 same day."""
        result = _add_business_hours(MONDAY_9AM, 9.0, DEFAULT_CONFIG)
        assert result == datetime(2026, 7, 20, 18, 0, 0)

    def test_skips_weekend_correctly(self):
        """1h remaining at Friday 17:00 → Friday 18:00 (still same day)."""
        friday_17h = datetime(2026, 7, 17, 17, 0, 0)  # Friday
        result = _add_business_hours(friday_17h, 1.0, DEFAULT_CONFIG)
        assert result == datetime(2026, 7, 17, 18, 0, 0)

    def test_start_after_close_wraps_to_monday(self):
        """Starting Friday 19:00 (after close) + 1h → Monday 09:00."""
        fri_19h = datetime(2026, 7, 17, 19, 0, 0)
        result = _add_business_hours(fri_19h, 1.0, DEFAULT_CONFIG)
        assert result == datetime(2026, 7, 20, 9, 0, 0)

    def test_zero_hours_returns_start(self):
        """Zero-hour delta should return the start time unchanged."""
        result = _add_business_hours(MONDAY_9AM, 0.0, DEFAULT_CONFIG)
        assert result == MONDAY_9AM

    def test_large_sla_lands_on_weekday(self):
        """240-hour SLA deadline must be a Mon–Fri datetime."""
        start = datetime(2026, 7, 20, 8, 0, 0)
        result = _add_business_hours(start, 240.0, DEFAULT_CONFIG)
        assert result > start + timedelta(days=20)
        assert result.weekday() < 5  # Monday–Friday


# ════════════════════════════════════════════════════════════════════════════
# Tests: _sla_label — traffic-light logic
# ════════════════════════════════════════════════════════════════════════════
class TestSlaLabel:
    def test_verde_under_80_pct(self):
        assert _sla_label(50.0, 240.0, False) == "Verde"

    def test_verde_at_exactly_79_pct(self):
        assert _sla_label(189.5, 240.0, False) == "Verde"

    def test_amarelo_between_80_and_99_pct(self):
        assert _sla_label(200.0, 240.0, False) == "Amarelo"

    def test_amarelo_at_exactly_80_pct(self):
        assert _sla_label(192.0, 240.0, False) == "Amarelo"

    def test_vermelho_at_100_pct(self):
        assert _sla_label(240.0, 240.0, False) == "Vermelho"

    def test_vermelho_over_100_pct(self):
        assert _sla_label(300.0, 240.0, False) == "Vermelho"

    def test_finished_po_always_verde(self):
        """COMPLETED / CANCELLED POs must always show Verde regardless of elapsed hours."""
        assert _sla_label(500.0, 240.0, True) == "Verde"
        assert _sla_label(0.0, 240.0, True) == "Verde"

    def test_zero_limit_returns_empty(self):
        """Misconfigured zero-limit must not crash and should return ''."""
        assert _sla_label(10.0, 0.0, False) == ""


# ════════════════════════════════════════════════════════════════════════════
# Tests: _compute_stage_times — stage timing from audit logs
# ════════════════════════════════════════════════════════════════════════════
def _make_log(to_status: str, created_at: datetime, from_status: str = None):
    """Build a minimal AuditLog-like namedtuple for unit testing."""
    _Log = namedtuple("FakeLog", ["to_status", "from_status", "created_at", "item_id"])
    return _Log(
        to_status=to_status,
        from_status=from_status,
        created_at=created_at,
        item_id="item-1",
    )


class TestComputeStageTimes:
    def test_no_logs_uses_po_created_at(self):
        """Without logs, hours_in_current_stage is measured from created_at."""
        now = datetime(2026, 7, 21, 12, 0, 0)          # Tuesday 12:00
        po_created = datetime(2026, 7, 20, 8, 0, 0)    # Monday 08:00
        result = _compute_stage_times(
            logs=[],
            po_status_macro="MANUFACTURING",
            po_created_at=po_created,
            config=DEFAULT_CONFIG,
            now=now,
        )
        # Mon 08:00–18:00 (10h) + Tue 08:00–12:00 (4h) = 14h
        assert result["hours_in_current_stage"] == pytest.approx(14.0, abs=0.1)

    def test_area_time_attribution(self):
        """PO: APPROVED (PCP, Mon 08–14) → MANUFACTURING (Produção, Mon 14 – Tue 10)."""
        now = datetime(2026, 7, 21, 10, 0, 0)           # Tuesday 10:00
        po_created = datetime(2026, 7, 20, 8, 0, 0)     # Monday 08:00
        logs = [
            _make_log("APPROVED",      datetime(2026, 7, 20, 8, 0, 0)),
            _make_log("MANUFACTURING", datetime(2026, 7, 20, 14, 0, 0)),
        ]
        result = _compute_stage_times(
            logs=logs,
            po_status_macro="MANUFACTURING",
            po_created_at=po_created,
            config=DEFAULT_CONFIG,
            now=now,
        )
        hba = result["hours_by_area"]
        # PCP: Mon 08:00–14:00 = 6h
        assert hba.get("PCP", 0.0) == pytest.approx(6.0, abs=0.1)
        # Produção: Mon 14:00–18:00 (4h) + Tue 08:00–10:00 (2h) = 6h
        assert hba.get("Produção", 0.0) == pytest.approx(6.0, abs=0.1)

    def test_hours_in_stage_at_entry_moment_is_zero(self):
        """Stage entered exactly at 'now' → 0 business hours in stage."""
        now = datetime(2026, 7, 21, 8, 0, 0)
        logs = [_make_log("BILLING", now)]
        result = _compute_stage_times(
            logs=logs,
            po_status_macro="BILLING",
            po_created_at=datetime(2026, 7, 20, 8, 0, 0),
            config=DEFAULT_CONFIG,
            now=now,
        )
        assert result["hours_in_current_stage"] == pytest.approx(0.0, abs=0.01)

    def test_faturamento_area_accumulates(self):
        """BILLING and FINANCE both map to 'Faturamento' area."""
        now = datetime(2026, 7, 21, 18, 0, 0)
        po_created = datetime(2026, 7, 20, 8, 0, 0)
        logs = [
            _make_log("BILLING", datetime(2026, 7, 20, 8, 0, 0)),
            _make_log("FINANCE", datetime(2026, 7, 20, 14, 0, 0)),
        ]
        result = _compute_stage_times(
            logs=logs,
            po_status_macro="FINANCE",
            po_created_at=po_created,
            config=DEFAULT_CONFIG,
            now=now,
        )
        hba = result["hours_by_area"]
        # Both BILLING and FINANCE → Faturamento
        # Mon 08:00–18:00 (10h) + Tue 08:00–18:00 (10h) = 20h
        assert hba.get("Faturamento", 0.0) == pytest.approx(20.0, abs=0.5)

    def test_never_negative_stage_hours(self):
        """Degenerate inputs must never produce negative hours."""
        future_log = _make_log("MANUFACTURING", datetime(2026, 7, 22, 9, 0, 0))
        now = datetime(2026, 7, 21, 9, 0, 0)
        result = _compute_stage_times(
            logs=[future_log],
            po_status_macro="MANUFACTURING",
            po_created_at=datetime(2026, 7, 20, 8, 0, 0),
            config=DEFAULT_CONFIG,
            now=now,
        )
        assert result["hours_in_current_stage"] >= 0.0


# ════════════════════════════════════════════════════════════════════════════
# Tests: CSV column structure (integration, in-memory SQLite)
# ════════════════════════════════════════════════════════════════════════════
class TestCsvColumns:
    """Validates that the exported CSV has the correct header structure.

    Uses an in-memory SQLite DB and an authenticated mock user so the
    route handler runs end-to-end without a real PostgreSQL connection.
    """

    @pytest.fixture
    def db_session(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from backend.database import Base

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()

        # Insert a Tenant row so the route doesn't error on FK constraints
        from backend.models import Tenant
        tenant = Tenant(
            id=uuid.uuid4(),
            name="Test Tenant",
            cnpj="00.000.000/0001-00",
            is_active=True,
        )
        session.add(tenant)
        session.commit()
        yield session, tenant.id
        session.close()

    def _call_route(self, tenant_id, db):
        """Call the async route handler synchronously via asyncio."""
        import asyncio
        from unittest.mock import MagicMock
        from backend.routers.reports import export_pos_csv

        mock_user = MagicMock()
        mock_user.tenant_id = tenant_id

        async def _run():
            response = await export_pos_csv(current_user=mock_user, db=db)
            # body_iterator may be sync (iter) or async — drain both
            chunks = []
            it = response.body_iterator
            if hasattr(it, "__aiter__"):
                async for chunk in it:
                    chunks.append(chunk)
            else:
                for chunk in it:
                    chunks.append(chunk)
            return b"".join(chunks)

        return asyncio.run(_run())

    def _parse_csv(self, raw_bytes: bytes) -> list:
        raw = raw_bytes.decode("utf-8-sig")
        return list(csv.reader(io.StringIO(raw), delimiter=";"))

    def test_header_has_25_columns(self, db_session):
        session, tid = db_session
        raw = self._call_route(tid, session)
        rows = self._parse_csv(raw)
        assert len(rows) >= 1, "CSV must have at least a header row"
        assert len(rows[0]) == 25, (
            f"Expected 25 columns, got {len(rows[0])}.\n"
            f"Header: {rows[0]}"
        )

    def test_all_new_sla_columns_in_header(self, db_session):
        session, tid = db_session
        raw = self._call_route(tid, session)
        header = self._parse_csv(raw)[0]
        required = [
            "CÓDIGO ESTRUTURADO",
            "ETAPA ATUAL",
            "STATUS SLA",
            "HORAS SLA DECORRIDAS",
            "PRAZO LIMITE SLA",
            "HORAS DE ATRASO",
            "JUSTIFICATIVA OCORRÊNCIA",
            "DATA ENTRADA KANBAN",
            "SLA ENTREGA CLIENTE",
            "TEMPO ETAPA ATUAL (h)",
            "TEMPO PCP (h)",
            "TEMPO PRODUÇÃO (h)",
            "TEMPO FATURAMENTO (h)",
        ]
        missing = [c for c in required if c not in header]
        assert not missing, f"Missing SLA columns: {missing}"

    def test_empty_tenant_produces_header_only(self, db_session):
        """A tenant with no POs should produce exactly 1 row (header)."""
        session, tid = db_session
        raw = self._call_route(tid, session)
        rows = self._parse_csv(raw)
        assert len(rows) == 1, f"Expected 1 row (header only), got {len(rows)}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
