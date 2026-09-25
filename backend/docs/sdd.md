# FlexFlow — System Design Document (SDD)

> **Maintained by:** Engineering team  
> **Last updated:** 2026-09-24  
> **Rule 3.1 compliance:** All architectural changes must be reflected here before merging to production.

---

## 1. System Overview

FlexFlow is a multi-tenant, SaaS Kanban-based production-order (PO) management system for a Brazilian manufacturer. It integrates with the ONET ERP via Excel/CSV spreadsheet imports and orchestrates a production workflow from commercial order intake through manufacturing, billing (Faturamento), and outbound logistics (Expedição).

### 1.1 Core Technology Stack

| Layer | Technology |
|---|---|
| Backend API | Python 3.10 · FastAPI · SQLAlchemy 2 |
| Database | PostgreSQL 14 (production: `flexflow_prod` on port 5434) |
| Frontend | React 18 · Vite 5 · Vanilla CSS |
| File Storage | Google Cloud Storage (GCS) |
| Auth | JWT (RS256) via Supabase-compatible token |
| Process Manager | Gunicorn + Uvicorn workers |

---

## 2. Database Architecture

### 2.1 Key Tables

| Table | Purpose |
|---|---|
| `purchase_orders` | PO header — one row per PO |
| `order_items` | Line items — FK to `purchase_orders` |
| `staging_sessions` | Staging preview state — JSONB auto-saved staging drafts |
| `material_costs` | Reference material unit costs (m²/kg, yield) by SKU |
| `audit_logs` | Immutable blockchain-hash chained audit trail |
| `handoff_history` | Stage transition records |
| `client_preferences` | Persisted client → business_unit preference memory |

### 2.2 JSONB Columns & Staging Sessions

Three JSONB structures carry all transient and non-relational metadata:

#### `staging_sessions.data` & `session_metadata`
Stores live preview sessions for Mesa de Conferência imports:
- **Auto-Save Debounce:** Frontend changes to staging rows trigger a 300ms debounced auto-save to `POST /api/import/staging-session`.
- **Concurrent Safety:** Each session uses a unique `session_id` and timestamped heartbeats to prevent multi-user overwrites.

#### `purchase_orders.partition_metadata`
Contains PO-level fields:
```json
{
  "client_name": "string",
  "expected_delivery_date": "DD/MM/YYYY",   // Dt.Faturamento — SLA base [§9.1]
  "order_entry_date": "DD/MM/YYYY",          // Dt.Entrega — order receipt date
  "order_date": "DD/MM/YYYY",                // Data do Pedido — original ERP order date
  "carrier_code": "string | null",           // Cod. Transportadora (ONET 2026-07-01)
  "carrier_name": "string | null",           // Nome Transportadora (ONET 2026-07-01)
  "packaging_type": "string | null",
  "business_unit": "Indústria|Construção Civil|Varejo|Outros",
  "is_personalized": "bool",
  "is_new_client": "bool",
  "is_export": "bool",
  "is_replacement": "bool",
  "invoice_pdf_path": "string | null",       // GCS path — set on Faturamento upload
  "invoice_pdf_path_2": "string | null",     // Secondary invoice PDF
  "invoice_xml_path": "string | null",       // XML NF-e (if provided)
  "numero_nfe": "string | null",
  "transportadora": "string | null",         // Operator-filled on Faturamento stage
  "data_emissao_nf": "string | null"
}
```

#### `order_items.extra_metadata`
Contains item-level fields:
```json
{
  "description": "string",           // Produto column (renamed from Descr. Produto)
  "codigo_estruturado": "string",    // Codigo Estruturado — primary product code (ONET 2026-07-01)
  "delivery_date": "DD/MM/YYYY",     // Dt.Entrega (order entry/receipt date)
  "billing_date": "DD/MM/YYYY",      // Dt.Faturamento (SLA contractual delivery)
  "order_date": "DD/MM/YYYY",        // Data do Pedido (original ERP creation date)
  "carrier_code": "string",          // Mirrored from PO level for per-item traceability
  "carrier_name": "string",          // Mirrored from PO level
  "width": "decimal",
  "length": "decimal",
  "lead_time": "int",
  "icms_percent": "decimal",
  "freight": "decimal",
  "salesperson": "string",
  "ipi": "decimal",
  "block_status": "BLOQUEADO|LIBERADO",
  "balance": "decimal",
  "delay": "int",
  "payment_terms": "string"
}
```

### 2.3 Database Connection — NullPool

**Rationale:** Gunicorn spawns multiple worker processes. A standard `QueuePool` would create separate connection pools per worker process, causing connection exhaustion under load. Instead, FlexFlow uses **SQLAlchemy `NullPool`** so each request opens and closes a connection independently — compatible with pgBouncer in transaction mode and avoids idle connection accumulation.

```python
# backend/database.py
engine = create_engine(
    DATABASE_URL,
    poolclass=NullPool,      # ← no persistent pool; one conn per request
)
```

**Event-loop thread offloading:** All blocking SQLAlchemy calls are wrapped in `asyncio.get_event_loop().run_in_executor(None, ...)` to avoid blocking the FastAPI async event loop.

---

## 3. Status Flow Architecture

### 3.1 `purchase_orders.status_macro` Valid Values

```sql
CHECK (status_macro IN (
  'DRAFT', 'SUBMITTED', 'PCP', 'APPROVED', 'MANUFACTURING',
  'BILLING', 'SHIPPING', 'WAITING_DISPATCH',
  'ARCHIVED', 'ARCHIVED_PARTITIONED', 'COMPLETED', 'CANCELLED'
))
```

> **BILLING constraint:** Added in startup DDL boot via `_run_ddl_step("alter_status_constraint_billing")` in `backend/main.py`. Runs idempotently on every restart via `DROP CONSTRAINT IF EXISTS` + `ADD CONSTRAINT`.

### 3.2 Kanban Column ↔ Status Mapping

| Kanban Column (UI) | `status_macro` DB Value | Notes |
|---|---|---|
| Mesa de Conferência | *(staging area, not persisted as status)* | |
| Análise de Crédito | `SUBMITTED` | Finance gate |
| PCP | `APPROVED` / `PCP` | Cost linking stage |
| Fabricação | `MANUFACTURING` | Production floor |
| **Faturamento** | `BILLING` | NF-e, Transportadora, invoice upload |
| **Expedição** | `SHIPPING` / `WAITING_DISPATCH` | Logistics photos, truck dispatch |
| Concluídos | `COMPLETED` | Archived |

### 3.3 Split Faturamento / Expedição Flow (implemented 2026-06)

Prior to this change, `BILLING` and `SHIPPING` were combined into a single "Faturamento/Expedição" accordion. They were split into independent stages:

- **Faturamento (BILLING):** Collects NF-e number, Transportadora, NF-e emission date, and at least one invoice PDF/XML attachment. The "Avançar para Expedição" button requires `isBillingDocReady()` → at least one of `invoice_pdf_path` or `invoice_pdf_path_2` populated.
- **Expedição (SHIPPING):** Collects logistics photos (truck load + canhoto), checklist (endereço conferido, peso validado, etiquetas impressas). Advancing to `WAITING_DISPATCH` / `COMPLETED` requires all checklist items checked.

### 3.4 Performance Bulk Loading & Hygiene Filter

To eliminate N+1 query bottlenecks on `GET /api/kanban/board`:
- **Bulk Relationship Preloading:** Eagerly loads `po.items` using SQLAlchemy `selectinload`/`joinedload`.
- **Concluded Cards Hygiene Filter:** Concluded/Archived cards (`COMPLETED`, `ARCHIVED`, `CANCELLED`) updated more than 3 days ago are automatically filtered out from active board payloads, keeping active payload response times under 50ms while preserving recent completed cards.

### 3.5 CR-F4 Alt+Tab Silent Refresh Architecture

In `frontend/src/pages/KanbanPage.jsx`:
- **Silent Background Fetch:** `fetchBoard(isBackground = true)` bypasses full-screen loading spinners (`setLoading(true/false)`) when triggered by window focus (`handleFocus`), eliminating intrusive spinner flashing and UI lockup when operators Alt+Tab between FlexFlow and ONET ERP.
- **Silent Catch Guard:** Errors encountered during background focus refresh log a warning to console (`console.warn('[FF-CR-F4] Silent background auto-sync failed gracefully:', err)`) without interrupting operator interaction.
- **Scroll Position Shield:** Double-buffered frame preservation (`requestAnimationFrame` + `setTimeout(50ms, 150ms)`) locks column scroll positions during background re-renders.

### 3.6 CR-F3 Universal Return to Commercial & Cancellation Architecture

Implemented in `backend/routers/kanban.py` and `frontend/src/pages/KanbanPage.jsx`:
- **Universal Express Return:** Selecting `[Cancelamento de Pedido]` in the Return Modal (`POST /api/kanban/return-status` or `POST /api/kanban/pos/{po_id}/return`) dynamically updates the modal header to "Devolver para Comercial (Cancelamento)" with an amber warning badge. When executed, it overrides standard step-back logic and immediately routes the PO directly to `SUBMITTED` (Comercial), bypassing all intermediate stages (PCP, Produção, Faturamento, Expedição).
- **Item Status Synchronization:** All line items in `po.items` have their `status_item` and `status` synchronized directly to `SUBMITTED`.
- **Commercial Cancellation Gating:** Order cancellation in the Commercial stage (`SUBMITTED` / `DRAFT`) via `POST /api/kanban/pos/{po_id}/cancel` is restricted to users with `admin` or `master` roles, OR users granted the explicit delegated permission `can_cancel_commercial = true`.
- **Cascade Cancellation:** Cancelling a PO transitions `po.status_macro = 'CANCELLED'`, cascades `status_item = 'CANCELLED'` across all line items, cancels child partition orders (if partitioned), and persists an immutable SHA-256 Ledger V2 audit log entry.

---

## 4. ONET Final Production Excel Schema (2026-07-01)

Ewaldo (ONET ERP developer) provided the final production spreadsheet format. Changes vs. prior 22-field schema:

### 4.1 Column Rename
| Old Name | New Name | Field Type |
|---|---|---|
| `Descr. Produto` | **`Produto`** | `description` |

Both names remain accepted (backward compatibility alias in `FIELD_ALIASES`).

### 4.2 New Columns

| Column Name | `ImportFieldType` | Storage |
|---|---|---|
| `Data do Pedido` | `ORDER_DATE` | `partition_metadata["order_date"]` + `extra_metadata["order_date"]` |
| `Codigo Estruturado` | `CODIGO_ESTRUTURADO` | `extra_metadata["codigo_estruturado"]` |
| `Cod. Transportadora` | `CARRIER_CODE` | `partition_metadata["carrier_code"]` |
| `Nome Transportadora` | `CARRIER_NAME` | `partition_metadata["carrier_name"]` |

### 4.3 Date Role Alignment (Critical)

| Column | Old interpretation | **Correct interpretation** |
|---|---|---|
| `Dt.Entrega` | SLA base → `expected_delivery_date` ❌ | Order entry/receipt date → `order_entry_date` ✅ |
| `Dt.Faturamento` | Not used as SLA | **SLA base → `expected_delivery_date`** ✅ |
| `Data do Pedido` | Not captured | Original ERP order creation date → `order_date` |

> **Impact:** The SLA countdown timer in the Kanban card, PO header, and all delay calculations are now driven by `Dt.Faturamento` (the contractual billing/delivery deadline), not the order entry date.

### 4.4 ERP Noise Guard

ONET legacy systems represent NULL numeric values as large negative sentinel floats (e.g. `-3.35565E+17`). The `clean_brazilian_number()` function in `backend/utils/number_utils.py` treats any value `< -9,999,999` as corrupt system noise and coerces it to `0.0`.

---

## 5. Authentication & Settings Delegation

### 5.1 JWT Token Structure

FlexFlow uses RS256-signed JWTs issued by Supabase. User roles are read from `token.app_metadata.role`:

| Role | Permissions |
|---|---|
| `master` | Full access, Settings, User Management |
| `admin` | Full Kanban, Import, Reports, Settings read |
| `operator` | Kanban only (limited stages) |
| `user` | Salesperson view (restricted to own sales orders) |

### 5.2 `is_sla_manager` Field

A new claim `is_sla_manager` can be embedded in the JWT `app_metadata` to grant an `operator`-level user the ability to:
- View SLA performance metrics on the Kanban board
- Override SLA justification categories
- Access the SLA management panel in Settings

### 5.2.1 `can_cancel_commercial` Field (CR-F3)

A boolean flag `can_cancel_commercial` (default `FALSE`) on the `users` table, exposed in JWT claims and `/api/users`:
- Allows administrators to grant specific non-admin users permission to cancel purchase orders directly within the Commercial stage (`SUBMITTED`/`DRAFT`).
- In `KanbanPage.jsx`, renders the `[ 🚫 Cancelar Pedido ]` button for authorized users.
- In `backend/routers/kanban.py`, gates `POST /api/kanban/pos/{po_id}/cancel` to ensure unauthorized users receive HTTP 403 Forbidden.

### 5.3 Role-Based Separation of Duties (SoD) in Sales Filtering

Implemented in `backend/utils/salesperson_filter.py`:
- **`user` Role:** Strictly restricted to filtering and viewing sales orders where `extra_metadata.salesperson` matches the user's name/email.
- **`operator`, `admin`, `master` Roles:** Bypass salesperson restrictions to manage all orders across the pipeline.

### 5.4 Endpoint Security Gating

- **`/import` Endpoints:** Restricted to `comercial@promaflex.com.br` or users with `admin` / `master` roles.
- **`/dashboard` & KPI Endpoints:** Restricted strictly to `admin` / `master` roles.

---

## 6. Import Pipeline Architecture

```
Frontend (ImportPage.jsx)
    │  multipart upload with mapping_json
    ▼
POST /api/import/upload
    │  → ImportService.validate_import_data()
    │      ├── resolve_aliases()       ← maps Excel headers → ImportFieldType
    │      ├── parse_row()             ← per-row field extraction + cleaning
    │      └── ImportItemData          ← Pydantic validation
    │
    ▼  (returns staging preview to frontend)
    
Mesa de Conferência UI (ImportPage.jsx)
    │  operator reviews, checks items, sets flags
    │  auto-saves draft to staging_sessions (300ms debounce)
    ▼
POST /api/import/confirm-staging
    │  → import_router.confirm_staging()
    │      ├── Clean delete of existing PO with same po_number
    │      ├── PurchaseOrder INSERT (partition_metadata populated)
    │      ├── OrderItem INSERT × N (extra_metadata populated)
    │      └── AuditLog INSERT (blockchain-chained v2 hash)
    ▼
PostgreSQL (flexflow_prod)
```

---

## 7. Unit-Aware Material Cost & Financial Margin Engine

Financial metrics are calculated in `frontend/src/utils/marginCalculator.js` and `backend/routers/kanban.py` via `calculate_unit_aware_item_cost`:

### 7.1 Tax Burden & Present Value (VP) Discounting

- **Tax Index Calculation:**
  $$\text{Tax Rate} = \frac{9.25\% \text{ (PIS/COFINS)} + \text{ICMS \% (from ONET item)}}{100}$$
  $$\text{Net Revenue} = \text{Gross Revenue} \times (1 - \text{Tax Rate})$$

- **Present Value (VP) Financial Discount:**
  For orders with deferred payment terms (`Cond.Pgto` / `payment_terms`), revenue is discounted to present value at a rate of 2.5% per 30 days:
  $$\text{Days} = \text{parse\_payment\_term\_days}(payment\_terms)$$
  $$\text{VP Net Revenue} = \frac{\text{Net Revenue}}{1 + 0.025 \times (\text{Days} / 30)}$$

### 7.2 Unit-Aware Industrial Cost Engine

Calculates item cost according to the item's unit of measurement (`unidade_medida`):

- **M2 (Square Meters):**
  $$\text{Total Cost} = \text{Quantity}_{\text{m2}} \times \text{Custo}_{\text{m2}}$$

- **KG (Kilograms):**
  $$\text{Cost}_{\text{kg}} = \text{Custo}_{\text{m2}} \times \text{Rendimento}_{\text{m2/kg}}$$
  $$\text{Total Cost} = \text{Quantity}_{\text{kg}} \times \text{Cost}_{\text{kg}}$$

- **RL / UN (Rolls / Units):**
  $$\text{Width}_{\text{m}} = \frac{\text{Width}_{\text{mm}}}{1000}$$
  $$\text{Total Area}_{\text{m2}} = \text{Width}_{\text{m}} \times \text{Length}_{\text{m}} \times \text{Quantity}$$
  $$\text{Total Cost} = \text{Total Area}_{\text{m2}} \times \text{Custo}_{\text{m2}}$$

- **Fallback:**
  $$\text{Total Cost} = \text{Quantity} \times \text{Custo}_{\text{m2}}$$

### 7.3 Net Profit Margin Calculation

$$\text{Net Profit} = \text{VP Net Revenue} - \text{Total Industrial Cost}$$
$$\text{Net Profit Margin \%} = \left(\frac{\text{Net Profit}}{\text{Gross Revenue}}\right) \times 100$$

> **Cap:** Net profit margin is capped strictly at $\le 100.0\%$ to prevent mathematical anomalies.

---

## 8. Key Backend Safeguards & Hardening

| Code | Description |
|---|---|
| `FF-HARDENING-004` | Financial mismatch detection: sum(item_total + IPI) vs. PO total. Operator must explicitly override. Creates immutable audit log. |
| `FF-HARDENING-006` | SLA justification persistence in `purchase_orders.sla_justification_category` + `sla_justification_text`. |
| `FF-HARDENING-012.2` | Faturamento stage gate: NF-e number + Transportadora + emission date + at least one invoice PDF required before advancing. |
| `CR-F7` | Dynamic financial export in `GET /api/reports/po-export` gated by RBAC/SoD (`role in ['admin', 'master']` OR `area in ['FATURAMENTO', 'FINANCEIRO', 'DIRETORIA']`). Adds 3 currency-formatted columns (`VALOR UNITARIO (R$)`, `VALOR TOTAL ITEM (R$)`, `VALOR TOTAL PEDIDO (R$)`) totaling 29 columns for authorized users, while enforcing 26 baseline columns for non-authorized users. |
| ERP Noise Guard | `clean_brazilian_number()` & `safe_format_currency()` coerce values `< -9,999,999` to `0.0`. Prevents legacy ONET NULL sentinel crashes. |
| `NullPool` | Database connection pool strategy — see §2.3. |
| Startup DDL | `_run_ddl_step()` in `main.py` runs idempotent DDL on startup (e.g. `BILLING` constraint, index creation). |

---

## 9. Frontend UI Landmarks

### 9.1 KanbanPage Modal — PO Header Block
Five-card summary row (md:grid-cols-5):
1. **Vl.Pedido** — `po_total_value`
2. **Dt.Entrega (SLA)** — `partition_metadata.expected_delivery_date` ← sourced from `Dt.Faturamento`
3. **Itens** — `items_count`
4. **Status** — `status_macro` human label
5. **Data do Pedido** (blue card) — `partition_metadata.order_date` ← sourced from `Data do Pedido`

### 9.2 KanbanPage — PCP Grade de Itens Table
Five-column table:
1. SKU / Produto
2. **Cód. Estruturado** (indigo badge, `extra_metadata.codigo_estruturado`)
3. Quantidade
4. Status de Custo
5. Ações

### 9.3 Faturamento Stage — Transportadora Auto-Population
On modal open, `localFields.transportadora` is pre-seeded from `partition_metadata.carrier_name` (if `extra_metadata.transportadora` is not already saved). This eliminates manual re-entry for operators.

### 9.4 ImportPage Mesa de Conferência
- **Item header:** `codigo_estruturado` rendered as indigo badge under Descrição do Produto.
- **Date strip:** Expanded from 6 → 7 cells. Seventh cell (blue) shows `Data do Pedido` when present.
- **Auto-Save:** Draft changes in Mesa de Conferência trigger a 300ms debounced auto-save to `staging_sessions`.

---

## 10. Deployment Notes

- **No git commits policy:** All changes are applied directly to the working directory. Production deploy is via `git push` by the infrastructure team.
- **Environment:** `.env` file at workspace root contains `DATABASE_URL`, `GCS_BUCKET_NAME`, `SUPABASE_JWT_SECRET`, etc.
- **Port:** Backend runs on `:8000` (Gunicorn); frontend dev server on `:5173` (Vite).
- **DB Host:** Production database at `localhost:5434` (Cloud SQL Proxy must be active).

---

*End of SDD — update this document whenever architectural changes are made.*
