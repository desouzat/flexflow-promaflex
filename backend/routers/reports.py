"""
FF-HARDENING-012.2 [Item 5]: Reports Router
GET /api/reports/po-export — Generates a downloadable CSV report of all
purchase orders for the authenticated user's tenant.

GET /api/reports/cancellations-export — Exports only CANCELLED POs.

Security: All DB queries are strictly filtered by current_user.tenant_id
to prevent cross-tenant data leaks.
"""
import csv
import io
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

try:
    from backend.database import get_db
    from backend.models import AuditLog, OrderItem, PurchaseOrder
    from backend.routers.auth import UserInfo, get_current_user
    from backend.utils.business_hours import (
        calculate_business_hours,
        get_sla_config_from_db,
    )
except ModuleNotFoundError:
    from database import get_db
    from models import AuditLog, OrderItem, PurchaseOrder
    from routers.auth import UserInfo, get_current_user
    from utils.business_hours import calculate_business_hours, get_sla_config_from_db

router = APIRouter(prefix="/api/reports", tags=["Reports"])

# ── SLA area mapping ────────────────────────────────────────────────────────
# Maps status_macro values to PromaFlex operational areas.
# Must stay in sync with kanban.py area_sla_ratios.
_STATUS_AREA: Dict[str, str] = {
    "DRAFT":                        "Comercial",
    "SUBMITTED":                    "Comercial",
    "ANALISE_CREDITO":              "Comercial",
    "WAITING_COMMERCIAL_PARTITION": "Comercial",
    "APPROVED":                     "PCP",
    "WAITING_MATERIAL":             "PCP",
    "MANUFACTURING":                "Produção",
    "BILLING":                      "Faturamento",
    "FINANCE":                      "Faturamento",
    "SHIPPING":                     "Expedição",
    "COMPLETED":                    "Expedição",
    "ARCHIVED":                     "Arquivado",
    "ARCHIVED_PARTITIONED":         "Arquivado",
    "CANCELLED":                    "Cancelado",
}

_FINISHED_STATUSES = {"COMPLETED", "CANCELLED", "ARCHIVED", "ARCHIVED_PARTITIONED"}
_AREAS_OF_INTEREST = ["PCP", "Produção", "Faturamento"]


# ── Helper: project a business-hours deadline forward from a start datetime ─
def _add_business_hours(
    start: datetime,
    hours_to_add: float,
    config: dict,
) -> datetime:
    """Return the datetime that is `hours_to_add` business hours after `start`.

    Walks forward day-by-day respecting sla_start_hour / sla_end_hour /
    sla_working_days from `config`.
    """
    start_hour: int = int(config.get("sla_start_hour", 8))
    end_hour: int = int(config.get("sla_end_hour", 18))

    # Re-use the same working-days parser from business_hours module via config keys;
    # We replicate the simple set logic here to avoid importing a private helper.
    _DAY_MAP = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
    raw = str(config.get("sla_working_days", "Mon-Fri")).strip()
    if "-" in raw and "," not in raw:
        parts = [p.strip().lower()[:3] for p in raw.split("-", 1)]
        if len(parts) == 2 and parts[0] in _DAY_MAP and parts[1] in _DAY_MAP:
            s, e = _DAY_MAP[parts[0]], _DAY_MAP[parts[1]]
            working_days = set(range(s, e + 1)) if s <= e else {0, 1, 2, 3, 4}
        else:
            working_days = {0, 1, 2, 3, 4}
    elif "," in raw:
        working_days = {_DAY_MAP[t.strip().lower()[:3]] for t in raw.split(",") if t.strip().lower()[:3] in _DAY_MAP} or {0, 1, 2, 3, 4}
    else:
        working_days = {0, 1, 2, 3, 4}

    remaining = float(hours_to_add)
    current = start
    if start_hour >= end_hour:
        start_hour, end_hour = 8, 18

    while remaining > 1e-9:
        if current.weekday() in working_days:
            day_open = current.replace(hour=start_hour, minute=0, second=0, microsecond=0)
            day_close = current.replace(hour=end_hour, minute=0, second=0, microsecond=0)
            effective_start = max(current, day_open)
            if effective_start < day_close:
                available_h = (day_close - effective_start).total_seconds() / 3600.0
                if remaining <= available_h:
                    return effective_start + timedelta(hours=remaining)
                remaining -= available_h

        # Advance to the start of the next calendar day
        next_day = (current + timedelta(days=1)).replace(
            hour=start_hour, minute=0, second=0, microsecond=0
        )
        current = next_day

    return current


# ── Helper: SLA traffic-light label ────────────────────────────────────────
def _sla_label(elapsed_h: float, limit_h: float, is_finished: bool) -> str:
    """Return 'Verde', 'Amarelo', or 'Vermelho' SLA status."""
    if is_finished:
        return "Verde"
    if limit_h <= 0:
        return ""
    pct = elapsed_h / limit_h
    if pct >= 1.0:
        return "Vermelho"
    if pct >= 0.8:
        return "Amarelo"
    return "Verde"


# ── Helper: bulk-load audit logs for a set of POs ──────────────────────────
def _load_audit_logs_by_po(
    db: Session,
    po_ids: List,
) -> Dict[str, List]:
    """
    One-shot load of all AuditLog entries for the given list of PO IDs.

    Returns a dict  { po_id_str → [AuditLog, ...] }  sorted by created_at asc.
    The lookup key is `str(po.id)` to avoid UUID type mismatches.
    """
    if not po_ids:
        return {}

    # Step 1: get all OrderItems for these POs, capturing item_id → po_id mapping
    items = (
        db.query(OrderItem.id, OrderItem.purchase_order_id)
        .filter(OrderItem.purchase_order_id.in_(po_ids))
        .all()
    )
    item_to_po: Dict[str, str] = {
        str(row.id): str(row.purchase_order_id) for row in items
    }
    if not item_to_po:
        return {}

    item_ids = list(item_to_po.keys())

    # Step 2: load all audit logs for these items in one query
    logs = (
        db.query(AuditLog)
        .filter(AuditLog.item_id.in_(item_ids))
        .order_by(AuditLog.created_at.asc())
        .all()
    )

    # Step 3: group by po_id
    by_po: Dict[str, List] = defaultdict(list)
    for log in logs:
        po_id_str = item_to_po.get(str(log.item_id))
        if po_id_str:
            by_po[po_id_str].append(log)

    return by_po


# ── Helper: compute per-PO stage timeline from audit logs ───────────────────
def _compute_stage_times(
    logs: List,
    po_status_macro: str,
    po_created_at: datetime,
    config: dict,
    now: datetime,
) -> Dict:
    """
    Given sorted AuditLog entries for a PO, compute:
      - stage_entry_at: when the PO entered its current status_macro
      - hours_in_current_stage: business hours since stage_entry_at
      - hours_by_area: dict of { area_name → total_business_hours }

    Uses earliest-entry-wins logic across all items to build a PO-level timeline.
    """
    # Collect earliest timestamp for each distinct status encountered
    earliest_entry: Dict[str, datetime] = {}
    for log in logs:
        ts = log.created_at
        # Normalise to naive UTC for arithmetic
        if ts is not None and ts.tzinfo is not None:
            ts = ts.astimezone(timezone.utc).replace(tzinfo=None)
        if ts is None:
            continue
        status = log.to_status
        if status not in earliest_entry or ts < earliest_entry[status]:
            earliest_entry[status] = ts

    # Ensure the origin status (whatever the PO started at) is anchored to created_at
    po_created_naive = po_created_at
    if po_created_naive is not None and po_created_naive.tzinfo is not None:
        po_created_naive = po_created_naive.astimezone(timezone.utc).replace(tzinfo=None)

    # Build a sorted timeline: [(timestamp, status), ...]
    # Seed from created_at so we always have a starting point
    timeline = []
    if po_created_naive:
        # Add the implicit "entry into first status" at PO creation
        first_status = logs[0].to_status if logs else po_status_macro
        timeline.append((po_created_naive, first_status))

    for status, ts in sorted(earliest_entry.items(), key=lambda x: x[1]):
        timeline.append((ts, status))

    # Deduplicate and sort by timestamp
    seen_ts = set()
    unique_timeline = []
    for ts, status in sorted(timeline, key=lambda x: x[0]):
        key = (ts, status)
        if key not in seen_ts:
            seen_ts.add(key)
            unique_timeline.append((ts, status))

    now_naive = now
    if now_naive.tzinfo is not None:
        now_naive = now_naive.astimezone(timezone.utc).replace(tzinfo=None)

    # ── Accumulate business hours by area ──────────────────────────────────
    hours_by_area: Dict[str, float] = defaultdict(float)
    for i, (ts_enter, status) in enumerate(unique_timeline):
        ts_exit = unique_timeline[i + 1][0] if i + 1 < len(unique_timeline) else now_naive
        if ts_exit <= ts_enter:
            continue
        area = _STATUS_AREA.get(status, "Outro")
        bh = calculate_business_hours(ts_enter, ts_exit, config)
        hours_by_area[area] += bh

    # ── Time in current stage ──────────────────────────────────────────────
    stage_entry_at = earliest_entry.get(po_status_macro)
    if stage_entry_at is None and po_created_naive:
        stage_entry_at = po_created_naive
    hours_in_stage = 0.0
    if stage_entry_at and now_naive > stage_entry_at:
        hours_in_stage = calculate_business_hours(stage_entry_at, now_naive, config)

    return {
        "hours_in_current_stage": round(hours_in_stage, 2),
        "hours_by_area": dict(hours_by_area),
    }


# ════════════════════════════════════════════════════════════════════════════
# GET /api/reports/po-export
# ════════════════════════════════════════════════════════════════════════════
@router.get("/po-export")
async def export_pos_csv(
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Export all purchase orders for the tenant as a CSV file.

    Columns (21 total):
        ── Core PO & Item Data (12 columns) ──────────────────────────────────
        Nº PO | CLIENTE | PRODUTO | DATA RECEBIMENTO | UNIDADE MEDIDA |
        QTDE | PERSONALIZADO | LARGURA | COMPRIMENTO |
        STATUS PRODUÇÃO | QTD REAL PRODUZIDA | PERDA TÉCNICA

        ── SLA & Audit Columns (9 columns, Sponsor-approved — Celso) ─────────
        ETAPA ATUAL | STATUS SLA | HORAS SLA DECORRIDAS |
        PRAZO LIMITE SLA | HORAS DE ATRASO | JUSTIFICATIVA OCORRÊNCIA |
        DATA ENTRADA KANBAN | SLA ENTREGA CLIENTE |
        TEMPO ETAPA ATUAL (h) | TEMPO PCP (h) | TEMPO PRODUÇÃO (h) | TEMPO FATURAMENTO (h)

    Security: Strictly filtered by current_user.tenant_id — no cross-tenant
    data can appear in the response.
    """
    # ── Fetch POs — tenant-scoped ─────────────────────────────────────────
    pos = (
        db.query(PurchaseOrder)
        .filter(PurchaseOrder.tenant_id == current_user.tenant_id)
        .order_by(PurchaseOrder.created_at.desc())
        .all()
    )

    # ── Load SLA config once for the tenant ──────────────────────────────
    sla_config = get_sla_config_from_db(db, current_user.tenant_id)
    sla_limit_h = float(sla_config.get("sla_total_hours", 240))

    # ── Bulk-load audit logs to avoid N+1 queries ─────────────────────────
    po_ids = [po.id for po in pos]
    audit_by_po = _load_audit_logs_by_po(db, po_ids)

    now_utc = datetime.utcnow()

    # ── Build CSV in memory ──────────────────────────────────────────────
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_MINIMAL)

    # Header row — 21 columns
    writer.writerow([
        # ── Core PO & Item data ───────────────────────────────────────────
        "Nº PO",
        "CLIENTE",
        "PRODUTO",
        "DATA RECEBIMENTO",
        "UNIDADE MEDIDA",
        "QTDE",
        "PERSONALIZADO",
        "LARGURA",
        "COMPRIMENTO",
        "STATUS PRODUÇÃO",
        "QTD REAL PRODUZIDA",
        "PERDA TÉCNICA",
        # ── SLA & Audit columns (9 new, Sponsor-approved) ─────────────────
        "ETAPA ATUAL",
        "STATUS SLA",
        "HORAS SLA DECORRIDAS",
        "PRAZO LIMITE SLA",
        "HORAS DE ATRASO",
        "JUSTIFICATIVA OCORRÊNCIA",
        "DATA ENTRADA KANBAN",
        "SLA ENTREGA CLIENTE",
        "TEMPO ETAPA ATUAL (h)",
        "TEMPO PCP (h)",
        "TEMPO PRODUÇÃO (h)",
        "TEMPO FATURAMENTO (h)",
    ])

    for po in pos:
        # ── Resolve client name ───────────────────────────────────────────
        client_name = ""
        if po.partition_metadata and "client_name" in po.partition_metadata:
            client_name = po.partition_metadata["client_name"] or ""
        if not client_name:
            client_name = getattr(po, "client_name", "") or ""
        if not client_name and po.items:
            client_name = (
                po.items[0].extra_metadata.get("client_name", "")
                if po.items[0].extra_metadata
                else ""
            )

        # ── Date received ─────────────────────────────────────────────────
        date_received = po.created_at.strftime("%d/%m/%Y") if po.created_at else ""

        # ── SLA computations (PO-level, shared across all item rows) ──────
        po_created_naive = po.created_at
        if po_created_naive is not None and po_created_naive.tzinfo is not None:
            po_created_naive = po_created_naive.astimezone(timezone.utc).replace(tzinfo=None)

        is_finished = po.status_macro in _FINISHED_STATUSES

        # Elapsed business hours (subtract any SLA freeze time)
        elapsed_h = 0.0
        sla_deadline_str = ""
        sla_status_label = ""
        overdue_h_str = ""

        if po_created_naive:
            raw_elapsed_h = calculate_business_hours(po_created_naive, now_utc, sla_config)
            hold_h = float(getattr(po, "total_hold_time_seconds", 0) or 0) / 3600.0
            elapsed_h = max(0.0, raw_elapsed_h - hold_h)

            # SLA deadline: project sla_limit_h forward from created_at
            deadline_dt = _add_business_hours(po_created_naive, sla_limit_h, sla_config)
            sla_deadline_str = deadline_dt.strftime("%d/%m/%Y %H:%M")

            sla_status_label = _sla_label(elapsed_h, sla_limit_h, is_finished)
            overdue_h = max(0.0, elapsed_h - sla_limit_h) if not is_finished else 0.0
            overdue_h_str = f"{overdue_h:.2f}".replace(".", ",") if overdue_h > 0 else ""

        elapsed_h_str = f"{elapsed_h:.2f}".replace(".", ",")

        # Justification: category + free-text
        just_cat = po.sla_justification_category or ""
        just_txt = po.sla_justification_text or ""
        if just_cat and just_txt:
            justificativa = f"{just_cat}: {just_txt}"
        elif just_cat:
            justificativa = just_cat
        else:
            justificativa = just_txt

        # Data de entrada no Kanban (same as created_at, full timestamp)
        data_entrada = (
            po.created_at.strftime("%d/%m/%Y %H:%M") if po.created_at else ""
        )

        # SLA Entrega ao Cliente — expected_delivery_date property
        entrega_cliente = ""
        edd = getattr(po, "expected_delivery_date", None)
        if edd is not None:
            try:
                if hasattr(edd, "strftime"):
                    entrega_cliente = edd.strftime("%d/%m/%Y")
                else:
                    entrega_cliente = str(edd)
            except Exception:
                entrega_cliente = str(edd)

        # Stage timing from audit logs
        po_logs = audit_by_po.get(str(po.id), [])
        stage_data = _compute_stage_times(
            logs=po_logs,
            po_status_macro=po.status_macro,
            po_created_at=po.created_at,
            config=sla_config,
            now=now_utc,
        )
        hours_in_stage_str = (
            f"{stage_data['hours_in_current_stage']:.2f}".replace(".", ",")
        )
        hba = stage_data["hours_by_area"]
        tempo_pcp_str = f"{hba.get('PCP', 0.0):.2f}".replace(".", ",")
        tempo_producao_str = f"{hba.get('Produção', 0.0):.2f}".replace(".", ",")
        tempo_fatur_str = f"{hba.get('Faturamento', 0.0):.2f}".replace(".", ",")

        # ── Etapa Atual (human label) ─────────────────────────────────────
        etapa_atual = po.status_macro or ""

        # ── Build SLA tuple shared across all rows for this PO ────────────
        sla_cols = [
            etapa_atual,
            sla_status_label,
            elapsed_h_str,
            sla_deadline_str,
            overdue_h_str,
            justificativa,
            data_entrada,
            entrega_cliente,
            hours_in_stage_str,
            tempo_pcp_str,
            tempo_producao_str,
            tempo_fatur_str,
        ]

        if not po.items:
            # PO with no items — emit one row with blanks for item fields
            writer.writerow([
                po.po_number,
                client_name,
                "",             # PRODUTO
                date_received,
                "",             # UNIDADE MEDIDA
                "",             # QTDE
                "",             # PERSONALIZADO
                "",             # LARGURA
                "",             # COMPRIMENTO
                "",             # STATUS PRODUÇÃO
                "",             # QTD REAL PRODUZIDA
                "",             # PERDA TÉCNICA
                *sla_cols,
            ])
            continue

        for item in po.items:
            meta = item.extra_metadata or {}

            # Produto / description
            produto = (
                meta.get("description")
                or meta.get("product_description")
                or item.sku
                or ""
            )

            # Client name — prefer item-level if available
            item_client = meta.get("client_name") or client_name

            # Unit of measure
            unit = (
                meta.get("unit")
                or meta.get("unidade_medida")
                or meta.get("Unit")
                or ""
            )

            # Quantity
            qty = float(item.quantity) if item.quantity else 0
            qty_str = f"{qty:g}"

            # Personalized
            personalizado = "Sim" if item.is_personalized else "Não"

            # Dimensions — ORM columns first, then JSONB fallback
            raw_largura = getattr(item, "width", None) or getattr(item, "largura", None)
            if raw_largura is None:
                raw_largura = (
                    meta.get("largura") or meta.get("Largura")
                    or meta.get("width") or meta.get("Width")
                )
            largura = str(raw_largura) if raw_largura not in (None, "") else ""

            raw_comprimento = (
                getattr(item, "length", None) or getattr(item, "comprimento", None)
            )
            if raw_comprimento is None:
                raw_comprimento = (
                    meta.get("comprimento") or meta.get("Comprimento")
                    or meta.get("length") or meta.get("Length")
                )
            comprimento = str(raw_comprimento) if raw_comprimento not in (None, "") else ""

            # FF-HARDENING-013 Item 13A: per-SKU production metrics
            status_producao = meta.get("status_producao") or ""
            qtd_real_produzida = meta.get("qtd_real_produzida")
            qtd_real_str = str(qtd_real_produzida) if qtd_real_produzida is not None else ""
            perda_tecnica = meta.get("perda_tecnica")
            perda_str = str(perda_tecnica) if perda_tecnica is not None else ""

            writer.writerow([
                po.po_number,
                item_client,
                produto,
                date_received,
                unit,
                qty_str,
                personalizado,
                largura,
                comprimento,
                status_producao,
                qtd_real_str,
                perda_str,
                *sla_cols,
            ])

    # ── Stream with BOM for Excel UTF-8 compatibility ─────────────────────
    csv_content = "\ufeff" + output.getvalue()
    output.close()

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"pedidos_export_{timestamp}.csv"

    return StreamingResponse(
        iter([csv_content.encode("utf-8-sig")]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "text/csv; charset=utf-8",
        },
    )


# ════════════════════════════════════════════════════════════════════════════
# GET /api/reports/cancellations-export
# ════════════════════════════════════════════════════════════════════════════
@router.get("/cancellations-export")
async def export_cancellations_csv(
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Export all CANCELLED purchase orders for the tenant as a CSV file.

    Mesa de Conferência — Relatório de Cancelamentos.

    Columns (8 in order):
        Número PO | Cliente | Valor Total do Pedido | SKU |
        Código estruturado | Justificativa de Cancelamento |
        Data/hora cancelamento (America/Sao_Paulo) | Usuário

    Security: Strictly filtered by current_user.tenant_id — no cross-tenant
    data can appear in the response.
    """
    from zoneinfo import ZoneInfo  # Python 3.9+

    SP_TZ = ZoneInfo("America/Sao_Paulo")

    # ── Fetch only CANCELLED POs — tenant-scoped ──────────────────────────
    pos = (
        db.query(PurchaseOrder)
        .filter(
            PurchaseOrder.tenant_id == current_user.tenant_id,
            PurchaseOrder.status_macro == "CANCELLED",
        )
        .order_by(PurchaseOrder.updated_at.desc())
        .all()
    )

    # ── Build CSV in memory ───────────────────────────────────────────────
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_MINIMAL)

    # Header row — exactly 8 columns as specified
    writer.writerow([
        "Número PO",
        "Cliente",
        "Valor Total do Pedido",
        "SKU",
        "Código estruturado",
        "Justificativa de Cancelamento",
        "Data/hora cancelamento",
        "Usuário",
    ])

    for po in pos:
        # ── Resolve shared PO-level fields ────────────────────────────────
        client_name = po.client_name or ""

        # Valor total — prefer po_total_value ORM column, fall back to sum of item prices
        if po.po_total_value is not None:
            total_value_str = f"{float(po.po_total_value):.2f}".replace(".", ",")
        else:
            computed = sum(
                float(item.price or 0) * float(item.quantity or 0)
                for item in (po.items or [])
            )
            total_value_str = f"{computed:.2f}".replace(".", ",")

        # Justification text
        justificativa = po.sla_justification_text or ""
        usuario = po.sla_justification_user or ""

        # Cancellation timestamp — convert UTC → America/Sao_Paulo
        cancelamento_str = ""
        if po.sla_justification_at:
            utc_dt = po.sla_justification_at
            if utc_dt.tzinfo is None:
                utc_dt = utc_dt.replace(tzinfo=timezone.utc)
            sp_dt = utc_dt.astimezone(SP_TZ)
            cancelamento_str = sp_dt.strftime("%d/%m/%Y %H:%M:%S")

        if not po.items:
            writer.writerow([
                po.po_number,
                client_name,
                total_value_str,
                "",   # SKU
                "",   # Código estruturado
                justificativa,
                cancelamento_str,
                usuario,
            ])
            continue

        for item in po.items:
            meta = item.extra_metadata or {}
            sku = item.sku or ""
            codigo_estruturado = (
                meta.get("codigo_estruturado")
                or meta.get("cod_estruturado")
                or meta.get("codigo")
                or ""
            )
            writer.writerow([
                po.po_number,
                client_name,
                total_value_str,
                sku,
                codigo_estruturado,
                justificativa,
                cancelamento_str,
                usuario,
            ])

    # ── Stream with BOM for Excel UTF-8 compatibility ─────────────────────
    csv_content = "\ufeff" + output.getvalue()
    output.close()

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"cancelamentos_export_{timestamp}.csv"

    return StreamingResponse(
        iter([csv_content.encode("utf-8-sig")]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "text/csv; charset=utf-8",
        },
    )
