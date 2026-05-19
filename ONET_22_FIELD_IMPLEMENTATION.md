# ONET 22-Field Structure Implementation

## Overview
Complete implementation of the 22-field ONET data structure with financial integrity validation.

**Date:** 2026-05-19  
**Status:** ✅ IMPLEMENTED

---

## 📋 22-Field Structure

### Core Fields (1-4)
1. **Pedido** - PO Number
2. **Cliente** - Client Name
3. **SKU** - Product SKU
4. **Descrição** - Product Description

### Quantity & Unit (5-6)
5. **Qtd** - Quantity
6. **Unidade** - Unit of Measure

### Dimensions (7-8)
7. **Largura** - Width (mm)
8. **Comprimento** - Length (mm)

### Timeline (9-11)
9. **Lead Time** - Lead time in days
10. **Data Entrega** - Delivery Date
11. **Data Faturamento** - Billing Date

### Tax & Status (12-15)
12. **% ICMS** - ICMS Tax Percentage
13. **Bloqueio** - Credit Block Status
14. **Saldo** - Balance
15. **Atraso** - Delay in days

### Commercial (16-19)
16. **Condição Pagamento** - Payment Terms
17. **Frete** - Freight Cost
18. **Vendedor** - Salesperson
19. **IPI** - IPI Tax

### **NEW: Financial Values (20-22)** 💰
20. **Vl.Unit** - Unit Value (R$)
21. **Total Item** - Item Total (Qtd × Vl.Unit)
22. **Valor Total do Pedido** - PO Total Value (Σ Total Item)

---

## 🔒 Financial Integrity Validation

### Item-Level Validation
**Rule:** `Total Item = Qtd × Vl.Unit`

```python
@model_validator(mode='after')
def validate_item_total(self):
    """Validate that item_total_value matches quantity * unit_value"""
    if self.unit_value is not None and self.item_total_value is not None:
        expected_total = Decimal(str(self.quantity)) * self.unit_value
        tolerance = Decimal("0.01")  # 1 cent tolerance
        difference = abs(self.item_total_value - expected_total)
        
        if difference > tolerance:
            self.validation_errors.append(
                f"Divergência no Total Item: Esperado {expected_total:.2f} "
                f"(Qtd {self.quantity} × Vl.Unit {self.unit_value:.2f}), "
                f"mas encontrado {self.item_total_value:.2f}"
            )
    
    return self
```

### PO-Level Validation
**Rule:** `Valor Total do Pedido = Σ(Total Item)`

```python
@model_validator(mode='after')
def validate_po_integrity(self):
    """
    CRITICAL INTEGRITY CHECK:
    Validate that the sum of all item_total_value matches po_total_value.
    """
    if self.po_total_value is None:
        return self
    
    items_with_totals = [item for item in self.items if item.item_total_value is not None]
    
    if not items_with_totals:
        return self
    
    calculated_sum = sum(item.item_total_value for item in items_with_totals)
    tolerance = Decimal("0.01")  # 1 cent tolerance
    difference = abs(calculated_sum - self.po_total_value)
    
    if difference > tolerance:
        self.has_integrity_error = True
        self.integrity_error_message = (
            f"Divergência de valores: Soma dos itens (R$ {calculated_sum:.2f}) "
            f"não confere com o total do pedido (R$ {self.po_total_value:.2f}). "
            f"Diferença: R$ {difference:.2f}"
        )
    else:
        self.has_integrity_error = False
        self.integrity_error_message = None
    
    return self
```

---

## 🎨 Updated UI Layout

### PO Header Section
```jsx
<div className="grid grid-cols-3 gap-4 mb-4">
    <div>
        <label className="text-sm font-medium text-gray-700">Número PO</label>
        <p className="text-lg font-semibold text-gray-900">{currentPO.po_number}</p>
    </div>
    <div>
        <label className="text-sm font-medium text-gray-700">Cliente</label>
        <p className="text-lg font-semibold text-gray-900">{currentPO.client_name}</p>
    </div>
    <div>
        <label className="text-sm font-medium text-gray-700">💰 Valor Total do Pedido</label>
        <p className="text-lg font-semibold text-green-600">
            {currentPO.po_total_value 
                ? `R$ ${parseFloat(currentPO.po_total_value).toLocaleString('pt-BR', { 
                    minimumFractionDigits: 2, 
                    maximumFractionDigits: 2 
                })}` 
                : 'N/A'
            }
        </p>
    </div>
</div>
```

### Integrity Warning Banner
```jsx
{currentPO.has_integrity_error && (
    <div className="mb-4 p-4 bg-red-50 border-2 border-red-300 rounded-lg">
        <div className="flex items-start gap-3">
            <AlertCircle className="w-6 h-6 text-red-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
                <h4 className="text-sm font-bold text-red-900 mb-1">
                    ⚠️ Divergência de Valores Detectada
                </h4>
                <p className="text-sm text-red-800">
                    {currentPO.integrity_error_message || 
                     'A soma dos itens não confere com o total do pedido.'}
                </p>
                <p className="text-xs text-red-700 mt-2">
                    <strong>Ação necessária:</strong> Verifique os valores antes de 
                    marcar os itens como conferidos.
                </p>
            </div>
        </div>
    </div>
)}
```

### Item Row Display
```jsx
<div className="grid grid-cols-6 gap-4 mb-4">
    <div>
        <label className="text-xs font-medium text-gray-600">SKU</label>
        <p className="font-semibold text-gray-900">{item.sku}</p>
    </div>
    <div className="col-span-2">
        <label className="text-xs font-medium text-gray-600">Descrição do Produto</label>
        <p className="font-semibold text-gray-900 text-sm truncate" 
           title={item.description || 'N/A'}>
            {item.description || 'N/A'}
        </p>
    </div>
    <div>
        <label className="text-xs font-medium text-gray-600">Quantidade</label>
        <p className="font-semibold text-gray-900">{item.quantity}</p>
    </div>
    <div>
        <label className="text-xs font-medium text-gray-600">Vl.Unit</label>
        <p className="font-semibold text-gray-900">
            {item.unit_value 
                ? `R$ ${parseFloat(item.unit_value).toFixed(2)}` 
                : `R$ ${item.price_unit.toFixed(2)}`
            }
        </p>
    </div>
    <div>
        <label className="text-xs font-medium text-gray-600">Total Item</label>
        <p className="font-semibold text-green-600">
            {item.item_total_value 
                ? `R$ ${parseFloat(item.item_total_value).toFixed(2)}`
                : `R$ ${(item.quantity * item.price_unit).toFixed(2)}`
            }
        </p>
    </div>
</div>
```

### Conferido Logic Update
```javascript
const canCommit = () => {
    // Check if all items are checked and have no errors
    const allChecked = allItemsChecked()
    const noErrors = calculateSummary().withErrors === 0
    
    // Check if any PO has integrity errors
    const hasIntegrityErrors = stagingData?.po_list?.some(po => po.has_integrity_error) || false
    
    // User can only commit if:
    // 1. All items are checked
    // 2. No validation errors
    // 3. No integrity errors
    return allChecked && noErrors && !hasIntegrityErrors
}
```

---

## 📊 Mock Data Generator

### Financial Logic
```python
# Generate realistic unit values (R$ 5.00 to R$ 150.00)
unit_value = round(random.uniform(5.0, 150.0), 2)

# Calculate item total with integrity
item_total = round(quantity * unit_value, 2)

# Track PO totals
if po_number not in po_totals:
    po_totals[po_number] = 0.0
po_totals[po_number] += item_total

# Second pass: Fill in Valor Total do Pedido
for row in data:
    row['Valor Total do Pedido'] = po_totals[row['Pedido']]
```

### Verification
```python
# Verify integrity for sample PO
sample_po = df['Pedido'].iloc[0]
po_items = df[df['Pedido'] == sample_po]
calculated_total = po_items['Total Item'].sum()
declared_total = po_items['Valor Total do Pedido'].iloc[0]
difference = abs(calculated_total - declared_total)
status = '✓ ÍNTEGRO' if difference < 0.01 else '✗ DIVERGENTE'
```

---

## 🗄️ Database Schema Updates

### ImportItemData Schema
```python
class ImportItemData(BaseModel):
    # ... existing fields ...
    
    # NEW: Financial value fields (22-field structure)
    unit_value: Optional[Decimal] = Field(None, ge=0, description="Unit value (Vl.Unit)")
    item_total_value: Optional[Decimal] = Field(None, ge=0, description="Item total value (Total Item)")
```

### ImportPOData Schema
```python
class ImportPOData(BaseModel):
    # ... existing fields ...
    
    # NEW: PO total value from spreadsheet
    po_total_value: Optional[Decimal] = Field(
        None, 
        ge=0, 
        description="PO total value from spreadsheet (Valor Total do Pedido)"
    )
    
    # Integrity check fields
    has_integrity_error: bool = Field(default=False, description="Whether PO has integrity errors")
    integrity_error_message: Optional[str] = Field(None, description="Integrity error details")
```

### ImportFieldType Enum
```python
class ImportFieldType(str, Enum):
    # ... existing fields ...
    
    # NEW: Financial value fields (22-field structure)
    UNIT_VALUE = "unit_value"  # Vl.Unit
    ITEM_TOTAL_VALUE = "item_total_value"  # Total Item
    PO_TOTAL_VALUE = "po_total_value"  # Valor Total do Pedido
```

---

## 🔄 Import Mapping

### Frontend Mapping (22 fields)
```javascript
const defaultMapping = {
    mappings: [
        // Core required fields
        { column_name: 'Pedido', field_type: 'po_number' },
        { column_name: 'Cliente', field_type: 'client_name' },
        { column_name: 'SKU', field_type: 'sku' },
        { column_name: 'Qtd', field_type: 'quantity' },
        // Optional ONET fields (22-field structure)
        { column_name: 'Descrição', field_type: 'description' },
        { column_name: 'Unidade', field_type: 'unit' },
        { column_name: 'Largura', field_type: 'width' },
        { column_name: 'Comprimento', field_type: 'length' },
        { column_name: 'Lead Time', field_type: 'lead_time' },
        { column_name: 'Data Entrega', field_type: 'delivery_date' },
        { column_name: 'Data Faturamento', field_type: 'billing_date' },
        { column_name: '% ICMS', field_type: 'icms_percent' },
        { column_name: 'Bloqueio', field_type: 'block_status' },
        { column_name: 'Saldo', field_type: 'balance' },
        { column_name: 'Atraso', field_type: 'delay' },
        { column_name: 'Condição Pagamento', field_type: 'payment_terms' },
        { column_name: 'Frete', field_type: 'freight' },
        { column_name: 'Vendedor', field_type: 'salesperson' },
        { column_name: 'IPI', field_type: 'ipi' },
        // NEW: Financial value fields
        { column_name: 'Vl.Unit', field_type: 'unit_value' },
        { column_name: 'Total Item', field_type: 'item_total_value' },
        { column_name: 'Valor Total do Pedido', field_type: 'po_total_value' }
    ]
}
```

---

## ✅ Implementation Checklist

- [x] **Mock Generator** - Updated to generate 22 columns with financial integrity
- [x] **Backend Schemas** - Added financial fields and PO integrity validator
- [x] **Import Mapping** - Updated to include 3 new financial fields
- [x] **UI Header** - Display Valor Total do Pedido prominently
- [x] **UI Rows** - Display Descrição, Vl.Unit, and Total Item
- [x] **Integrity Warning** - Show banner when sum mismatch detected
- [x] **Conferido Logic** - Block commit if integrity errors exist
- [ ] **Database Models** - Add explicit financial columns
- [ ] **Financial Service** - Update margin calculations to use real values
- [ ] **Testing** - Generate and import test file

---

## 🎯 Business Rules

### Integrity Validation Rules
1. **Item Level:** Total Item must equal Qtd × Vl.Unit (tolerance: R$ 0.01)
2. **PO Level:** Valor Total do Pedido must equal Σ(Total Item) (tolerance: R$ 0.01)
3. **Conferido Block:** Users cannot mark items as "Conferido" if PO has integrity errors
4. **Commit Block:** System prevents commit if any PO has integrity errors

### Error Messages
- **Item Divergence:** "Divergência no Total Item: Esperado {expected} (Qtd {qty} × Vl.Unit {unit}), mas encontrado {actual}"
- **PO Divergence:** "Divergência de valores: Soma dos itens (R$ {sum}) não confere com o total do pedido (R$ {total}). Diferença: R$ {diff}"

---

## 📈 Next Steps

1. **Database Migration:** Add `unit_value`, `item_total_value`, `po_total_value` columns to OrderItem and PurchaseOrder tables
2. **Financial Service Update:** Modify margin calculations to use real `unit_value` instead of mocks
3. **Dashboard Integration:** Display PO totals and item totals in financial reports
4. **Testing:** Generate mock file and test complete import flow with integrity validation

---

## 🔍 Testing Scenarios

### Valid Scenario
- PO with 3 items
- Item 1: Qtd=100, Vl.Unit=10.00, Total Item=1000.00
- Item 2: Qtd=50, Vl.Unit=20.00, Total Item=1000.00
- Item 3: Qtd=200, Vl.Unit=5.00, Total Item=1000.00
- **Valor Total do Pedido:** R$ 3,000.00 ✓

### Invalid Scenario
- PO with 2 items
- Item 1: Qtd=100, Vl.Unit=10.00, Total Item=1000.00
- Item 2: Qtd=50, Vl.Unit=20.00, Total Item=1000.00
- **Valor Total do Pedido:** R$ 2,500.00 ✗ (Expected: R$ 2,000.00)
- **Error:** "Divergência de valores: Soma dos itens (R$ 2,000.00) não confere com o total do pedido (R$ 2,500.00). Diferença: R$ 500.00"

---

**Implementation Complete:** Mock Generator, Schemas, UI, and Integrity Validator  
**Remaining:** Database Models, Financial Service, Testing
