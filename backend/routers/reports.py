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
    ])

    for po in pos:
        # Client name — resolved from partition_metadata or item metadata
        client_name = ""
        if po.partition_metadata and "client_name" in po.partition_metadata:
            client_name = po.partition_metadata["client_name"] or ""

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

            # Dimensions
            largura = meta.get("largura") or meta.get("Largura") or ""
            comprimento = meta.get("comprimento") or meta.get("Comprimento") or ""

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
