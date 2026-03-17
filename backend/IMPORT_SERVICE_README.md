# FlexFlow Dynamic Import Service

## Overview

The FlexFlow Import Service provides a robust, production-ready solution for importing Purchase Orders from Excel/CSV files with dynamic column mapping, automatic margin calculations, and full data validation.

## Features

### ✅ 1. Dynamic Column Mapping
- **Flexible Headers**: Map any column name from your spreadsheet to system fields
- **User-Friendly**: No need to rename columns in your Excel files
- **Validation**: Ensures all required fields are mapped before import

### ✅ 2. Automatic Margin Calculation
- **Item-Level Margins**: `margin_item = price_unit - (cost_mp + cost_mo + cost_energy + cost_gas)`
- **Global PO Margin**: Calculates total margin across all items
- **Margin Percentage**: Provides margin as a percentage of total value

### ✅ 3. Comprehensive Data Validation
- **Type Checking**: Validates numbers, decimals, and strings
- **Business Rules**: Enforces positive quantities, non-negative prices
- **Detailed Errors**: Provides row-by-row error reporting with exact locations

### ✅ 4. Atomicity (All-or-Nothing)
- **Transaction Safety**: If any item fails validation, entire import is cancelled
- **Rollback Support**: Database rollback on any error
- **Clear Error Messages**: Detailed feedback on what went wrong

### ✅ 5. Multi-Tenancy Support
- **Tenant Isolation**: All imported data is linked to the correct tenant
- **User Tracking**: Records which user performed the import
- **Security**: Ensures data segregation

### ✅ 6. Status Management
- **Initial Status**: All imported items start with `NOVO_PEDIDO` status
- **Workflow Integration**: Ready for state machine transitions

## Architecture

```
┌─────────────────┐
│   Excel/CSV     │
│   File Upload   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Column Mapping │ ◄── User defines mapping
│   Configuration │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  File Reading   │
│  (pandas)       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Data Parsing   │
│  & Validation   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Margin         │
│  Calculation    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Database       │
│  Transaction    │ ◄── Rollback on error
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Success/Error  │
│  Response       │
└─────────────────┘
```

## Required Fields

Every import must map these 9 fields:

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| `po_number` | String | Purchase Order number | Required, non-empty |
| `client_name` | String | Client/Customer name | Required, non-empty |
| `sku` | String | Product SKU/Code | Required, non-empty |
| `quantity` | Integer | Item quantity | Required, > 0 |
| `price_unit` | Decimal | Unit price | Required, ≥ 0 |
| `cost_mp` | Decimal | Material cost (Matéria Prima) | Required, ≥ 0 |
| `cost_mo` | Decimal | Labor cost (Mão de Obra) | Required, ≥ 0 |
| `cost_energy` | Decimal | Energy cost | Required, ≥ 0 |
| `cost_gas` | Decimal | Gas cost | Required, ≥ 0 |

## Usage Examples

### 1. Basic Import

```python
from backend.services.import_service import ImportService
from backend.schemas.import_schema import ImportMapping, ColumnMapping, ImportFieldType, ImportRequest

# Initialize service
db = get_db_session()
import_service = ImportService(db)

# Define column mapping
mapping = ImportMapping(
    mappings=[
        ColumnMapping(column_name="Número PO", field_type=ImportFieldType.PO_NUMBER),
        ColumnMapping(column_name="Cliente", field_type=ImportFieldType.CLIENT_NAME),
        ColumnMapping(column_name="SKU", field_type=ImportFieldType.SKU),
        ColumnMapping(column_name="Quantidade", field_type=ImportFieldType.QUANTITY),
        ColumnMapping(column_name="Preço Unitário", field_type=ImportFieldType.PRICE_UNIT),
        ColumnMapping(column_name="Custo MP", field_type=ImportFieldType.COST_MP),
        ColumnMapping(column_name="Custo MO", field_type=ImportFieldType.COST_MO),
        ColumnMapping(column_name="Custo Energia", field_type=ImportFieldType.COST_ENERGY),
        ColumnMapping(column_name="Custo Gás", field_type=ImportFieldType.COST_GAS),
    ]
)

# Read file
with open("pedido.xlsx", "rb") as f:
    file_content = f.read()

# Create import request
request = ImportRequest(
    file_content=file_content,
    file_name="pedido.xlsx",
    mapping=mapping,
    tenant_id="tenant-uuid",
    user_id="user-uuid"
)

# Execute import
response = import_service.import_po(request)

if response.success:
    print(f"✅ Import successful!")
    print(f"PO Number: {response.po_number}")
    print(f"Items imported: {response.items_imported}")
    print(f"Total value: R$ {response.total_value}")
    print(f"Global margin: R$ {response.margin_global} ({response.margin_percentage}%)")
else:
    print(f"❌ Import failed: {response.message}")
    if response.validation_result:
        for error in response.validation_result.errors:
            print(f"  - Row {error.row_number}: {error.error_message}")
```

### 2. Get File Headers (for UI mapping)

```python
# Extract headers from uploaded file
with open("pedido.xlsx", "rb") as f:
    file_content = f.read()

headers = import_service.get_file_headers(file_content, "pedido.xlsx")
print("Available columns:", headers)
# Output: ['Número PO', 'Cliente', 'SKU', 'Quantidade', ...]
```

### 3. Validate Before Import

```python
# Read and validate without saving
df = import_service.read_file(file_content, "pedido.xlsx")
validation_result = import_service.validate_import_data(df, mapping)

if validation_result.success:
    po_data = validation_result.po_data
    print(f"PO: {po_data.po_number}")
    print(f"Client: {po_data.client_name}")
    print(f"Items: {len(po_data.items)}")
    print(f"Total margin: R$ {po_data.margin_global}")
else:
    print("Validation errors:")
    for error in validation_result.errors:
        print(f"  - {error.error_message}")
```

## Example Excel/CSV Format

### Input File (pedido.xlsx)

| Número PO | Cliente | SKU | Quantidade | Preço Unitário | Custo MP | Custo MO | Custo Energia | Custo Gás |
|-----------|---------|-----|------------|----------------|----------|----------|---------------|-----------|
| PO-2024-001 | Acme Corp | SKU-001 | 100 | 150.00 | 50.00 | 30.00 | 10.00 | 5.00 |
| PO-2024-001 | Acme Corp | SKU-002 | 50 | 200.00 | 80.00 | 40.00 | 15.00 | 10.00 |

### Calculated Results

**Item 1:**
- Total Cost: 50 + 30 + 10 + 5 = R$ 95.00
- Margin: 150 - 95 = R$ 55.00
- Total Value: 100 × 150 = R$ 15,000.00

**Item 2:**
- Total Cost: 80 + 40 + 15 + 10 = R$ 145.00
- Margin: 200 - 145 = R$ 55.00
- Total Value: 50 × 200 = R$ 10,000.00

**PO Totals:**
- Total Value: R$ 25,000.00
- Total Cost: (95 × 100) + (145 × 50) = R$ 16,750.00
- Global Margin: R$ 8,250.00
- Margin %: 33%

## Error Handling

### Common Validation Errors

#### 1. Invalid Number Format
```
❌ Row 3: Quantity must be a valid integer, got: "abc"
```

#### 2. Negative Values
```
❌ Row 5: Unit Price must be non-negative
```

#### 3. Empty Required Fields
```
❌ Row 7: SKU cannot be empty
```

#### 4. Multiple PO Numbers
```
❌ Multiple PO numbers found in file: PO-001, PO-002. Please import one PO at a time.
```

#### 5. Inconsistent Client Names
```
❌ PO PO-001 has inconsistent client names: 'Acme Corp' vs 'Different Corp'
```

### Atomicity Example

```python
# File with 10 rows, row 8 has invalid data
response = import_service.import_po(request)

# Result: NO rows are imported (all-or-nothing)
assert response.success == False
assert response.items_imported == 0
assert "Row 8" in response.message
```

## Testing

Run the comprehensive test suite:

```bash
# Run all import service tests
pytest backend/tests/test_import_service.py -v

# Run specific test
pytest backend/tests/test_import_service.py::test_import_po_success -v

# Run with coverage
pytest backend/tests/test_import_service.py --cov=backend.services.import_service
```

### Test Coverage

The test suite covers:
- ✅ File reading (CSV, Excel)
- ✅ Column mapping validation
- ✅ Data type parsing (decimal, integer, string)
- ✅ Margin calculations (item and global)
- ✅ Validation errors (detailed error reporting)
- ✅ Rollback on database errors
- ✅ Edge cases (whitespace, extra columns, etc.)

## API Integration

### FastAPI Endpoint Example

```python
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.services.import_service import ImportService
from backend.schemas.import_schema import ImportMapping, ImportResponse
from backend.database import get_db
from backend.middleware import get_current_user

router = APIRouter(prefix="/api/import", tags=["import"])

@router.post("/po", response_model=ImportResponse)
async def import_purchase_order(
    file: UploadFile = File(...),
    mapping: ImportMapping = Depends(),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Import a Purchase Order from Excel/CSV file.
    
    - **file**: Excel (.xlsx, .xls) or CSV file
    - **mapping**: Column mapping configuration
    """
    # Read file content
    file_content = await file.read()
    
    # Create import request
    request = ImportRequest(
        file_content=file_content,
        file_name=file.filename,
        mapping=mapping,
        tenant_id=str(current_user.tenant_id),
        user_id=str(current_user.id)
    )
    
    # Execute import
    import_service = ImportService(db)
    response = import_service.import_po(request)
    
    if not response.success:
        raise HTTPException(status_code=400, detail=response.message)
    
    return response

@router.post("/headers")
async def get_file_headers(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Extract column headers from uploaded file for mapping UI.
    """
    file_content = await file.read()
    
    import_service = ImportService(db)
    headers = import_service.get_file_headers(file_content, file.filename)
    
    return {"headers": headers}
```

## Performance Considerations

### File Size Limits
- **Recommended**: < 1000 rows per file
- **Maximum**: 10,000 rows (adjust based on server capacity)
- **Memory**: Uses pandas for efficient processing

### Optimization Tips
1. **Batch Processing**: For large imports, split into multiple files
2. **Async Processing**: Consider background tasks for very large files
3. **Caching**: Cache column mappings for repeated imports
4. **Indexing**: Ensure database indexes on `tenant_id` and `po_number`

## Security

### Multi-Tenancy
- All records automatically tagged with `tenant_id`
- User cannot import data for other tenants
- Validation ensures tenant isolation

### Input Validation
- File type validation (only .xlsx, .xls, .csv)
- Size limits enforced
- SQL injection prevention (parameterized queries)
- XSS prevention (data sanitization)

## Future Enhancements

### Planned Features
- [ ] Support for multiple PO numbers in one file
- [ ] Async/background processing for large files
- [ ] Import history and audit trail
- [ ] Template download for users
- [ ] Duplicate detection
- [ ] Partial import option (import valid rows, skip invalid)
- [ ] Custom validation rules per tenant
- [ ] Import scheduling

## Troubleshooting

### Issue: "File is empty or contains no valid data"
**Solution**: Ensure file has header row and at least one data row

### Issue: "Columns not found in file"
**Solution**: Check column names match exactly (case-sensitive)

### Issue: "Multiple PO numbers found"
**Solution**: Split file into separate files, one per PO

### Issue: "Database error during import"
**Solution**: Check database connection and permissions

## Support

For issues or questions:
1. Check this documentation
2. Review test cases in `test_import_service.py`
3. Check error messages for specific guidance
4. Contact development team

---

**Version**: 1.0.0  
**Last Updated**: 2026-03-17  
**Author**: FlexFlow Development Team
