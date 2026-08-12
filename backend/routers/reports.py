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
import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, selectinload

logger = logging.getLogger(__name__)

def safe_format_date(dt) -> str:
    """Format any date object or date string to dd/mm/yyyy safely."""
    if not dt:
        return ""
    if hasattr(dt, 'strftime'):
        return dt.strftime('%d/%m/%Y')
    val_str = str(dt).strip()
    if not val_str:
        return ""
    if len(val_str) == 10 and val_str[2] == '/' and val_str[5] == '/':
        return val_str
    if "-" in val_str:
        try:
            parts = val_str.split("T")[0].split("-")
            if len(parts) == 3:
                return f"{parts[2]}/{parts[1]}/{parts[0]}"
        except Exception:
            pass
    return val_str

def safe_get_field(obj, attr: str, default: any = "") -> any:
    """Safely extract key/attribute from a dictionary, ORM model, or JSON-parsed object."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        val = obj.get(attr)
        return val if val is not None else default
    if isinstance(obj, str):
        try:
            parsed = json.loads(obj)
            if isinstance(parsed, dict):
                val = parsed.get(attr)
                return val if val is not None else default
        except Exception:
            pass
        return default
    if hasattr(obj, "extra_metadata"):
        meta = getattr(obj, "extra_metadata", None)
        if isinstance(meta, dict) and attr in meta:
            val = meta.get(attr)
            if val not in (None, ""):
                return val
        elif isinstance(meta, str):
            try:
                parsed = json.loads(meta)
                if isinstance(parsed, dict) and attr in parsed:
                    val = parsed.get(attr)
                    if val not in (None, ""):
                        return val
            except Exception:
                pass
    if hasattr(obj, attr):
        val = getattr(obj, attr, None)
        return val if val not in (None, "") else default
    return default

safe_get_dict_field = safe_get_field

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

from backend.utils.salesperson_filter import (
    get_salesperson_filter_name,
    filter_pos_by_salesperson
)

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

# ── Human-readable Portuguese labels for Kanban stage names ─────────────────────
# Used in the ETAPA ATUAL column of the CSV export.
_STATUS_TRANSLATION: Dict[str, str] = {
    "DRAFT":                        "Rascunho",
    "SUBMITTED":                    "Submetido",
    "ANALISE_CREDITO":              "Análise de Crédito",
    "WAITING_COMMERCIAL_PARTITION": "Comercial (Partição)",
    "APPROVED":                     "PCP",
    "WAITING_MATERIAL":             "Aguardando Material",
    "MANUFACTURING":                "Produção/Embalagem",
    "BILLING":                      "Faturamento",
    "FINANCE":                      "Financeiro",
    "SHIPPING":                     "Expedição",
    "COMPLETED":                    "Concluído",
    "ARCHIVED":                     "Arquivado",
    "ARCHIVED_PARTITIONED":         "Arquivado (Particionado)",
    "CANCELLED":                    "Cancelado",
}


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
        db.query(OrderItem.id, OrderItem.po_id)  # FK column is po_id, NOT purchase_order_id
        .filter(OrderItem.po_id.in_(po_ids))
        .all()
    )
    item_to_po: Dict[str, str] = {
        str(row.id): str(row.po_id) for row in items
    }
    if not item_to_po:
        return {}

    item_id_objs = [row.id for row in items]

    # Step 2: load all audit logs for these items in one query
    logs = (
        db.query(AuditLog)
        .filter(AuditLog.item_id.in_(item_id_objs))
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
    po_created_at,
    config: dict,
    now: datetime,
) -> Dict:
    """
    Given sorted AuditLog entries for a PO, compute:
      - stage_entry_at: when the PO entered its current status_macro
      - hours_in_current_stage: business hours since stage_entry_at
      - hours_by_area: dict of { area_name → total_business_hours }

    Uses earliest-entry-wins logic across all items to build a PO-level timeline.
    All inputs are null-guarded — never raises on missing dates or empty logs.
    """
    _ZERO_RESULT = {"hours_in_current_stage": 0.0, "hours_by_area": {}}

    # Guard: can't compute anything without a creation timestamp
    if po_created_at is None:
        return _ZERO_RESULT

    # Normalise now to naive UTC
    now_naive = now
    if now_naive is not None and getattr(now_naive, 'tzinfo', None) is not None:
        now_naive = now_naive.astimezone(timezone.utc).replace(tzinfo=None)
    if now_naive is None:
        now_naive = datetime.utcnow()

    # Collect earliest timestamp for each distinct status encountered
    earliest_entry: Dict[str, datetime] = {}
    for log in (logs or []):
        ts = getattr(log, 'created_at', None)
        if ts is None:
            continue
        # Normalise to naive UTC for arithmetic
        if ts.tzinfo is not None:
            ts = ts.astimezone(timezone.utc).replace(tzinfo=None)
        status = getattr(log, 'to_status', None)
        if not status:
            continue
        if status not in earliest_entry or ts < earliest_entry[status]:
            earliest_entry[status] = ts

    # Ensure the origin status (whatever the PO started at) is anchored to created_at
    po_created_naive = po_created_at
    if getattr(po_created_naive, 'tzinfo', None) is not None:
        po_created_naive = po_created_naive.astimezone(timezone.utc).replace(tzinfo=None)

    # Build a sorted timeline: [(timestamp, status), ...]
    # Seed from created_at so we always have a starting point
    timeline = []
    if po_created_naive:
        # Add the implicit "entry into first status" at PO creation
        first_log = logs[0] if logs else None
        first_status = getattr(first_log, 'to_status', None) if first_log else None
        first_status = first_status or po_status_macro or "DRAFT"
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

    # ── Accumulate business hours by area ──────────────────────────────────
    hours_by_area: Dict[str, float] = defaultdict(float)
    for i, (ts_enter, status) in enumerate(unique_timeline):
        ts_exit = unique_timeline[i + 1][0] if i + 1 < len(unique_timeline) else now_naive
        if ts_exit <= ts_enter:
            continue
        area = _STATUS_AREA.get(status, "Outro")
        try:
            bh = calculate_business_hours(ts_enter, ts_exit, config)
            hours_by_area[area] += max(0.0, bh)
        except Exception:
            pass  # never crash the export on a bad segment

    # ── Time in current stage ──────────────────────────────────────────────
    stage_entry_at = earliest_entry.get(po_status_macro or "")
    if stage_entry_at is None and po_created_naive:
        stage_entry_at = po_created_naive
    hours_in_stage = 0.0
    if stage_entry_at and now_naive > stage_entry_at:
        try:
            hours_in_stage = max(0.0, calculate_business_hours(stage_entry_at, now_naive, config))
        except Exception:
            hours_in_stage = 0.0

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

    Columns (25 total):
        ── Core PO & Item Data (13 columns) ────────────────────────────────
        Nº PO | CLIENTE | PRODUTO | CÓDIGO ESTRUTURADO | DATA RECEBIMENTO |
        UNIDADE MEDIDA | QTDE | PERSONALIZADO | LARGURA | COMPRIMENTO |
        STATUS PRODUÇÃO | QTD REAL PRODUZIDA | PERDA TÉCNICA

        ── SLA & Audit Columns (12 columns, Sponsor-approved — Celso) ──────
        ETAPA ATUAL | STATUS SLA | HORAS SLA DECORRIDAS |
        PRAZO LIMITE SLA | HORAS DE ATRASO | JUSTIFICATIVA OCORRÊNCIA |
        DATA ENTRADA KANBAN | SLA ENTREGA CLIENTE |
        TEMPO ETAPA ATUAL (h) | TEMPO PCP (h) | TEMPO PRODUÇÃO (h) | TEMPO FATURAMENTO (h)

    Security: Strictly filtered by current_user.tenant_id — no cross-tenant
    data can appear in the response.
    """
    # ── Fetch POs — tenant-scoped with eager-loaded items ─────────────────
    pos = (
        db.query(PurchaseOrder)
        .options(selectinload(PurchaseOrder.items))
        .filter(PurchaseOrder.tenant_id == current_user.tenant_id)
        .order_by(PurchaseOrder.created_at.desc())
        .all()
    )

    sp_filter = get_salesperson_filter_name(current_user, db)
    if sp_filter:
        pos = filter_pos_by_salesperson(pos, sp_filter)

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

    # Header row — 25 columns
    writer.writerow([
        # ── Core PO & Item data ───────────────────────────────────────────
        "Nº PO",
        "CLIENTE",
        "PRODUTO",
        "CÓDIGO ESTRUTURADO",
        "DATA RECEBIMENTO",
        "UNIDADE MEDIDA",
        "QTDE",
        "PERSONALIZADO",
        "LARGURA",
        "COMPRIMENTO",
        "STATUS PRODUÇÃO",
        "QTD REAL PRODUZIDA",
        "PERDA TÉCNICA",
        # ── SLA & Audit columns (13 columns, Sponsor-approved — Celso) ──────
        "ETAPA ATUAL",
        "STATUS SLA",
        "HORAS SLA DECORRIDAS",
        "PRAZO LIMITE SLA",
        "HORAS DE ATRASO",
        "JUSTIFICATIVA OCORRÊNCIA",
        "DATA ENTRADA KANBAN",
        "SLA ENTREGA CLIENTE (ONET)",
        "DATA PROGRAMADA PCP",
        "TEMPO ETAPA ATUAL (h)",
        "TEMPO PCP (h)",
        "TEMPO PRODUÇÃO (h)",
        "TEMPO FATURAMENTO (h)",
    ])

    for po in pos:
        try:
            # ── Unpack metadata safely ──────────────────────────────────
            partition_meta = po.partition_metadata if isinstance(po.partition_metadata, dict) else {}
            if isinstance(po.partition_metadata, str):
                try:
                    partition_meta = json.loads(po.partition_metadata)
                    if not isinstance(partition_meta, dict):
                        partition_meta = {}
                except Exception:
                    partition_meta = {}

            po_extra = getattr(po, "extra_metadata", None)
            extra_meta = po_extra if isinstance(po_extra, dict) else {}
            if isinstance(po_extra, str):
                try:
                    extra_meta = json.loads(po_extra)
                    if not isinstance(extra_meta, dict):
                        extra_meta = {}
                except Exception:
                    extra_meta = {}

            # ── Resolve client name ───────────────────────────────────────────
            client_name = safe_get_dict_field(partition_meta, "client_name") or getattr(po, "client_name", "") or ""
            if not client_name and po.items:
                item0_meta = po.items[0].extra_metadata if isinstance(po.items[0].extra_metadata, dict) else {}
                client_name = safe_get_dict_field(item0_meta, "client_name", "")

            # ── Date received ─────────────────────────────────────────────────
            date_received = safe_format_date(po.created_at)

            # ── SLA computations (PO-level, shared across all item rows) ──────
            po_created_naive = po.created_at
            if po_created_naive is not None and getattr(po_created_naive, 'tzinfo', None) is not None:
                po_created_naive = po_created_naive.astimezone(timezone.utc).replace(tzinfo=None)

            is_finished = (po.status_macro or "") in _FINISHED_STATUSES

            # Elapsed business hours (subtract any SLA freeze time)
            elapsed_h = 0.0
            sla_deadline_str = ""
            sla_status_label = ""
            overdue_h_str = ""

            if po_created_naive:
                try:
                    raw_elapsed_h = calculate_business_hours(po_created_naive, now_utc, sla_config)
                    hold_h = float(getattr(po, "total_hold_time_seconds", 0) or 0) / 3600.0
                    elapsed_h = max(0.0, raw_elapsed_h - hold_h)

                    # SLA deadline: project sla_limit_h forward from created_at
                    deadline_dt = _add_business_hours(po_created_naive, sla_limit_h, sla_config)
                    sla_deadline_str = deadline_dt.strftime("%d/%m/%Y %H:%M")

                    sla_status_label = _sla_label(elapsed_h, sla_limit_h, is_finished)
                    overdue_h = max(0.0, elapsed_h - sla_limit_h) if not is_finished else 0.0
                    overdue_h_str = f"{overdue_h:.2f}".replace(".", ",") if overdue_h > 0 else ""
                except Exception:
                    elapsed_h = 0.0
                    sla_deadline_str = ""
                    sla_status_label = ""
                    overdue_h_str = ""

            elapsed_h_str = f"{elapsed_h:.2f}".replace(".", ",")

            # Justification: category + free-text
            just_cat = getattr(po, "sla_justification_category", "") or ""
            just_txt = getattr(po, "sla_justification_text", "") or ""
            if just_cat and just_txt:
                justificativa = f"{just_cat}: {just_txt}"
            elif just_cat:
                justificativa = just_cat
            else:
                justificativa = just_txt

            # Data de entrada no Kanban (same as created_at, full timestamp)
            try:
                data_entrada = (
                    po.created_at.strftime("%d/%m/%Y %H:%M") if po.created_at else ""
                )
            except Exception:
                data_entrada = ""

            # Column U: SLA Entrega Cliente (ONET) - ALWAYS read expected_delivery_date directly
            entrega_cliente = safe_format_date(getattr(po, "expected_delivery_date", None))

            # DATA PROGRAMADA PCP — partition_metadata or extra_metadata data_programada
            p_prog = safe_get_dict_field(partition_meta, "data_programada") or safe_get_dict_field(extra_meta, "data_programada")
            data_programada_pcp = safe_format_date(p_prog)

            # Stage timing from audit logs
            po_logs = audit_by_po.get(str(po.id), [])
            try:
                stage_data = _compute_stage_times(
                    logs=po_logs,
                    po_status_macro=po.status_macro or "",
                    po_created_at=po.created_at,
                    config=sla_config,
                    now=now_utc,
                )
            except Exception:
                stage_data = {"hours_in_current_stage": 0.0, "hours_by_area": {}}
            hours_in_stage_str = (
                f"{stage_data['hours_in_current_stage']:.2f}".replace(".", ",")
            )
            hba = stage_data["hours_by_area"]
            tempo_pcp_str = f"{hba.get('PCP', 0.0):.2f}".replace(".", ",")
            tempo_producao_str = f"{hba.get('Produção', 0.0):.2f}".replace(".", ",")
            tempo_fatur_str = f"{hba.get('Faturamento', 0.0):.2f}".replace(".", ",")

            # ── Etapa Atual — friendly Portuguese label ───────────────────────────
            raw_status = po.status_macro or ""
            etapa_atual = _STATUS_TRANSLATION.get(raw_status, raw_status)

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
                data_programada_pcp,
                hours_in_stage_str,
                tempo_pcp_str,
                tempo_producao_str,
                tempo_fatur_str,
            ]

            if not po.items:
                # PO with no items — emit one row with blanks for item fields
                writer.writerow([
                    getattr(po, "po_number", ""),
                    client_name,
                    "",             # PRODUTO
                    "",             # CÓDIGO ESTRUTURADO
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
                meta = item.extra_metadata if isinstance(item.extra_metadata, dict) else {}
                if isinstance(item.extra_metadata, str):
                    try:
                        meta = json.loads(item.extra_metadata)
                        if not isinstance(meta, dict):
                            meta = {}
                    except Exception:
                        meta = {}

                # Produto / description
                produto = (
                    safe_get_field(meta, "description")
                    or safe_get_field(meta, "product_description")
                    or safe_get_field(item, "description")
                    or safe_get_field(item, "sku")
                    or ""
                )

                # Client name — prefer item-level if available
                item_client = safe_get_field(meta, "client_name") or safe_get_field(item, "client_name") or client_name

                # Unit of measure
                unit = (
                    safe_get_field(meta, "unit")
                    or safe_get_field(meta, "unidade_medida")
                    or safe_get_field(meta, "Unit")
                    or safe_get_field(item, "unit")
                    or ""
                )

                # Quantity
                raw_qty = getattr(item, "quantity", None)
                if raw_qty is None or raw_qty == "":
                    raw_qty = safe_get_field(meta, "quantity", 0)
                try:
                    qty = float(raw_qty) if raw_qty else 0
                    qty_str = f"{qty:g}"
                except Exception:
                    qty_str = str(raw_qty)

                # Personalized
                is_pers = getattr(item, "is_personalized", False)
                if not is_pers:
                    is_pers = bool(safe_get_field(meta, "is_personalized", False))
                personalizado = "Sim" if is_pers else "Não"

                # Dimensions — ORM columns first, then JSONB fallback
                raw_largura = getattr(item, "width", None) or getattr(item, "largura", None)
                if raw_largura in (None, ""):
                    raw_largura = (
                        safe_get_field(meta, "largura") or safe_get_field(meta, "Largura")
                        or safe_get_field(meta, "width") or safe_get_field(meta, "Width")
                    )
                largura = str(raw_largura) if raw_largura not in (None, "") else ""

                raw_comprimento = getattr(item, "length", None) or getattr(item, "comprimento", None)
                if raw_comprimento in (None, ""):
                    raw_comprimento = (
                        safe_get_field(meta, "comprimento") or safe_get_field(meta, "Comprimento")
                        or safe_get_field(meta, "length") or safe_get_field(meta, "Length")
                    )
                comprimento = str(raw_comprimento) if raw_comprimento not in (None, "") else ""

                # FF-HARDENING-013 Item 13A: per-SKU production metrics
                status_producao = safe_get_field(meta, "status_producao") or safe_get_field(item, "status_item", "")
                qtd_real_produzida = safe_get_field(meta, "qtd_real_produzida")
                qtd_real_str = str(qtd_real_produzida) if qtd_real_produzida not in (None, "") else ""
                perda_tecnica = safe_get_field(meta, "perda_tecnica")
                perda_str = str(perda_tecnica) if perda_tecnica not in (None, "") else ""

                # Código Estruturado — from extra_metadata (various key aliases from ONET import)
                codigo_estruturado = (
                    safe_get_field(meta, "codigo_estruturado")
                    or safe_get_field(meta, "cod_estruturado")
                    or safe_get_field(meta, "Código Estruturado")
                    or safe_get_field(meta, "codigo")
                    or safe_get_field(item, "codigo_estruturado")
                    or safe_get_field(item, "sku")
                    or ""
                )
                codigo_estruturado = str(codigo_estruturado) if codigo_estruturado else ""

                # Extract raw untouched ONET date from item metadata first
                raw_item_onet_date = (
                    safe_get_field(meta, "billing_date")
                    or safe_get_field(meta, "dt_faturamento")
                    or safe_get_field(meta, "Dt.Faturamento")
                    or safe_get_field(meta, "dt_entrega")
                    or safe_get_field(meta, "Dt.Entrega")
                )
                if raw_item_onet_date:
                    item_entrega_cliente = safe_format_date(raw_item_onet_date)
                else:
                    item_entrega_cliente = entrega_cliente

                item_sla_cols = [
                    etapa_atual,
                    sla_status_label,
                    elapsed_h_str,
                    sla_deadline_str,
                    overdue_h_str,
                    justificativa,
                    data_entrada,
                    item_entrega_cliente,
                    data_programada_pcp,
                    hours_in_stage_str,
                    tempo_pcp_str,
                    tempo_producao_str,
                    tempo_fatur_str,
                ]

                writer.writerow([
                    getattr(po, "po_number", ""),
                    item_client,
                    produto,
                    codigo_estruturado,
                    date_received,
                    unit,
                    qty_str,
                    personalizado,
                    largura,
                    comprimento,
                    status_producao,
                    qtd_real_str,
                    perda_str,
                    *item_sla_cols,
                ])
        except Exception as po_err:
            logger.error(f"Error processing PO {getattr(po, 'po_number', 'unknown')} in po-export: {po_err}")
            writer.writerow([
                getattr(po, "po_number", ""),
                getattr(po, "client_name", ""),
                "", "", "", "", "", "", "", "", "", "", "",
                _STATUS_TRANSLATION.get(getattr(po, "status_macro", ""), getattr(po, "status_macro", "")),
                "", "", "", "", "", "", "", "", "", "", ""
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

    sp_filter = get_salesperson_filter_name(current_user, db)
    if sp_filter:
        pos = filter_pos_by_salesperson(pos, sp_filter)

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
