"""
FlexFlow - ONET New Aliases Ingestion & Validation Bypass Test
"""

import pytest
import io
import pandas as pd
from decimal import Decimal
from unittest.mock import Mock
from sqlalchemy.orm import Session

from backend.services.import_service import ImportService
from backend.schemas.import_schema import (
    ImportMapping,
    ColumnMapping,
    ImportFieldType,
    ImportRequest
)


def test_onet_new_aliases_flexible_matching():
    """
    Verify that importing a file with Dt.Entrega, Dt.Faturamento, Dias Médio Atraso,
    Vl. IPI, Saldo Devedor, Quantidade, and Vl.Frete correctly resolves aliases
    and passes mapping validation.
    """
    mock_db = Mock(spec=Session)
    import_service = ImportService(mock_db)
    
    # 1. Standard mapping using the default/legacy column names
    mapping = ImportMapping(
        mappings=[
            ColumnMapping(column_name="Pedido", field_type=ImportFieldType.PO_NUMBER),
            ColumnMapping(column_name="Cliente", field_type=ImportFieldType.CLIENT_NAME),
            ColumnMapping(column_name="SKU", field_type=ImportFieldType.SKU),
            
            # These columns are named differently in the spreadsheet (as aliases)
            ColumnMapping(column_name="Qtd", field_type=ImportFieldType.QUANTITY),
            ColumnMapping(column_name="Data Entrega", field_type=ImportFieldType.DELIVERY_DATE),
            ColumnMapping(column_name="Data Faturamento", field_type=ImportFieldType.BILLING_DATE),
            ColumnMapping(column_name="IPI", field_type=ImportFieldType.IPI),
            ColumnMapping(column_name="Frete", field_type=ImportFieldType.FREIGHT),
            ColumnMapping(column_name="Saldo", field_type=ImportFieldType.BALANCE),
            ColumnMapping(column_name="Atraso", field_type=ImportFieldType.DELAY),
        ]
    )
    
    # 2. DataFrame with ONET BRL headers (case-insensitive & trimmed checks)
    df = pd.DataFrame({
        'Pedido': ['PO-ONET-777'],
        'Cliente': ['Cliente ONET S.A.'],
        'SKU': ['SKU-ONET-001'],
        
        # Test case-insensitivity, spaces, and the specific new aliases
        '  Quantidade  ': [100],  # legacy Qtd, trimmed check
        'Dt.Entrega': ['2026-06-01'],  # legacy Data Entrega
        'dt.faturamento': ['2026-06-05'],  # legacy Data Faturamento, lower check
        'Vl. IPI': [15.50],  # legacy IPI
        'Vl.Frete': [200.00],  # legacy Frete
        'Saldo Devedor': [300.00],  # legacy Saldo
        'Dias Médio Atraso': [5]  # legacy Atraso
    })
    
    # 3. Verify that resolve_aliases maps the columns dynamically
    import_service.resolve_aliases(df, mapping)
    
    # Assert validation passes
    is_valid, error_msg = import_service.validate_mapping(df, mapping)
    assert is_valid, f"Mapping validation failed: {error_msg}"
    
    # Verify that columns in mapping were resolved to the correct DataFrame column headers
    mapping_dict = mapping.get_mapping_dict()
    
    assert mapping_dict['Pedido'] == ImportFieldType.PO_NUMBER
    assert mapping_dict['Cliente'] == ImportFieldType.CLIENT_NAME
    assert mapping_dict['SKU'] == ImportFieldType.SKU
    assert mapping_dict['  Quantidade  '] == ImportFieldType.QUANTITY
    assert mapping_dict['Dt.Entrega'] == ImportFieldType.DELIVERY_DATE
    assert mapping_dict['dt.faturamento'] == ImportFieldType.BILLING_DATE
    assert mapping_dict['Vl. IPI'] == ImportFieldType.IPI
    assert mapping_dict['Vl.Frete'] == ImportFieldType.FREIGHT
    assert mapping_dict['Saldo Devedor'] == ImportFieldType.BALANCE
    assert mapping_dict['Dias Médio Atraso'] == ImportFieldType.DELAY
    
    print("\n[OK] ALL ONET ALIASES DYNAMICALLY RESOLVED AND MAPPED SUCCESSFULLY!")


def test_integrity_gate_with_ipi():
    """
    Verify that the PO integrity gate checks SUM(item_total_value) + SUM(ipi) == po_total_value
    within a tolerance of R$ 0.01.
    """
    from backend.schemas.import_schema import ImportPOData, ImportItemData
    
    # 1. Balanced PO: item_total_value = 1000.00, ipi = 155.50, po_total_value = 1155.50
    item = ImportItemData(
        sku="SKU-IPI-001",
        quantity=10,
        item_total_value=Decimal("1000.00"),
        ipi=Decimal("155.50")
    )
    po = ImportPOData(
        po_number="PO-IPI-777",
        client_name="Cliente IPI",
        items=[item],
        po_total_value=Decimal("1155.50")
    )
    assert po.has_integrity_error is False
    assert po.integrity_error_message is None
    
    # 2. Divergent PO: sum with IPI = 1155.50, but po_total_value = 1155.00
    po_bad = ImportPOData(
        po_number="PO-IPI-888",
        client_name="Cliente IPI",
        items=[item],
        po_total_value=Decimal("1155.00")
    )
    assert po_bad.has_integrity_error is True
    assert "Soma dos itens + IPI" in po_bad.integrity_error_message
    print("\n[OK] INTEGRITY GATE MATH WITH IPI CORRECTLY BLOCKED AND VERIFIED!")
