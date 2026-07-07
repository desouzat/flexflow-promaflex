"""
FF-HARDENING-012.2 [Item 5]: Reports Router
GET /api/reports/po-export — Generates a downloadable CSV report of all
purchase orders for the authenticated user's tenant.

Security: All DB queries are strictly filtered by current_user.tenant_id
to prevent cross-tenant data leaks.
"""
import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

try:
    from backend.database import get_db
    from backend.models import PurchaseOrder, OrderItem
    from backend.routers.auth import get_current_user, UserInfo
except ModuleNotFoundError:
    from database import get_db
    from models import PurchaseOrder, OrderItem
    from routers.auth import get_current_user, UserInfo

router = APIRouter(prefix="/api/reports", tags=["Reports"])


@router.get("/po-export")
async def export_pos_csv(
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Export all purchase orders for the tenant as a CSV file.

    Columns (9):
        Nº PO | CLIENTE | PRODUTO | DATA RECEBIMENTO | UNIDADE MEDIDA |
        QTDE | PERSONALIZADO | LARGURA | COMPRIMENTO

    Security: Strictly filtered by current_user.tenant_id — no cross-tenant
    data can appear in the response.
    """
    # ── Fetch POs and items — tenant-scoped ─────────────────────────────────
    pos = (
        db.query(PurchaseOrder)
        .filter(PurchaseOrder.tenant_id == current_user.tenant_id)
        .order_by(PurchaseOrder.created_at.desc())
        .all()
    )

    # ── Build CSV in memory ──────────────────────────────────────────────────
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_MINIMAL)

    # Header row
    writer.writerow([
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
    ])

    for po in pos:
        # Client name — resolved from partition_metadata, po model column, or first-item metadata
        client_name = ""
        if po.partition_metadata and "client_name" in po.partition_metadata:
            client_name = po.partition_metadata["client_name"] or ""
        if not client_name:
            # Standard ONET POs store client_name directly on the PurchaseOrder row
            client_name = getattr(po, 'client_name', '') or ""
        if not client_name and po.items:
            # Manual exchange cards may store it in item metadata
            client_name = po.items[0].extra_metadata.get('client_name', '') if po.items[0].extra_metadata else ""

        # Date received (created_at formatted as dd/mm/yyyy)
        date_received = ""
        if po.created_at:
            date_received = po.created_at.strftime("%d/%m/%Y")

        if not po.items:
            # PO with no items — emit one row with blanks for item fields
            writer.writerow([
                po.po_number,
                client_name,
                "",
                date_received,
                "",
                "",
                "",
                "",
                "",
                "",  # STATUS PRODUÇÃO
                "",  # QTD REAL PRODUZIDA
                "",  # PERDA TÉCNICA
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

            # If client_name not in partition_metadata, try item metadata
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

            # Dimensions — ordered fallback chain for both PO types:
            # 1. Direct ORM columns item.width / item.length (standard ONET POs via import_service)
            # 2. JSONB extra_metadata keys: largura/Largura/width/Width
            # 3. Blank string if not found
            raw_largura = getattr(item, 'width', None) or getattr(item, 'largura', None)
            if raw_largura is None:
                raw_largura = (
                    meta.get("largura") or meta.get("Largura")
                    or meta.get("width") or meta.get("Width")
                )
            largura = str(raw_largura) if raw_largura not in (None, "") else ""

            raw_comprimento = getattr(item, 'length', None) or getattr(item, 'comprimento', None)
            if raw_comprimento is None:
                raw_comprimento = (
                    meta.get("comprimento") or meta.get("Comprimento")
                    or meta.get("length") or meta.get("Length")
                )
            comprimento = str(raw_comprimento) if raw_comprimento not in (None, "") else ""

            # FF-HARDENING-013 Item 13A: per-SKU production metrics from item.extra_metadata
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
            ])

    # ── Stream response with BOM for Excel UTF-8 compatibility ───────────────
    csv_content = "\ufeff" + output.getvalue()  # UTF-8 BOM for Excel
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


@router.get("/cancellations-export")
async def export_cancellations_csv(
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
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

    # ── Fetch only CANCELLED POs — tenant-scoped ─────────────────────────────
    pos = (
        db.query(PurchaseOrder)
        .filter(
            PurchaseOrder.tenant_id == current_user.tenant_id,
            PurchaseOrder.status_macro == "CANCELLED"
        )
        .order_by(PurchaseOrder.updated_at.desc())
        .all()
    )

    # ── Build CSV in memory ──────────────────────────────────────────────────
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
        # ── Resolve shared PO-level fields ───────────────────────────────────
        # client_name: uses the PO model @property (partition_metadata → item fallback)
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
            # sla_justification_at is stored as UTC in PostgreSQL
            utc_dt = po.sla_justification_at
            if utc_dt.tzinfo is None:
                # Naive datetime — treat as UTC
                from datetime import timezone
                utc_dt = utc_dt.replace(tzinfo=timezone.utc)
            sp_dt = utc_dt.astimezone(SP_TZ)
            cancelamento_str = sp_dt.strftime("%d/%m/%Y %H:%M:%S")

        if not po.items:
            # PO with no items — emit one row with blank item fields
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

            # SKU from OrderItem
            sku = item.sku or ""

            # Código estruturado from item.extra_metadata
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

    # ── Stream response with BOM for Excel UTF-8 compatibility ───────────────
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
