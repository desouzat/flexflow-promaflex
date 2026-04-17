# ONET Mock Data Generator

## 📋 Overview

Script to generate professional Excel test data for the **Staging Area (Mesa de Conferência)** with realistic ONET format data.

## 🎯 Generated File

**File:** `onet_test_data.xlsx`  
**Location:** Root directory  
**Rows:** 5 realistic test cases

## 📊 Test Data Specifications

### 14 Columns (Ewaldo's ONET Format)
1. **Pedido** - Order number
2. **Cliente** - Client name
3. **SKU** - Product SKU
4. **Descrição** - Product description
5. **Qtd** - Quantity
6. **Unidade** - Unit (UN)
7. **Largura** - Width (mm)
8. **Comprimento** - Length (mm)
9. **Lead Time** - Production lead time (days)
10. **Data Entrega** - Delivery date
11. **Data Faturamento** - Billing date
12. **% ICMS** - ICMS tax percentage
13. **Frete** - Freight cost
14. **Seguro** - Insurance cost

## 🧪 Test Cases Included

### ✅ Existing SKUs (2 items)
- **PP-1000** - Polipropileno Natural (exists in material_costs)
- **ABS-2000** - ABS Preto (exists in material_costs)
- **PET-1000** - PET Cristal (exists in material_costs)
- **PE-1000** - Polietileno HD Natural (exists in material_costs)

### ⚠️ New SKU (1 item)
- **PAB-035** - New SKU that will trigger yellow warning (not in material_costs)

### 🔧 Personalized Items (2 items)
- **PAB-035** - "Painel Frontal Customizado com Logo Gravado"
- **PE-1000** - "Gaveta Modular PE HD Natural com Divisórias Personalizadas"

## 🚀 Usage

### Generate the file:
```bash
python backend/generate_onet_mock.py
```

### Expected Output:
```
================================================================================
[OK] Arquivo ONET Mock Gerado com Sucesso!
================================================================================

Arquivo: onet_test_data.xlsx
Total de linhas: 5

Resumo dos dados:
   - 2 itens com SKUs EXISTENTES (PP-1000, ABS-2000)
   - 1 item com SKU NOVO (PAB-035) - vai trigger WARNING amarelo
   - 2 itens PERSONALIZADOS (PAB-035, PE-1000)
```

## 📝 Test Scenarios Covered

| Scenario | SKU | Expected Behavior |
|----------|-----|-------------------|
| Existing material cost | PP-1000, ABS-2000, PET-1000, PE-1000 | ✅ Auto-populate cost data |
| New SKU warning | PAB-035 | ⚠️ Yellow warning - cost not found |
| Personalized product | PAB-035, PE-1000 | 🔧 Requires "Personalizado" toggle |
| Different ICMS rates | Various | Test tax calculation variations |
| Varied quantities | 250-2000 units | Test volume scenarios |
| Different dimensions | Various sizes | Test dimensional data |

## 🎨 Excel Formatting

- **Header:** Bold, blue background (#366092), white text
- **Column widths:** Auto-adjusted for readability
- **Data alignment:** 
  - Numeric: Right-aligned
  - Dates: Center-aligned
  - Text: Left-aligned

## 🔄 Next Steps

1. Run the generator script
2. Import `onet_test_data.xlsx` into the Staging Area
3. Verify:
   - ✅ Existing SKUs auto-populate costs
   - ⚠️ PAB-035 shows yellow warning
   - 🔧 Personalized items can be toggled
   - 📊 All 14 columns display correctly
   - 💾 Data can be saved to database

## 📦 Dependencies

- `pandas` - Data manipulation and Excel generation
- `openpyxl` - Excel file formatting

Already included in `backend/requirements.txt`
