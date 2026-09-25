# FlexFlow — Master Repository Handover & Architecture Specification (HANDOVER.md)

> **Document Version:** 2.0 (Production Master)  
> **Author:** Antigravity Systems Engineering Team  
> **Target Audience:** Incoming Systems Engineers, Lead Architects, and DevOps Operators  
> **Last Updated:** 2026-09-24  
> **Rule 3.1 Compliance:** Single Source of Truth for live production architecture, schema, security, and calculation engines.

---

## 1. System Overview & Architecture

FlexFlow is a custom, multi-tenant Industrial Business Process Management System (BPMS) and Warehouse Management System (WMS) built specifically for **PromaFlex** (a leading Brazilian manufacturer of protective films, acoustic foams, and industrial adhesive tapes).

It bridges the gap between the legacy ERP system (**ONET ERP**) and shop-floor operations by ingesting daily production orders, orchestrating multi-stage Kanban workflows, enforcing Separation of Duties (SoD), tracking industrial material costs, and generating financial margin metrics.

```
                  ┌─────────────────────────────────────────────────────────┐
                  │                       ONET ERP                          │
                  │   (Excel / CSV Exports uploaded to S3 / GCS Bucket)     │
                  └────────────────────────────┬────────────────────────────┘
                                               │ S3 Sync / Upload
                                               ▼
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                                FLEXFLOW BACKEND (FastAPI)                                │
│                                                                                          │
│  ┌──────────────────────────┐   ┌──────────────────────────┐   ┌──────────────────────┐  │
│  │  Mesa de Conferência     │   │   Unit-Aware Cost &      │   │   Kanban Board       │  │
│  │  Staging (JSONB + 300ms) │   │   Margin Engine (VP/ICMS)│   │   N+1 Bulk Preload   │  │
│  └────────────┬─────────────┘   └────────────┬─────────────┘   └──────────┬───────────┘  │
│               │                              │                            │              │
└───────────────┼──────────────────────────────┼────────────────────────────┼──────────────┘
                │                              │                            │
                ▼                              ▼                            ▼
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                               POSTGRESQL (Cloud SQL)                                     │
│  purchase_orders · order_items · staging_sessions · material_costs · audit_logs (V2)  │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

### 1.1 Technology Stack & Core Runtimes

- **Backend Framework:** Python 3.11+ · FastAPI · SQLAlchemy 2 (async thread-offloaded with `run_in_executor`)
- **Database Connection Pooling:** PostgreSQL 14 (`NullPool` strategy for pgBouncer compatibility & connection safety)
- **Frontend SPA:** React 18 · Vite 5 · Vanilla CSS · Lucide Icons (served statically via FastAPI `StaticFiles`)
- **Cloud Infrastructure & Storage:**
  - **Cloud Run Service:** `flexflow-app` (Region: `southamerica-east1`)
  - **Cloud SQL Instance:** `flexflow-db-v1` (DB: `flexflow_prod`, Port: `5434` / `5435`)
  - **Primary Tenant UUID:** `23c431b9-da55-4098-9628-c86df8070b7c` (PromaFlex Industrial)
  - **GCS Storage Bucket:** `flexflow-attachments-224292950652`
  - **S3 Import Bucket:** `flexflow` (GCS S3-interoperability API)

---

## 2. Database Models & Schema Relationships

Source of truth: [backend/models.py](file:///c:/Documentos/BotCase/FlexFlow/backend/models.py).

### 2.1 Entity-Relationship Overview

- **`Tenant` (1) ── (N) `User`**
- **`Tenant` (1) ── (N) `PurchaseOrder`**
- **`PurchaseOrder` (1) ── (N) `OrderItem`**
- **`OrderItem` (1) ── (N) `AuditLog`**
- **`Tenant` (1) ── (N) `MaterialCost`**
- **`Tenant` (1) ── (N) `StagingSession`**

---

### 2.2 Table Specifications

#### 1. `purchase_orders` (`PurchaseOrder`)
Header record for a customer purchase order.
- `id` (UUID, Primary Key)
- `tenant_id` (UUID, FK -> `tenants.id`)
- `po_number` (String(100), Indexed) — e.g. `'214165'`
- `status_macro` (String(50), Check Constraint) — Valid statuses: `'DRAFT'`, `'SUBMITTED'`, `'APPROVED'`, `'MANUFACTURING'`, `'BILLING'`, `'SHIPPING'`, `'WAITING_DISPATCH'`, `'ARCHIVED'`, `'ARCHIVED_PARTITIONED'`, `'COMPLETED'`, `'CANCELLED'`.
- `created_at` / `updated_at` (DateTime with timezone)
- `created_by` (UUID, FK -> `users.id`)
- `parent_po_id` (UUID, FK -> `purchase_orders.id`, Nullable) — Reference for commercial/PCP order partitions.
- `partition_metadata` (JSONB) — Flexible PO-level metadata document:
  ```json
  {
    "client_name": "string",
    "order_date": "DD/MM/YYYY",
    "order_entry_date": "DD/MM/YYYY",
    "expected_delivery_date": "YYYY-MM-DD",
    "carrier_code": "string",
    "carrier_name": "string",
    "packaging_type": "string",
    "business_unit": "Indústria|Construção Civil|Varejo|Outros",
    "numero_nfe": "string",
    "data_emissao_nf": "YYYY-MM-DD",
    "invoice_pdf_path": "gcs_url_string",
    "foto_carga_path": "gcs_url_string",
    "foto_canhoto_path": "gcs_url_string"
  }
  ```

#### 2. `order_items` (`OrderItem`)
Individual line items belonging to a purchase order.
- `id` (UUID, Primary Key)
- `po_id` (UUID, FK -> `purchase_orders.id`, Cascade Delete)
- `sku` (String(100), Indexed)
- `quantity` (Numeric(12, 4))
- `width` (Numeric(10, 2)) — Width in mm
- `length` (Numeric(10, 2)) — Length in meters
- `unit_price` (Numeric(12, 4))
- `item_total_value` (Numeric(12, 2)) — Line item gross revenue
- `status_item` (String(50)) — Line item state (mirrors or partitions PO status)
- `extra_metadata` (JSONB) — Flexible item-level metadata document:
  ```json
  {
    "description": "string",
    "codigo_estruturado": "string",
    "unidade_medida": "M2|KG|RL|UN",
    "salesperson": "string",
    "icms_percent": 12.0,
    "ipi": 0.0,
    "payment_terms": "A VISTA | 28/35/42",
    "block_status": "LIBERADO|BLOQUEADO",
    "attachments": [
      {"url": "gcs_url", "type": "cargo_photo|receipt_photo", "timestamp": "ISO_string"}
    ]
  }
  ```

#### 3. `material_costs` (`MaterialCost`)
Reference table storing unit production costs and yield by SKU.
- `id` (UUID, Primary Key)
- `tenant_id` (UUID, FK -> `tenants.id`)
- `sku` (String(100), Indexed) — **Sanitization Rule:** SKUs are strictly sanitized on input/update by stripping whitespace and removing dots (e.g. `'8.175'` -> `'8175'`).
- `nome` (String(255)) — Product name / structured code (e.g. `'PROMALEVE AZUL'`)
- `custo_mp_kg` (Numeric(10, 4)) — **Cost per M² (R$/m²)**
- `rendimento` (Numeric(10, 4)) — **Yield in M² per KG (m²/kg)**
- `indice_impostos` (Numeric(5, 2)) — Default tax index percentage (default `22.25`)
- `updated_by` (UUID, FK -> `users.id`, Nullable)

#### 4. `staging_sessions` (`StagingSession`)
JSONB document store for Mesa de Conferência preview and multi-user auto-save drafts.
- `id` (UUID, Primary Key)
- `tenant_id` (UUID, FK -> `tenants.id`)
- `session_id` (String(100), Indexed)
- `user_id` (UUID, FK -> `users.id`)
- `data` (JSONB) — Complete array of staging PO rows and validation flags.
- `session_metadata` (JSONB) — Heartbeat timestamp, active editor email, filename, and row counts.
- `is_active` (Boolean, Default True)
- `created_at` / `updated_at` (DateTime with timezone)

#### 5. `audit_logs` (`AuditLog`)
Immutable SHA-256 blockchain-style append-only ledger for system actions and status transitions.
- `id` (UUID, Primary Key)
- `item_id` (UUID, FK -> `order_items.id`)
- `from_status` (String(50), Nullable)
- `to_status` (String(50))
- `hash` (String(64), SHA-256)
- `previous_hash` (String(64), Nullable)
- `hash_version` (Integer, Default 2) — **V2 Algorithm:** `SHA256(tenant_id + item_id + from_status + to_status + timestamp + previous_hash + changed_by)`
- `justification` (Text, Nullable)
- `changed_by` (UUID, FK -> `users.id`)
- `extra_data` (JSONB) — Stores `po_id`, `po_number`, `client_name`, `action`, `details`, etc.

#### 6. `users` (`User`)
User profiles and access permissions.
- `id` (UUID, Primary Key)
- `tenant_id` (UUID, FK -> `tenants.id`)
- `email` (String(255), Unique)
- `name` (String(255))
- `role` (String(50)) — Valid roles: `'user'`, `'operator'`, `'admin'`, `'master'`.
- `area` (String(100)) — Operational area: `'Comercial'`, `'PCP'`, `'Produção'`, `'Faturamento'`, `'Logística'`, `'Diretoria'`.
- `is_sla_manager` (Boolean, Default False) — SLA management access delegation.
- `can_cancel_commercial` (Boolean, Default False) — Delegated permission to cancel orders in Commercial stage (`SUBMITTED`/`DRAFT`) (CR-F3).

---

## 3. Core Business Workflows & Data Pipelines

### 3.1 Ingestion & Mesa de Conferência

1. **S3 Background Sync (`POST /api/import/sync-s3`):**
   - Automated task polls S3 bucket `flexflow` for raw ONET export files (`ONET_EXPORT_*.xlsx`).
   - Ignores empty weekend templates (size $\le 3307$ bytes).
   - Only processes files from the last 7 days (`/processed` recency window).
2. **Multi-File Import Modal:**
   - Operators can upload multiple `.xlsx`/`.csv` files simultaneously.
3. **Mesa de Conferência Staging Preview:**
   - Rows are parsed, validated, and rendered in the interactive staging table.
   - **300ms Debounced Auto-Save:** Any inline edit (e.g. updating business unit, client preference, or item quantities) fires a debounced auto-save to `POST /api/import/staging-session`.
   - **Concurrent Heartbeats & Warning Banner:** If another user opens the Mesa de Conferência, the system detects conflicting active session IDs and displays a real-time amber warning banner to prevent accidental overwrites.

### 3.2 Kanban Board Lifecycle

Order cards transition through six distinct columns:

```
[ MESA DE CONFERÊNCIA ] (Staging Preview & Manual Review)
           │ Confirm Staging
           ▼
[ ANÁLISE DE CRÉDITO ] (Status: SUBMITTED - Financial Mismatch Review)
           │ Release / Confirm
           ▼
[ PCP / MENSURAÇÃO ]   (Status: APPROVED - SKU Cost Linking & Partitions)
           │ Link Cost & Release
           ▼
[ FABRICAÇÃO ]         (Status: MANUFACTURING - Production Floor & Cutting)
           │ Complete Cutting
           ▼
[ FATURAMENTO ]        (Status: BILLING - NF-e Number, Transp, Invoice PDF)
           │ Upload Invoice PDF
           ▼
[ EXPEDIÇÃO ]          (Status: SHIPPING / WAITING_DISPATCH - Cargo Photos & Canhoto)
           │ Complete Checklist
           ▼
[ CONCLUÍDOS ]         (Status: ARCHIVED / COMPLETED)
```

### 3.3 High-Performance Architecture

- **N+1 Query Elimination:** `GET /api/kanban/board` bulk-preloads all item relationships using SQLAlchemy `selectinload` / `joinedload`.
- **Concluded Cards Hygiene Filter:** Orders in terminal states (`COMPLETED`, `ARCHIVED`, `CANCELLED`) updated more than **3 days ago** are automatically excluded from the active board payload. This maintains active Kanban board response times below **50ms** regardless of database size.
- **Scroll Preservation & Alt+Tab Silent Refresh (CR-F4):** Frontend `KanbanPage.jsx` uses `fetchBoard(isBackground = true)` on window focus (`handleFocus`), skipping full-screen loading spinners and preventing UI flashing while preserving column scroll positions via a double-buffered `requestAnimationFrame` and `setTimeout(50ms, 150ms)` loop. Errant background sync attempts fail silently with `console.warn`.

### 3.4 Express Return & Commercial Cancellation Engine (CR-F3)

- **Universal Express Return:** In any production phase (PCP, Produção, Faturamento, Expedição), choosing `[Cancelamento de Pedido]` in the Return Modal (`POST /api/kanban/return-status` or `POST /api/kanban/pos/{po_id}/return`) dynamically updates the modal title to "Devolver para Comercial (Cancelamento)" and routes the PO directly back to `SUBMITTED` (Comercial), bypassing all intermediate stages. All PO line items have `status_item` synchronized to `SUBMITTED`.
- **Gated Commercial Cancellation:** At the Commercial stage (`SUBMITTED`/`DRAFT`), the `[ 🚫 Cancelar Pedido ]` button is visible and active only for users with `admin`/`master` roles or `can_cancel_commercial = true`.
- **Transactional Cascade & Audit:** `POST /api/kanban/pos/{po_id}/cancel` validates minimum 3-character reason, sets `po.status_macro = 'CANCELLED'`, cascades `status_item = 'CANCELLED'` across all order items and child partitions, and logs an immutable SHA-256 Ledger V2 audit record.

---

## 4. Financial Calculation Engines (Formulas & DRE)

Source of truth: [frontend/src/utils/marginCalculator.js](file:///c:/Documentos/BotCase/FlexFlow/frontend/src/utils/marginCalculator.js) & [backend/routers/kanban.py](file:///c:/Documentos/BotCase/FlexFlow/backend/routers/kanban.py).

### 4.1 Full Tax Burden & Present Value (VP) Discounting

$$\text{Tax Rate} = \frac{9.25\% \text{ (PIS/COFINS Baseline)} + \text{ICMS \% (Item ONET)}}{100}$$

$$\text{Gross Revenue} = \text{item\_total\_value}$$

$$\text{Net Nominal Revenue} = \text{Gross Revenue} \times (1 - \text{Tax Rate})$$

For orders with deferred payment terms (`Cond.Pgto` / `payment_terms`, e.g. `28/35/42` $\rightarrow$ average 35 days), revenue is discounted to Present Value (VP) at a financial rate of **2.5% per 30-day period**:

$$\text{Days} = \text{parse\_payment\_term\_days}(payment\_terms)$$

$$\text{VP Net Revenue} = \frac{\text{Net Nominal Revenue}}{1 + 0.025 \times \left(\frac{\text{Days}}{30}\right)}$$

---

### 4.2 Unit-Aware Industrial Cost Engine

Industrial production cost is calculated strictly according to the item's unit of measurement (`unidade_medida`):

1. **M2 (Square Meters):**
   $$\text{Total Cost} = \text{Quantity}_{\text{m2}} \times \text{Custo}_{\text{m2}}$$

2. **KG (Kilograms):**
   $$\text{Cost}_{\text{kg}} = \text{Custo}_{\text{m2}} \times \text{Rendimento}_{\text{m2/kg}}$$
   $$\text{Total Cost} = \text{Quantity}_{\text{kg}} \times \text{Cost}_{\text{kg}}$$

3. **RL / UN (Rolls / Units):**
   $$\text{Width}_{\text{m}} = \frac{\text{Width}_{\text{mm}}}{1000}$$
   $$\text{Total Area}_{\text{m2}} = \text{Width}_{\text{m}} \times \text{Length}_{\text{m}} \times \text{Quantity}$$
   $$\text{Total Cost} = \text{Total Area}_{\text{m2}} \times \text{Custo}_{\text{m2}}$$

4. **Fallback:**
   $$\text{Total Cost} = \text{Quantity} \times \text{Custo}_{\text{m2}}$$

---

### 4.3 Official Net Profit Margin Formula

$$\text{Net Profit (Lucro Líquido)} = \text{VP Net Revenue} - \text{Total Industrial Cost}$$

$$\text{Net Profit Margin \%} = \left(\frac{\text{Net Profit}}{\text{Gross Revenue}}\right) \times 100$$

> **Business Boundary Rule:** Net Profit Margin percentage is strictly capped at $\le 100.0\%$ to eliminate mathematical division anomalies on sample or bonification orders.

---

### 4.4 Cost UI Table Display Standards

In the **Gerenciar Custos** (`/costs`) interface:
- Column **`CUSTO M²`**: Displays `custo_mp_kg` (R$/m²).
- Column **`RENDIMENTO`**: Displays `rendimento` (m²/kg).
- Column **`CUSTO KG`**: Calculated dynamically in UI via multiplication:
  $$\text{Custo KG} = \text{Custo M²} \times \text{Rendimento}$$

---

## 5. Security & Access Control (RBAC & Separation of Duties)

### 5.1 Commercial Salesperson Data Isolation

Implemented in [backend/utils/salesperson_filter.py](file:///c:/Documentos/BotCase/FlexFlow/backend/utils/salesperson_filter.py):
- **User Role `user` (Comercial Salesperson):** Restricted strictly to viewing sales orders where `extra_metadata.salesperson` matches the user's registered name/email.
- **Roles `operator`, `admin`, `master`:** Bypass salesperson filters to maintain complete operational visibility across all pipeline columns.

### 5.2 Endpoint Security Gating

- **`/api/import/*` Endpoints:** Restricted to `comercial@promaflex.com.br` or users with `admin` / `master` roles.
- **`/api/dashboard/*` & KPI Endpoints:** Restricted strictly to `admin` / `master` roles.

### 5.3 HTTP Security Middleware

Defined in [backend/middleware.py](file:///c:/Documentos/BotCase/FlexFlow/backend/middleware.py):
- Appends security headers on all HTTP responses:
  - `X-Frame-Options: DENY`
  - `X-Content-Type-Options: nosniff`
  - `Strict-Transport-Security: max-age=31536000; includeSubDomains`
  - `Content-Security-Policy: default-src 'self' ...`
- Automatically blocks vulnerability scanner probes (`.php`, `wp-admin`, `.env`, `etc/passwd`) with immediate `404 Not Found` responses.

---

## 6. Active Improvement Backlog (CR-F1 to CR-F7)

Below is the active backlog of 7 work fronts under client evaluation, highlighting the **Phase 1 Priority Scope (R\$ 15k / 30-day target)**:

| ID | Title | Scope & Description | Status / Dependency | Priority |
| :--- | :--- | :--- | :--- | :--- |
| **CR-F1** | **Módulo de Estoque em M² + Endereçamento** | Full inventory tracking in M², physical rack/aisle location addressing (`A-01-02`), and real-time roll availability check during PCP linking. | **Phase 1 Priority** | 🔴 HIGH |
| **CR-F2** | **Alterações ONET + [Atributo]** | Parsing structured attribute tags `[Atributo]` from ONET item notes. | Blocked (Awaiting Ewaldo/ONET) | 🟡 MED |
| **CR-F3** | **Cancelamento Comercial c/ Flag + Devolução Expressa** | Delegated user cancellation flag (`can_cancel_commercial`), universal express return (`[Cancelamento de Pedido]`) direct to Comercial, and transactional order/item cancellation cascade. | 🟢 **COMPLETED (Live Production)** | 🔴 HIGH |
| **CR-F4** | **Alt+Tab sem Spinner** | Silent background refetching on window focus without triggering global loading spinners (`fetchBoard(true)`). | 🟢 **COMPLETED (Live Production)** | 🟢 QUICK |
| **CR-F5** | **Calculadora de Apontamento + Medidas no Card do PCP** | On-card dimension calculator (width $\times$ length $\times$ qty) directly visible on PCP Kanban cards. | **Phase 1 Priority** | 🔴 HIGH |
| **CR-F6** | **Picking List da Logística** | Automated truck loading picking list generation. | Blocked (Awaiting Ewaldo/ONET) | 🟡 MED |
| **CR-F7** | **Relatório do Kanban com Valores Financeiros** | Financial report export for Faturamento (`GET /api/reports/po-export`) with RBAC/SoD gating (29 cols vs 26 cols) and currency formatting. | 🟢 **COMPLETED (Live Production)** | 🔴 HIGH |

---

## 7. DevOps & Operational Playbook

### 7.1 Local Development Proxy & Port Allocation

- **PostgreSQL Proxy Port:** Runs on **Port `5434`** (or `5435`).
  > **Port Safety:** Do NOT use Port `5432` locally to prevent conflicts with local PostgreSQL or FlowCare database instances.
- **Starting Local Cloud SQL Proxy:**
  ```powershell
  python backend/scripts/audit_po_214050.py
  ```
  *(Automated script fetches GCP access token via `gcloud` and launches `cloud-sql-proxy.exe` on port `5434`).*

### 7.2 Zero-Downtime Production Deployment Command

To deploy backend and frontend updates to Google Cloud Run:

```bash
git push origin main && gcloud run deploy flexflow-app --source . --region southamerica-east1 --max-instances 2
```

---

*End of Master Handover Specification (`HANDOVER.md`).*
