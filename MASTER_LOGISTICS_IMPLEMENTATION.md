# Master User Interaction & Logistics Module Implementation

## 🎯 Overview

This implementation enables Master/Admin users to interact with financial values and introduces the complete Logistics & Shipping module for the Expedição/Faturamento stage.

## ✅ Implementation Summary

### 1. Master Override Interaction - Commission Editing

#### Backend Changes

**File: `backend/schemas/kanban_schema.py`**
- Added `commission_rate` and `commission_value` fields to `POResponse`
- Added `manual_commission_rate` field to `POItemResponse`
- Created `UpdateCommissionRequest` schema with validation
- Created `UpdateCommissionResponse` schema

**File: `backend/routers/kanban.py`**
- Added `PUT /api/kanban/pos/{po_id}/commission` endpoint
- Authorization: Only MASTER or ADMIN roles can update commission
- Requires justification (minimum 10 characters)
- Updates `partition_metadata` with manual commission rate
- Recalculates margin immediately after update
- Integrates with `FinancialService` for calculations

#### Frontend Changes

**File: `frontend/src/pages/KanbanPage.jsx`**
- Added editable commission field in Order Detail modal
- Only visible to users with MASTER or ADMIN role
- Inline editing with save/cancel buttons
- Real-time margin recalculation display
- Justification textarea (required, min 10 chars)
- Success/error feedback via toast notifications

**Features:**
- ✅ Commission field is read-only for non-MASTER/ADMIN users
- ✅ Edit button appears only for authorized users
- ✅ Validation: 0-100% range, justification required
- ✅ Immediate UI refresh after successful update
- ✅ Displays updated margin (CM) after commission change

---

### 2. Logistics & Shipping Foundation

#### Backend Changes

**File: `backend/schemas/kanban_schema.py`**
- Created `UpdateLogisticsChecklistRequest` schema
- Created `UpdateLogisticsChecklistResponse` schema
- Added `logistics_checklist` field to `POResponse`

**File: `backend/routers/kanban.py`**
- Added `PUT /api/kanban/pos/{po_id}/logistics-checklist` endpoint
- Added `GET /api/kanban/pos/{po_id}/logistics-checklist` endpoint
- Stores checklist data in `partition_metadata.logistics_checklist`
- Validates completion status (all 3 checkboxes + 2 files)
- Returns `can_dispatch` boolean flag

#### Frontend Changes

**File: `frontend/src/pages/KanbanPage.jsx`**
- Added "Checklist de Saída" section (only visible in Expedição/Faturamento)
- 3 mandatory checkboxes:
  - ✅ Endereço Conferido
  - ✅ Peso Validado
  - ✅ Etiquetas Impressas
- Evidence upload section with 2 file slots:
  - 📸 Foto da Carga
  - 📸 Foto do Canhoto/NF
- Real-time checklist updates via API
- Visual feedback with CheckCircle icons
- Upload progress indicator

**Sync Logic:**
- "Concluir Despacho" button is **disabled** until:
  - All 3 checkboxes are checked ✅
  - Both evidence files are uploaded ✅
- Button changes color from gray (disabled) to green (enabled)
- Clear visual feedback: "Complete o Checklist e Evidências" vs "Concluir Despacho"

---

### 3. UI Refinement

#### Column Colors
**File: `frontend/src/components/kanban/KanbanColumn.jsx`**
- Expedição/Faturamento column uses soft light blue background
- Color mapping: `lightblue: 'bg-blue-100 border-blue-200'`
- Header: `bg-blue-200 text-blue-900`

#### Currency Formatting
**File: `frontend/src/pages/KanbanPage.jsx`**
- All currency values display as **R$ 0,00** format
- Uses `Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })`
- Applied to:
  - Total Value
  - Commission Value
  - Margin displays
  - Item prices

#### Labels & Messages (PT-BR)
All UI text is in Portuguese:
- "Dados Financeiros"
- "Checklist de Saída"
- "Endereço Conferido"
- "Peso Validado"
- "Etiquetas Impressas"
- "Evidências Fotográficas"
- "Foto da Carga"
- "Foto do Canhoto/NF"
- "Concluir Despacho"
- Success messages: "Comissão atualizada com sucesso", "Pronto para despacho!"

---

## 🔧 API Endpoints

### Update Manual Commission
```http
PUT /api/kanban/pos/{po_id}/commission
Authorization: Bearer <token> (MASTER/ADMIN only)

Request Body:
{
  "po_id": "uuid",
  "item_id": "uuid" (optional),
  "manual_commission_rate": 3.5,
  "justification": "Cliente estratégico com volume alto"
}

Response:
{
  "success": true,
  "message": "Comissão atualizada para 3.5% com sucesso",
  "po_id": "uuid",
  "new_commission_rate": 3.5,
  "new_margin": 28.75,
  "updated_by": "admin_user"
}
```

### Update Logistics Checklist
```http
PUT /api/kanban/pos/{po_id}/logistics-checklist
Authorization: Bearer <token>

Request Body:
{
  "po_id": "uuid",
  "endereco_conferido": true,
  "peso_validado": true,
  "etiquetas_impressas": true,
  "foto_carga_path": "/uploads/po-123/carga.jpg",
  "foto_canhoto_path": "/uploads/po-123/canhoto.jpg"
}

Response:
{
  "success": true,
  "message": "Checklist de logística atualizado com sucesso - Pronto para despacho!",
  "po_id": "uuid",
  "checklist_complete": true,
  "can_dispatch": true
}
```

### Get Logistics Checklist
```http
GET /api/kanban/pos/{po_id}/logistics-checklist
Authorization: Bearer <token>

Response:
{
  "po_id": "uuid",
  "checklist": {
    "endereco_conferido": true,
    "peso_validado": true,
    "etiquetas_impressas": false,
    "foto_carga_path": "/uploads/po-123/carga.jpg",
    "foto_canhoto_path": null,
    "updated_by": "user_id",
    "updated_at": "2026-05-14T15:00:00Z"
  },
  "checklist_complete": false,
  "evidence_complete": false,
  "can_dispatch": false
}
```

---

## 📊 Data Flow

### Commission Update Flow
1. User (MASTER/ADMIN) clicks "Editar Comissão"
2. Input field and justification textarea appear
3. User enters new rate and justification
4. Click "Salvar"
5. Frontend validates (0-100%, justification ≥ 10 chars)
6. API call to `/api/kanban/pos/{po_id}/commission`
7. Backend validates role and updates `partition_metadata`
8. FinancialService recalculates margin
9. Response returns new commission and margin
10. UI updates immediately with new values

### Logistics Checklist Flow
1. User opens PO in "Expedição/Faturamento" status
2. Checklist section loads current state via GET endpoint
3. User checks checkboxes → immediate PUT request
4. User uploads files → POST to upload endpoint → PUT to update checklist
5. Backend validates completion (3 checks + 2 files)
6. "Concluir Despacho" button enables when `can_dispatch: true`
7. User clicks button to complete dispatch

---

## 🎨 UI Components

### Financial Section (Modal)
```jsx
<div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
  <h3>Dados Financeiros</h3>
  <div className="grid grid-cols-3 gap-4">
    <div>Margem (CM): 28.75%</div>
    <div>Comissão: 3.5% (editable for MASTER/ADMIN)</div>
    <div>Valor Comissão: R$ 1.750,00</div>
  </div>
  {editingCommission && (
    <textarea placeholder="Justificativa..." />
    <button>Salvar</button>
  )}
</div>
```

### Logistics Checklist Section (Modal)
```jsx
<div className="mb-6 p-4 bg-cyan-50 border border-cyan-200 rounded-lg">
  <h3>Checklist de Saída</h3>
  <label>
    <input type="checkbox" checked={endereco_conferido} />
    Endereço Conferido
  </label>
  <label>
    <input type="checkbox" checked={peso_validado} />
    Peso Validado
  </label>
  <label>
    <input type="checkbox" checked={etiquetas_impressas} />
    Etiquetas Impressas
  </label>
  
  <h4>Evidências Fotográficas</h4>
  <div className="grid grid-cols-2 gap-4">
    <div>Foto da Carga: <input type="file" /></div>
    <div>Foto do Canhoto/NF: <input type="file" /></div>
  </div>
  
  <button disabled={!canDispatch}>
    {canDispatch ? 'Concluir Despacho' : 'Complete o Checklist e Evidências'}
  </button>
</div>
```

---

## 🔒 Security & Authorization

### Commission Editing
- **Authorization**: Only MASTER or ADMIN roles
- **Validation**: 
  - Rate must be 0-100%
  - Justification required (min 10 characters)
- **Audit Trail**: Stored in `partition_metadata`:
  ```json
  {
    "manual_commission_rate": 3.5,
    "commission_justification": "Cliente estratégico",
    "commission_updated_by": "user_uuid",
    "commission_updated_at": "2026-05-14T15:00:00Z"
  }
  ```

### Logistics Checklist
- **Authorization**: Any authenticated user
- **Validation**: File types (images only)
- **Storage**: Files in `/uploads/{po_id}/` directory
- **Audit Trail**: Stored in `partition_metadata.logistics_checklist`

---

## 🧪 Testing

### Manual Testing Checklist

#### Commission Editing
- [ ] Login as MASTER user → Edit button visible
- [ ] Login as ADMIN user → Edit button visible
- [ ] Login as OPERATOR user → Edit button NOT visible
- [ ] Enter commission rate 3.5% → Saves successfully
- [ ] Enter rate 150% → Validation error
- [ ] Enter justification < 10 chars → Validation error
- [ ] Save commission → Margin recalculates immediately
- [ ] Close and reopen modal → New commission persists

#### Logistics Checklist
- [ ] Open PO in "Expedição/Faturamento" → Checklist visible
- [ ] Open PO in "PCP" → Checklist NOT visible
- [ ] Check "Endereço Conferido" → Saves immediately
- [ ] Check all 3 boxes → Button still disabled (no files)
- [ ] Upload "Foto da Carga" → Success message
- [ ] Upload "Foto do Canhoto/NF" → Success message
- [ ] All complete → Button enables and turns green
- [ ] Refresh page → Checklist state persists

#### Currency Formatting
- [ ] All values display as R$ 0,00 format
- [ ] Decimal separator is comma (,)
- [ ] Thousands separator is period (.)
- [ ] Example: R$ 1.234,56

#### UI Colors
- [ ] Expedição/Faturamento column has light blue background
- [ ] Financial section has blue background
- [ ] Logistics section has cyan background

---

## 📝 Database Schema

### PurchaseOrder.partition_metadata (JSONB)
```json
{
  "manual_commission_rate": 3.5,
  "commission_justification": "Cliente estratégico com volume alto",
  "commission_updated_by": "uuid",
  "commission_updated_at": "2026-05-14T15:00:00Z",
  "logistics_checklist": {
    "endereco_conferido": true,
    "peso_validado": true,
    "etiquetas_impressas": true,
    "foto_carga_path": "/uploads/po-123/carga.jpg",
    "foto_canhoto_path": "/uploads/po-123/canhoto.jpg",
    "updated_by": "uuid",
    "updated_at": "2026-05-14T15:00:00Z"
  }
}
```

### OrderItem.extra_metadata (JSONB)
```json
{
  "manual_commission_rate": 3.5,
  "commission_justification": "Item específico com margem diferenciada",
  "commission_updated_by": "uuid",
  "commission_updated_at": "2026-05-14T15:00:00Z"
}
```

---

## 🚀 Deployment Notes

### Backend
1. No database migration required (uses existing JSONB fields)
2. Restart backend server to load new endpoints
3. Verify FinancialService is accessible

### Frontend
1. No new dependencies required
2. Rebuild frontend: `npm run build`
3. Deploy updated bundle

### Environment Variables
No new environment variables required.

---

## 📚 Related Documentation

- [ADVANCED_FINANCIAL_MODULE_IMPLEMENTATION.md](./ADVANCED_FINANCIAL_MODULE_IMPLEMENTATION.md) - Financial logic details
- [BUSINESS_RULES_IMPLEMENTATION.md](./BUSINESS_RULES_IMPLEMENTATION.md) - Business rules
- [backend/services/financial_service.py](./backend/services/financial_service.py) - Commission calculation logic

---

## ✨ Key Features Summary

1. **Master Override**: MASTER/ADMIN can manually set commission rates with justification
2. **Real-time Updates**: Margin recalculates immediately after commission change
3. **Logistics Checklist**: 3 mandatory checks before dispatch
4. **Evidence Upload**: 2 photo uploads required (Carga + Canhoto/NF)
5. **Sync Logic**: Dispatch button disabled until all requirements met
6. **Visual Feedback**: Color-coded sections, icons, and clear messaging
7. **Currency Formatting**: All values in R$ 0,00 format
8. **PT-BR Labels**: Complete Portuguese localization
9. **Audit Trail**: All changes tracked in metadata
10. **Role-based Access**: Commission editing restricted to MASTER/ADMIN

---

## 🎉 Implementation Complete!

All requirements have been successfully implemented:
- ✅ Master user can edit commission with justification
- ✅ Margin (CM) refreshes immediately in UI
- ✅ Logistics checklist with 3 mandatory items
- ✅ Evidence upload section with 2 file slots
- ✅ Dispatch button sync logic (disabled until complete)
- ✅ Expedição/Faturamento uses light blue background
- ✅ All currency values display as R$ 0,00
- ✅ All labels and messages in PT-BR

**Status**: Ready for testing and deployment! 🚀
