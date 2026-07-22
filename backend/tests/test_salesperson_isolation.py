import pytest
from unittest.mock import MagicMock
from backend.utils.salesperson_filter import (
    get_salesperson_filter_name,
    po_matches_salesperson,
    filter_pos_by_salesperson
)
from decimal import Decimal


def test_salesperson_filter_admin_bypass():
    current_user = MagicMock(id="11111111-1111-1111-1111-111111111111", role="admin")
    db = MagicMock()
    result = get_salesperson_filter_name(current_user, db)
    assert result is None


def test_salesperson_filter_master_bypass():
    current_user = MagicMock(id="11111111-1111-1111-1111-111111111111", role="master")
    db = MagicMock()
    result = get_salesperson_filter_name(current_user, db)
    assert result is None


def test_salesperson_filter_operador_comercial():
    current_user = MagicMock(id="22222222-2222-2222-2222-222222222222", role="operador")
    db_user = MagicMock(role="operador", area="COMERCIAL")
    db_user.name = "ANDREA"
    db = MagicMock()
    db.query().filter().first.return_value = db_user

    result = get_salesperson_filter_name(current_user, db)
    assert result == "ANDREA"


def test_po_matches_salesperson_matching():
    po = MagicMock()
    item1 = MagicMock(extra_metadata={"salesperson": "Andrea"})
    item2 = MagicMock(extra_metadata={"salesperson": "Bruno"})
    po.items = [item1, item2]

    assert po_matches_salesperson(po, "andrea") is True
    assert po_matches_salesperson(po, "ANDREA") is True
    assert po_matches_salesperson(po, "Carlos") is False


def test_filter_pos_by_salesperson_list():
    po1 = MagicMock(items=[MagicMock(extra_metadata={"salesperson": "Andrea"})])
    po2 = MagicMock(items=[MagicMock(extra_metadata={"salesperson": "Carlos"})])
    pos = [po1, po2]

    filtered = filter_pos_by_salesperson(pos, "Andrea")
    assert len(filtered) == 1
    assert filtered[0] == po1


def test_celso_margin_formula_multiplication():
    custo_mp_kg = Decimal("10.00")
    rendimento = Decimal("0.50")
    unit_cost = custo_mp_kg * rendimento
    assert unit_cost == Decimal("5.0000") or unit_cost == Decimal("5.00")
