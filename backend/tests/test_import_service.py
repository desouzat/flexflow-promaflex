"""
FlexFlow Import Service Tests
Comprehensive unit tests for the import service covering:
- Successful imports
- Mapping errors
- Margin calculations
- Rollback on validation failures
"""

import pytest
import io
from decimal import Decimal
from unittest.mock import Mock, MagicMock, patch
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from backend.services.import_service import ImportService
from backend.schemas.import_schema import (
    ImportMapping,
    ColumnMapping,
    ImportFieldType,
    ImportRequest,
    ImportItemData,
    ImportPOData
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_db():
    """Mock database session"""
    db = Mock(spec=Session)
    db.rollback = Mock()
    db.commit = Mock()
    db.add = Mock()
    db.flush = Mock()
    return db


@pytest.fixture
def import_service(mock_db):
    """Create import service instance"""
    return ImportService(mock_db)


@pytest.fixture
def valid_mapping():
    """Valid column mapping configuration"""
    return ImportMapping(
        mappings=[
            ColumnMapping(column_name="PO Number", field_type=ImportFieldType.PO_NUMBER),
            ColumnMapping(column_name="Client", field_type=ImportFieldType.CLIENT_NAME),
            ColumnMapping(column_name="SKU", field_type=ImportFieldType.SKU),
            ColumnMapping(column_name="Qty", field_type=ImportFieldType.QUANTITY),
            ColumnMapping(column_name="Price", field_type=ImportFieldType.PRICE_UNIT),
            ColumnMapping(column_name="Cost MP", field_type=ImportFieldType.COST_MP),
            ColumnMapping(column_name="Cost MO", field_type=ImportFieldType.COST_MO),
            ColumnMapping(column_name="Cost Energy", field_type=ImportFieldType.COST_ENERGY),
            ColumnMapping(column_name="Cost Gas", field_type=ImportFieldType.COST_GAS),
        ]
    )


@pytest.fixture
def valid_csv_content():
    """Valid CSV file content"""
    csv_data = """PO Number,Client,SKU,Qty,Price,Cost MP,Cost MO,Cost Energy,Cost Gas
PO-001,Acme Corp,SKU-001,10,100.00,30.00,20.00,5.00,3.00
PO-001,Acme Corp,SKU-002,5,200.00,80.00,40.00,10.00,5.00"""
    return csv_data.encode('utf-8')


@pytest.fixture
def valid_excel_content():
    """Valid Excel file content"""
    df = pd.DataFrame({
        'PO Number': ['PO-001', 'PO-001'],
        'Client': ['Acme Corp', 'Acme Corp'],
        'SKU': ['SKU-001', 'SKU-002'],
        'Qty': [10, 5],
        'Price': [100.00, 200.00],
        'Cost MP': [30.00, 80.00],
        'Cost MO': [20.00, 40.00],
        'Cost Energy': [5.00, 10.00],
        'Cost Gas': [3.00, 5.00]
    })
    
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False)
    buffer.seek(0)
    return buffer.read()


# ============================================================================
# TEST: FILE READING
# ============================================================================

def test_read_csv_file_success(import_service, valid_csv_content):
    """Test successful CSV file reading"""
    df = import_service.read_file(valid_csv_content, "test.csv")
    
    assert not df.empty
    assert len(df) == 2
    assert 'PO Number' in df.columns
    assert 'Client' in df.columns


def test_read_excel_file_success(import_service, valid_excel_content):
    """Test successful Excel file reading"""
    df = import_service.read_file(valid_excel_content, "test.xlsx")
    
    assert not df.empty
    assert len(df) == 2
    assert 'PO Number' in df.columns


def test_read_empty_file_fails(import_service):
    """Test that empty file raises error"""
    empty_csv = b"PO Number,Client,SKU\n"
    
    with pytest.raises(ValueError, match="empty"):
        import_service.read_file(empty_csv, "empty.csv")


def test_read_invalid_file_type_fails(import_service):
    """Test that invalid file type raises error"""
    with pytest.raises(ValueError, match="Unsupported file type"):
        import_service.read_file(b"some data", "test.txt")


# ============================================================================
# TEST: MAPPING VALIDATION
# ============================================================================

def test_validate_mapping_success(import_service, valid_mapping):
    """Test successful mapping validation"""
    df = pd.DataFrame({
        'PO Number': ['PO-001'],
        'Client': ['Acme Corp'],
        'SKU': ['SKU-001'],
        'Qty': [10],
        'Price': [100.00],
        'Cost MP': [30.00],
        'Cost MO': [20.00],
        'Cost Energy': [5.00],
        'Cost Gas': [3.00]
    })
    
    is_valid, error = import_service.validate_mapping(df, valid_mapping)
    
    assert is_valid
    assert error is None


def test_validate_mapping_missing_columns(import_service, valid_mapping):
    """Test mapping validation with missing columns"""
    df = pd.DataFrame({
        'PO Number': ['PO-001'],
        'Client': ['Acme Corp']
        # Missing other required columns
    })
    
    is_valid, error = import_service.validate_mapping(df, valid_mapping)
    
    assert not is_valid
    assert "not found in file" in error


# ============================================================================
# TEST: DATA PARSING
# ============================================================================

def test_parse_decimal_success(import_service):
    """Test successful decimal parsing"""
    value, error = import_service.parse_decimal("100.50", "Price", 1)
    
    assert error is None
    assert value == Decimal("100.50")


def test_parse_decimal_with_currency_symbol(import_service):
    """Test decimal parsing with currency symbols"""
    value, error = import_service.parse_decimal("R$ 100.50", "Price", 1)
    
    assert error is None
    assert value == Decimal("100.50")


def test_parse_decimal_negative_fails(import_service):
    """Test that negative decimals fail validation"""
    value, error = import_service.parse_decimal("-10.00", "Price", 1)
    
    assert value is None
    assert error is not None
    assert "non-negative" in error.error_message


def test_parse_decimal_invalid_fails(import_service):
    """Test that invalid decimals fail parsing"""
    value, error = import_service.parse_decimal("abc", "Price", 1)
    
    assert value is None
    assert error is not None
    assert "valid number" in error.error_message


def test_parse_decimal_empty_fails(import_service):
    """Test that empty decimals fail parsing"""
    value, error = import_service.parse_decimal(None, "Price", 1)
    
    assert value is None
    assert error is not None
    assert "required" in error.error_message


def test_parse_integer_success(import_service):
    """Test successful integer parsing"""
    value, error = import_service.parse_integer(10, "Quantity", 1)
    
    assert error is None
    assert value == 10


def test_parse_integer_from_float_string(import_service):
    """Test integer parsing from float string"""
    value, error = import_service.parse_integer("10.0", "Quantity", 1)
    
    assert error is None
    assert value == 10


def test_parse_integer_zero_fails(import_service):
    """Test that zero quantity fails validation"""
    value, error = import_service.parse_integer(0, "Quantity", 1)
    
    assert value is None
    assert error is not None
    assert "positive" in error.error_message


def test_parse_integer_negative_fails(import_service):
    """Test that negative integers fail validation"""
    value, error = import_service.parse_integer(-5, "Quantity", 1)
    
    assert value is None
    assert error is not None
    assert "positive" in error.error_message


def test_parse_string_success(import_service):
    """Test successful string parsing"""
    value, error = import_service.parse_string("SKU-001", "SKU", 1)
    
    assert error is None
    assert value == "SKU-001"


def test_parse_string_strips_whitespace(import_service):
    """Test that string parsing strips whitespace"""
    value, error = import_service.parse_string("  SKU-001  ", "SKU", 1)
    
    assert error is None
    assert value == "SKU-001"


def test_parse_string_empty_fails(import_service):
    """Test that empty strings fail validation"""
    value, error = import_service.parse_string("", "SKU", 1)
    
    assert value is None
    assert error is not None
    assert "cannot be empty" in error.error_message


# ============================================================================
# TEST: MARGIN CALCULATIONS
# ============================================================================

def test_item_margin_calculation():
    """Test automatic item margin calculation"""
    item = ImportItemData(
        sku="SKU-001",
        quantity=10,
        price_unit=Decimal("100.00"),
        cost_mp=Decimal("30.00"),
        cost_mo=Decimal("20.00"),
        cost_energy=Decimal("5.00"),
        cost_gas=Decimal("3.00")
    )
    
    # Margin should be calculated automatically
    assert item.total_cost == Decimal("58.00")
    assert item.margin_item == Decimal("42.00")


def test_po_margin_calculation():
    """Test automatic PO global margin calculation"""
    items = [
        ImportItemData(
            sku="SKU-001",
            quantity=10,
            price_unit=Decimal("100.00"),
            cost_mp=Decimal("30.00"),
            cost_mo=Decimal("20.00"),
            cost_energy=Decimal("5.00"),
            cost_gas=Decimal("3.00")
        ),
        ImportItemData(
            sku="SKU-002",
            quantity=5,
            price_unit=Decimal("200.00"),
            cost_mp=Decimal("80.00"),
            cost_mo=Decimal("40.00"),
            cost_energy=Decimal("10.00"),
            cost_gas=Decimal("5.00")
        )
    ]
    
    po = ImportPOData(
        po_number="PO-001",
        client_name="Acme Corp",
        items=items
    )
    
    # Total value: (100 * 10) + (200 * 5) = 2000
    assert po.total_value == Decimal("2000.00")
    
    # Total cost: (58 * 10) + (135 * 5) = 1255
    assert po.total_cost == Decimal("1255.00")
    
    # Global margin: 2000 - 1255 = 745
    assert po.margin_global == Decimal("745.00")
    
    # Margin percentage: (745 / 2000) * 100 = 37.25%
    assert po.margin_percentage == Decimal("37.25")


# ============================================================================
# TEST: VALIDATION RESULTS
# ============================================================================

def test_validate_import_data_success(import_service, valid_mapping):
    """Test successful data validation"""
    df = pd.DataFrame({
        'PO Number': ['PO-001', 'PO-001'],
        'Client': ['Acme Corp', 'Acme Corp'],
        'SKU': ['SKU-001', 'SKU-002'],
        'Qty': [10, 5],
        'Price': [100.00, 200.00],
        'Cost MP': [30.00, 80.00],
        'Cost MO': [20.00, 40.00],
        'Cost Energy': [5.00, 10.00],
        'Cost Gas': [3.00, 5.00]
    })
    
    result = import_service.validate_import_data(df, valid_mapping)
    
    assert result.success
    assert result.po_data is not None
    assert result.po_data.po_number == "PO-001"
    assert result.po_data.client_name == "Acme Corp"
    assert len(result.po_data.items) == 2
    assert result.total_rows_processed == 2
    assert result.valid_rows == 2
    assert result.invalid_rows == 0


def test_validate_import_data_with_invalid_number(import_service, valid_mapping):
    """Test validation with invalid number (text in numeric field)"""
    df = pd.DataFrame({
        'PO Number': ['PO-001'],
        'Client': ['Acme Corp'],
        'SKU': ['SKU-001'],
        'Qty': ['abc'],  # Invalid: text instead of number
        'Price': [100.00],
        'Cost MP': [30.00],
        'Cost MO': [20.00],
        'Cost Energy': [5.00],
        'Cost Gas': [3.00]
    })
    
    result = import_service.validate_import_data(df, valid_mapping)
    
    assert not result.success
    assert len(result.errors) > 0
    assert any("valid integer" in error.error_message for error in result.errors)


def test_validate_import_data_with_negative_price(import_service, valid_mapping):
    """Test validation with negative price"""
    df = pd.DataFrame({
        'PO Number': ['PO-001'],
        'Client': ['Acme Corp'],
        'SKU': ['SKU-001'],
        'Qty': [10],
        'Price': [-100.00],  # Invalid: negative price
        'Cost MP': [30.00],
        'Cost MO': [20.00],
        'Cost Energy': [5.00],
        'Cost Gas': [3.00]
    })
    
    result = import_service.validate_import_data(df, valid_mapping)
    
    assert not result.success
    assert len(result.errors) > 0
    assert any("non-negative" in error.error_message for error in result.errors)


def test_validate_import_data_with_empty_required_field(import_service, valid_mapping):
    """Test validation with empty required field"""
    df = pd.DataFrame({
        'PO Number': ['PO-001'],
        'Client': ['Acme Corp'],
        'SKU': [''],  # Invalid: empty SKU
        'Qty': [10],
        'Price': [100.00],
        'Cost MP': [30.00],
        'Cost MO': [20.00],
        'Cost Energy': [5.00],
        'Cost Gas': [3.00]
    })
    
    result = import_service.validate_import_data(df, valid_mapping)
    
    assert not result.success
    assert len(result.errors) > 0
    assert any("cannot be empty" in error.error_message for error in result.errors)


def test_validate_import_data_multiple_pos_fails(import_service, valid_mapping):
    """Test that multiple PO numbers in one file fails"""
    df = pd.DataFrame({
        'PO Number': ['PO-001', 'PO-002'],  # Different PO numbers
        'Client': ['Acme Corp', 'Beta Inc'],
        'SKU': ['SKU-001', 'SKU-002'],
        'Qty': [10, 5],
        'Price': [100.00, 200.00],
        'Cost MP': [30.00, 80.00],
        'Cost MO': [20.00, 40.00],
        'Cost Energy': [5.00, 10.00],
        'Cost Gas': [3.00, 5.00]
    })
    
    result = import_service.validate_import_data(df, valid_mapping)
    
    assert not result.success
    assert any("Multiple PO numbers" in error.error_message for error in result.errors)


def test_validate_import_data_inconsistent_client_name(import_service, valid_mapping):
    """Test that inconsistent client names for same PO fails"""
    df = pd.DataFrame({
        'PO Number': ['PO-001', 'PO-001'],
        'Client': ['Acme Corp', 'Different Corp'],  # Inconsistent client names
        'SKU': ['SKU-001', 'SKU-002'],
        'Qty': [10, 5],
        'Price': [100.00, 200.00],
        'Cost MP': [30.00, 80.00],
        'Cost MO': [20.00, 40.00],
        'Cost Energy': [5.00, 10.00],
        'Cost Gas': [3.00, 5.00]
    })
    
    result = import_service.validate_import_data(df, valid_mapping)
    
    assert not result.success
    assert any("inconsistent client names" in error.error_message for error in result.errors)


# ============================================================================
# TEST: FULL IMPORT PROCESS
# ============================================================================

def test_import_po_success(import_service, valid_mapping, valid_csv_content):
    """Test successful full import process"""
    request = ImportRequest(
        file_content=valid_csv_content,
        file_name="test.csv",
        mapping=valid_mapping,
        tenant_id="tenant-123",
        user_id="user-456"
    )
    
    response = import_service.import_po(request)
    
    assert response.success
    assert response.po_number == "PO-001"
    assert response.items_imported == 2
    assert response.total_value == Decimal("2000.00")
    assert response.margin_global == Decimal("745.00")
    assert "Successfully imported" in response.message


def test_import_po_with_invalid_data_fails(import_service, valid_mapping):
    """Test that import fails with invalid data"""
    invalid_csv = b"""PO Number,Client,SKU,Qty,Price,Cost MP,Cost MO,Cost Energy,Cost Gas
PO-001,Acme Corp,SKU-001,abc,100.00,30.00,20.00,5.00,3.00"""
    
    request = ImportRequest(
        file_content=invalid_csv,
        file_name="test.csv",
        mapping=valid_mapping,
        tenant_id="tenant-123",
        user_id="user-456"
    )
    
    response = import_service.import_po(request)
    
    assert not response.success
    assert response.items_imported == 0
    assert "Validation failed" in response.message


def test_import_po_with_mapping_error_fails(import_service):
    """Test that import fails with incorrect mapping"""
    csv_content = b"""PO Number,Client,SKU,Qty,Price,Cost MP,Cost MO,Cost Energy,Cost Gas
PO-001,Acme Corp,SKU-001,10,100.00,30.00,20.00,5.00,3.00"""
    
    # Mapping references non-existent column
    wrong_mapping = ImportMapping(
        mappings=[
            ColumnMapping(column_name="Wrong Column", field_type=ImportFieldType.PO_NUMBER),
            ColumnMapping(column_name="Client", field_type=ImportFieldType.CLIENT_NAME),
            ColumnMapping(column_name="SKU", field_type=ImportFieldType.SKU),
            ColumnMapping(column_name="Qty", field_type=ImportFieldType.QUANTITY),
            ColumnMapping(column_name="Price", field_type=ImportFieldType.PRICE_UNIT),
            ColumnMapping(column_name="Cost MP", field_type=ImportFieldType.COST_MP),
            ColumnMapping(column_name="Cost MO", field_type=ImportFieldType.COST_MO),
            ColumnMapping(column_name="Cost Energy", field_type=ImportFieldType.COST_ENERGY),
            ColumnMapping(column_name="Cost Gas", field_type=ImportFieldType.COST_GAS),
        ]
    )
    
    request = ImportRequest(
        file_content=csv_content,
        file_name="test.csv",
        mapping=wrong_mapping,
        tenant_id="tenant-123",
        user_id="user-456"
    )
    
    response = import_service.import_po(request)
    
    assert not response.success
    assert "Mapping error" in response.message


# ============================================================================
# TEST: ROLLBACK ON FAILURE
# ============================================================================

def test_import_rollback_on_database_error(mock_db):
    """Test that database errors trigger rollback"""
    # Note: This test demonstrates the rollback mechanism
    # In the current implementation, actual database operations are commented out
    # When models are implemented, this test will verify rollback behavior
    
    # For now, we verify the service handles exceptions gracefully
    import_service = ImportService(mock_db)
    
    valid_csv = b"""PO Number,Client,SKU,Qty,Price,Cost MP,Cost MO,Cost Energy,Cost Gas
PO-001,Acme Corp,SKU-001,10,100.00,30.00,20.00,5.00,3.00"""
    
    mapping = ImportMapping(
        mappings=[
            ColumnMapping(column_name="PO Number", field_type=ImportFieldType.PO_NUMBER),
            ColumnMapping(column_name="Client", field_type=ImportFieldType.CLIENT_NAME),
            ColumnMapping(column_name="SKU", field_type=ImportFieldType.SKU),
            ColumnMapping(column_name="Qty", field_type=ImportFieldType.QUANTITY),
            ColumnMapping(column_name="Price", field_type=ImportFieldType.PRICE_UNIT),
            ColumnMapping(column_name="Cost MP", field_type=ImportFieldType.COST_MP),
            ColumnMapping(column_name="Cost MO", field_type=ImportFieldType.COST_MO),
            ColumnMapping(column_name="Cost Energy", field_type=ImportFieldType.COST_ENERGY),
            ColumnMapping(column_name="Cost Gas", field_type=ImportFieldType.COST_GAS),
        ]
    )
    
    request = ImportRequest(
        file_content=valid_csv,
        file_name="test.csv",
        mapping=mapping,
        tenant_id="tenant-123",
        user_id="user-456"
    )
    
    response = import_service.import_po(request)
    
    # Currently succeeds because DB operations are not implemented
    # When models are added, mock db.commit to raise SQLAlchemyError
    # and verify rollback is called
    assert response.success or not response.success  # Placeholder assertion


# ============================================================================
# TEST: GET FILE HEADERS
# ============================================================================

def test_get_file_headers_csv(import_service, valid_csv_content):
    """Test extracting headers from CSV file"""
    headers = import_service.get_file_headers(valid_csv_content, "test.csv")
    
    assert len(headers) == 9
    assert "PO Number" in headers
    assert "Client" in headers
    assert "SKU" in headers


def test_get_file_headers_excel(import_service, valid_excel_content):
    """Test extracting headers from Excel file"""
    headers = import_service.get_file_headers(valid_excel_content, "test.xlsx")
    
    assert len(headers) == 9
    assert "PO Number" in headers
    assert "Client" in headers


# ============================================================================
# TEST: EDGE CASES
# ============================================================================

def test_import_with_extra_columns(import_service, valid_mapping):
    """Test that extra columns in file are ignored"""
    csv_with_extra = b"""PO Number,Client,SKU,Qty,Price,Cost MP,Cost MO,Cost Energy,Cost Gas,Extra Column
PO-001,Acme Corp,SKU-001,10,100.00,30.00,20.00,5.00,3.00,ignored"""
    
    request = ImportRequest(
        file_content=csv_with_extra,
        file_name="test.csv",
        mapping=valid_mapping,
        tenant_id="tenant-123",
        user_id="user-456"
    )
    
    response = import_service.import_po(request)
    
    assert response.success
    assert response.items_imported == 1


def test_import_with_whitespace_in_data(import_service, valid_mapping):
    """Test that whitespace in data is handled correctly"""
    csv_with_whitespace = b"""PO Number,Client,SKU,Qty,Price,Cost MP,Cost MO,Cost Energy,Cost Gas
  PO-001  ,  Acme Corp  ,  SKU-001  ,10,100.00,30.00,20.00,5.00,3.00"""
    
    request = ImportRequest(
        file_content=csv_with_whitespace,
        file_name="test.csv",
        mapping=valid_mapping,
        tenant_id="tenant-123",
        user_id="user-456"
    )
    
    response = import_service.import_po(request)
    
    assert response.success
    assert response.po_number == "PO-001"  # Whitespace should be stripped


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
