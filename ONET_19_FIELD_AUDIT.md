# ONET 19-FIELD GLOBAL MAPPING AUDIT

**Date:** 2026-05-15  
**Issue:** PRICE_UNIT causing "Unexpected error" during import  
**Root Cause:** Key mismatch between frontend mapping and backend service expectations

---

## 🔴 CRITICAL ISSUES FOUND

### Issue #1: Missing PRICE_UNIT in Frontend Mapping
**File:** `frontend/src/pages/ImportPage.jsx` (lines 62-84)  
**Problem:** The frontend sends 19 ONET fields but does NOT include any cost/price fields that the backend service requires.

**Frontend Mapping (Current):**
```javascript
{ column_name: 'Pedido', field_type: 'po_number' },
{ column_name: 'Cliente', field_type: 'client_name' },
{ column_name: 'SKU', field_type: 'sku' },
{ column_name: 'Qtd', field_type: 'quantity' },
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
{ column_name: 'IPI', field_type: 'ipi' }
// ❌ MISSING: price_unit, cost_mp, cost_mo, cost_energy, cost_gas
```

### Issue #2: Backend Service Expects Cost Fields
**File:** `backend/services/import_service.py` (lines 316-354)  
**Problem:** The `parse_row()` method REQUIRES these fields to exist in mapping_dict:
- `PRICE_UNIT` (line 317)
- `COST_MP` (line 325)
- `COST_MO` (line 333)
- `COST_ENERGY` (line 341)
- `COST_GAS` (line 349)

**Backend Code (Current):**
```python
# Line 317: This FAILS because PRICE_UNIT is not in mapping_dict
price_col = field_to_column[ImportFieldType.PRICE_UNIT]
price_unit, error = self.parse_decimal(row[price_col], "Unit Price", row_number)
```

**Error Flow:**
1. Frontend sends mapping WITHOUT `price_unit`
2. Backend creates `field_to_column` dict from mapping
3. Backend tries to access `field_to_column[ImportFieldType.PRICE_UNIT]`
4. **KeyError** → Caught as "Unexpected error"

### Issue #3: Schema Defines Fields as Optional but Service Treats as Required
**File:** `backend/schemas/import_schema.py`  
**Problem:** Schema says cost fields are optional (lines 156-161), but service requires them (lines 316-354).

---

## 📊 FIELD-BY-FIELD COMPARISON

| # | Field Name | Generator | Frontend | Schema | Service | Status |
|---|------------|-----------|----------|--------|---------|--------|
| 1 | Pedido | ✅ | ✅ po_number | ✅ PO_NUMBER | ✅ Required | ✅ SYNCED |
| 2 | Cliente | ✅ | ✅ client_name | ✅ CLIENT_NAME | ✅ Required | ✅ SYNCED |
| 3 | SKU | ✅ | ✅ sku | ✅ SKU | ✅ Required | ✅ SYNCED |
| 4 | Descrição | ✅ | ✅ description | ✅ DESCRIPTION | ❌ Not parsed | ⚠️ PARTIAL |
| 5 | Qtd | ✅ | ✅ quantity | ✅ QUANTITY | ✅ Required | ✅ SYNCED |
| 6 | Unidade | ✅ | ✅ unit | ✅ UNIT | ❌ Not parsed | ⚠️ PARTIAL |
| 7 | Largura | ✅ | ✅ width | ✅ WIDTH | ❌ Not parsed | ⚠️ PARTIAL |
| 8 | Comprimento | ✅ | ✅ length | ✅ LENGTH | ❌ Not parsed | ⚠️ PARTIAL |
| 9 | Lead Time | ✅ | ✅ lead_time | ✅ LEAD_TIME | ❌ Not parsed | ⚠️ PARTIAL |
| 10 | Data Entrega | ✅ | ✅ delivery_date | ✅ DELIVERY_DATE | ❌ Not parsed | ⚠️ PARTIAL |
| 11 | Data Faturamento | ✅ | ✅ billing_date | ✅ BILLING_DATE | ❌ Not parsed | ⚠️ PARTIAL |
| 12 | % ICMS | ✅ | ✅ icms_percent | ✅ ICMS_PERCENT | ❌ Not parsed | ⚠️ PARTIAL |
| 13 | Bloqueio | ✅ | ✅ block_status | ✅ BLOCK_STATUS | ❌ Not parsed | ⚠️ PARTIAL |
| 14 | Saldo | ✅ | ✅ balance | ✅ BALANCE | ❌ Not parsed | ⚠️ PARTIAL |
| 15 | Atraso | ✅ | ✅ delay | ✅ DELAY | ❌ Not parsed | ⚠️ PARTIAL |
| 16 | Condição Pagamento | ✅ | ✅ payment_terms | ✅ PAYMENT_TERMS | ❌ Not parsed | ⚠️ PARTIAL |
| 17 | Frete | ✅ | ✅ freight | ✅ FREIGHT | ❌ Not parsed | ⚠️ PARTIAL |
| 18 | Vendedor | ✅ | ✅ salesperson | ✅ SALESPERSON | ❌ Not parsed | ⚠️ PARTIAL |
| 19 | IPI | ✅ | ✅ ipi | ✅ IPI | ❌ Not parsed | ⚠️ PARTIAL |
| - | **PRICE_UNIT** | ❌ | ❌ **MISSING** | ✅ Optional | ✅ **REQUIRED** | 🔴 **BROKEN** |
| - | **COST_MP** | ❌ | ❌ **MISSING** | ✅ Optional | ✅ **REQUIRED** | 🔴 **BROKEN** |
| - | **COST_MO** | ❌ | ❌ **MISSING** | ✅ Optional | ✅ **REQUIRED** | 🔴 **BROKEN** |
| - | **COST_ENERGY** | ❌ | ❌ **MISSING** | ✅ Optional | ✅ **REQUIRED** | 🔴 **BROKEN** |
| - | **COST_GAS** | ❌ | ❌ **MISSING** | ✅ Optional | ✅ **REQUIRED** | 🔴 **BROKEN** |

---

## 🎯 REQUIRED FIXES

### Fix #1: Update import_service.py to Handle Optional Fields
**Change:** Make cost fields truly optional in `parse_row()` method.

**Strategy:**
- Check if field exists in `field_to_column` before accessing
- Only parse if mapped
- Set to `None` or `Decimal(0)` if not provided

### Fix #2: Update import_schema.py Validation
**Change:** Clarify that cost fields are NOT required for ONET imports.

**Strategy:**
- Keep `ImportFieldType` enum with all fields
- Update `validate_required_fields()` to only require: PO_NUMBER, CLIENT_NAME, SKU, QUANTITY
- Remove cost fields from required validation

### Fix #3: Keep Frontend Mapping as Pure ONET (19 fields)
**Decision:** The frontend should ONLY send the 19 ONET fields. Cost calculation should happen in the backend by looking up SKU costs from `material_costs` table.

**Rationale:**
- ONET files don't contain cost data
- Costs are internal business data
- Backend should enrich the import with cost lookups

### Fix #4: Update Backend to Lookup Costs from Database
**New Logic:**
1. Frontend sends 19 ONET fields (no costs)
2. Backend receives and validates ONET fields
3. Backend looks up `material_costs` by SKU
4. Backend calculates margins using looked-up costs
5. Backend returns enriched data to staging area

---

## 🔧 IMPLEMENTATION PLAN

1. ✅ **Audit Complete** - Document all mismatches
2. ⏳ **Fix import_service.py** - Make cost fields optional, add SKU cost lookup
3. ⏳ **Fix import_schema.py** - Update required field validation
4. ⏳ **Keep ImportPage.jsx** - Already correct (19 ONET fields only)
5. ⏳ **Keep generate_onet_mock.py** - Already correct (19 ONET fields only)
6. ⏳ **Create verification script** - Test end-to-end import
7. ⏳ **Run verification** - Confirm 100% success

---

## 📝 VERIFICATION CRITERIA

The system will be considered "100% SYNCED" when:

1. ✅ Frontend sends exactly 19 ONET fields (no cost fields)
2. ✅ Backend accepts import without requiring cost fields
3. ✅ Backend looks up costs from `material_costs` table by SKU
4. ✅ Backend calculates margins correctly
5. ✅ Staging area displays all 19 ONET fields + calculated costs
6. ✅ No "Unexpected error" messages
7. ✅ Verification script passes 100%

---

**Next Step:** Fix `import_service.py` to make cost fields optional and add SKU cost lookup logic.
