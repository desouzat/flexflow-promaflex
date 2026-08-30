import pytest
from decimal import Decimal
from unittest.mock import MagicMock
from backend.routers.kanban import calculate_unit_aware_item_cost

def test_unit_aware_cost_m2():
    # Item in M2 (Square Meters)
    item = {
        "unidade_medida": "M2",
        "quantity": 3500.0,
    }
    material = MagicMock()
    material.custo_mp_kg = 1.62
    material.rendimento = 14.8698
    
    total_cost, unit_cost = calculate_unit_aware_item_cost(item, material)
    
    # For M2 orders: cost = qty_m2 * cost_m2
    assert total_cost == Decimal("3500.0") * Decimal("1.62")
    assert total_cost == Decimal("5670.00")
    assert unit_cost == Decimal("1.62")

def test_unit_aware_cost_kg():
    # Item in KG
    item = {
        "unidade_medida": "KG",
        "quantity": 100.0,
    }
    material = MagicMock()
    material.custo_mp_kg = 1.62
    material.rendimento = 14.8698
    
    total_cost, unit_cost = calculate_unit_aware_item_cost(item, material)
    
    # For KG orders: cost = qty_kg * (cost_m2 * yield_m2_per_kg)
    expected_cost = Decimal("100.0") * (Decimal("1.62") * Decimal("14.8698"))
    assert total_cost == expected_cost
    assert unit_cost == (Decimal("1.62") * Decimal("14.8698"))

def test_unit_aware_cost_rolls():
    # Item in RL (Rolls)
    item = {
        "unidade_medida": "RL",
        "quantity": 10.0,
        "width": 1300.0,  # mm -> 1.3m
        "length": 100.0,  # m
    }
    material = MagicMock()
    material.custo_mp_kg = 1.62
    material.rendimento = 14.8698
    
    total_cost, unit_cost = calculate_unit_aware_item_cost(item, material)
    
    # For Rolls: total m2 area = (1.3 * 100 * 10) = 1300 m2
    # total cost = 1300 * 1.62 = 2106.00
    assert total_cost == Decimal("1300.0") * Decimal("1.62")
    assert total_cost == Decimal("2106.00")
    assert unit_cost == Decimal("210.60")

def test_unit_aware_cost_units():
    # Item in UN (Units)
    item = {
        "unidade_medida": "UN",
        "quantity": 5.0,
        "width": 1200.0,  # mm -> 1.2m
        "length": 50.0,   # m
    }
    material = MagicMock()
    material.custo_mp_kg = 1.85
    material.rendimento = 12.3456
    
    total_cost, unit_cost = calculate_unit_aware_item_cost(item, material)
    
    # For Units: total m2 area = (1.2 * 50 * 5) = 300 m2
    # total cost = 300 * 1.85 = 555.00
    assert total_cost == Decimal("300.0") * Decimal("1.85")
    assert total_cost == Decimal("555.00")
    assert unit_cost == Decimal("111.00")
