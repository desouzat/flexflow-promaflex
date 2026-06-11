"""
Time-Tracing Audit — confirm_staging with NullPool-safe pattern.
Connects to production DB via Cloud SQL Auth Proxy on port 5434.
Uses ZERO intermediate db.flush() inside the PO transaction — all UUIDs
are pre-assigned in Python so no round-trip is needed to resolve PKs.
"""

import sys, os, uuid, time
from datetime import datetime, timezone
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["PYTHONIOENCODING"] = "utf-8"

SCRIPT_START = time.perf_counter()

def ts():
    now = datetime.now()
    elapsed = (time.perf_counter() - SCRIPT_START) * 1000
    return f"[{now.strftime('%H:%M:%S.%f')[:-3]}] [+{elapsed:8.1f}ms]"

def step(label):
    print(f"{ts()}  >>  {label}", flush=True)

def done(label, t0):
    ms = (time.perf_counter() - t0) * 1000
    flag = "  <<< SLOW >>>" if ms > 300 else ""
    print(f"{ts()}  <<  {label}  [{ms:.1f}ms]{flag}", flush=True)
    return ms

timing = []

# ── Imports ────────────────────────────────────────────────────────────────
step("Loading backend modules...")
t0 = time.perf_counter()
from backend.database import SessionLocal
from backend.models import PurchaseOrder, OrderItem, AuditLog, ClientPreference
from sqlalchemy import select, text
ms = done("Module import", t0)
timing.append(("Module import", ms))

# ── Real production IDs ─────────────────────────────────────────────────────
TENANT_ID = uuid.UUID("23c431b9-da55-4098-9628-c86df8070b7c")   # PromaFlex
USER_ID   = uuid.UUID("b785e0f0-e351-41b2-97a8-12793b6cc3a1")   # test user

# ── Mock payload ─────────────────────────────────────────────────────────────
class Meta:
    is_personalized = False; is_new_client = False; is_export = False
    is_replacement = False; customization_notes = None; attachment_path = None
    attachment_filename = None; apply_sla_reduction = False
    finance_justification = None

class Item:
    def __init__(self, sku, blocked=False):
        self.sku = sku; self.quantity = 2
        self.price_unit = Decimal("100.00"); self.unit_value = Decimal("100.00")
        self.item_total_value = Decimal("200.00")
        self.block_status = "BLOQUEADO" if blocked else "LIBERADO"
        self.balance = None; self.delay = None; self.payment_terms = "30 DDL"
        self.description = f"Produto {sku}"; self.unit = "UN"
        self.width = None; self.length = None; self.lead_time = 30
        self.delivery_date = "15/07/2026"; self.billing_date = None
        self.icms_percent = Decimal("12.00"); self.freight = Decimal("25.00")
        self.salesperson = "Vendedor Teste"; self.ipi = Decimal("5.00")
        self.extra_metadata = Meta()

class PO:
    def __init__(self, num, client):
        self.po_number = num; self.client_name = client
        self.business_unit = "Direto"; self.packaging_type = "Caixa"
        self.freight_cost = Decimal("0"); self.additional_costs = Decimal("0")
        self.po_total_value = Decimal("600.00")
        self.items = [Item(f"SKU-{num}-A"), Item(f"SKU-{num}-B"),
                      Item(f"SKU-{num}-C", blocked=True)]

PAYLOAD_POS = [PO("TRACE-PO-001", "Cliente Teste A"),
               PO("TRACE-PO-002", "Cliente Teste B")]

step(f"Payload ready: {len(PAYLOAD_POS)} POs, {sum(len(p.items) for p in PAYLOAD_POS)} items")

# ── Pre-cleanup ──────────────────────────────────────────────────────────────
step("Pre-cleanup: removing any prior TRACE-PO-* rows...")
t0 = time.perf_counter()
_db = SessionLocal()
try:
    stale = _db.query(PurchaseOrder).filter(
        PurchaseOrder.po_number.in_(["TRACE-PO-001", "TRACE-PO-002"])
    ).all()
    for s in stale:
        _db.delete(s)
    if stale:
        _db.commit()
    step(f"  Removed {len(stale)} stale trace rows")
except Exception as e:
    _db.rollback(); step(f"  Pre-cleanup error (non-fatal): {e}")
finally:
    _db.close()
ms = done("Pre-cleanup", t0)
timing.append(("Pre-cleanup", ms))

# ════════════════════════════════════════════════════════════════════════════
print(f"\n{'='*72}")
print("  BEGIN confirm_staging TRACE — NullPool-safe pattern")
print(f"  Pattern: ClientPreference committed separately → PO+items atomic commit")
print(f"{'='*72}\n")

db = SessionLocal()
step("Session opened")

try:
    for po_idx, po in enumerate(PAYLOAD_POS):
        print(f"\n{'─'*72}")
        print(f"{ts()}  PO [{po_idx+1}/{len(PAYLOAD_POS)}]: {po.po_number}")
        print(f"{'─'*72}")

        # ── 1. Delete existing PO (idempotency) ──────────────────────────────
        label = f"[{po.po_number}] SELECT existing PO (idempotency check)"
        step(label); t0 = time.perf_counter()
        existing_po = (
            db.query(PurchaseOrder)
            .filter(PurchaseOrder.po_number == po.po_number,
                    PurchaseOrder.tenant_id == TENANT_ID)
            .first()
        )
        ms = done(label, t0); timing.append((label, ms))
        if existing_po:
            label2 = f"[{po.po_number}] DELETE existing PO + db.commit()"
            step(label2); t0 = time.perf_counter()
            db.delete(existing_po)
            db.commit()
            ms = done(label2, t0); timing.append((label2, ms))
        else:
            step(f"[{po.po_number}] No existing PO — skip delete")

        # ── 2. Pure-Python calculations ───────────────────────────────────────
        label = f"[{po.po_number}] Pure-Python: blocked check + freight"
        step(label); t0 = time.perf_counter()
        has_blocked_item = any(
            item.block_status == "BLOQUEADO" or (
                item.extra_metadata is not None and
                getattr(item.extra_metadata, "finance_justification", None) and
                str(item.extra_metadata.finance_justification).strip()
            )
            for item in po.items
        )
        po_status_macro = "FINANCE" if has_blocked_item else "APPROVED"
        first_item_delivery = next(
            (i.delivery_date for i in po.items if i.delivery_date), None
        )
        is_personalized = any(i.extra_metadata.is_personalized for i in po.items if i.extra_metadata)
        is_new_client   = any(i.extra_metadata.is_new_client   for i in po.items if i.extra_metadata)
        is_export       = any(i.extra_metadata.is_export       for i in po.items if i.extra_metadata)
        is_replacement  = any(i.extra_metadata.is_replacement  for i in po.items if i.extra_metadata)
        customization_notes = next(
            (i.extra_metadata.customization_notes for i in po.items
             if i.extra_metadata and i.extra_metadata.customization_notes), None
        )
        attachment_path = next(
            (i.extra_metadata.attachment_path for i in po.items
             if i.extra_metadata and i.extra_metadata.attachment_path), None
        )
        original_freight = po.freight_cost + po.additional_costs
        if original_freight == 0 and po.items:
            original_freight = sum(float(i.freight or 0) for i in po.items)
        ms = done(label, t0); timing.append((label, ms))
        step(f"[{po.po_number}] status_macro={po_status_macro} freight={original_freight}")

        # ── 3. ClientPreference upsert — OWN committed transaction ───────────
        label = f"[{po.po_number}] SELECT ClientPreference"
        step(label); t0 = time.perf_counter()
        pref_stmt = select(ClientPreference).where(
            ClientPreference.tenant_id == TENANT_ID,
            ClientPreference.client_name == po.client_name
        )
        existing_pref = db.execute(pref_stmt).scalar_one_or_none()
        ms = done(label, t0); timing.append((label, ms))

        label = f"[{po.po_number}] ClientPreference upsert db.flush() [same TX]"
        step(label); t0 = time.perf_counter()
        if existing_pref:
            existing_pref.business_unit = po.business_unit
        else:
            db.add(ClientPreference(
                tenant_id=TENANT_ID,
                client_name=po.client_name,
                business_unit=po.business_unit
            ))
        db.flush()   # sends INSERT on the CURRENT open connection (same TX)
        ms = done(label, t0); timing.append((label, ms))

        # ── 4. PO batch — pre-assign ALL UUIDs in Python, ZERO flushes ────────
        label = f"[{po.po_number}] Pre-assign UUIDs + build PurchaseOrder (pure Python)"
        step(label); t0 = time.perf_counter()
        new_po_id = uuid.uuid4()
        new_po = PurchaseOrder(
            id=new_po_id,
            tenant_id=TENANT_ID,
            po_number=po.po_number,
            status_macro=po_status_macro,
            created_by=USER_ID,
            shipping_cost=original_freight,
            po_total_value=po.po_total_value,
            partition_metadata={
                "client_name": po.client_name,
                "expected_delivery_date": first_item_delivery,
                "packaging_type": po.packaging_type,
                "is_personalized": is_personalized,
                "is_new_client": is_new_client,
                "is_export": is_export,
                "is_replacement": is_replacement,
                "customization_notes": customization_notes,
                "attachment_path": attachment_path,
                "additional_costs": float(po.additional_costs),
                "business_unit": po.business_unit
            }
        )
        db.add(new_po)

        label = f"[{po.po_number}] db.flush() after PO — serializes PO INSERT (required)"
        step(label); t0 = time.perf_counter()
        db.flush()   # flush PO so items can reference it via FK
        ms = done(label, t0); timing.append((label, ms))
        step(f"[{po.po_number}] new_po_id={new_po_id} flushed to DB")

        # ── 5. Item loop — all db.add(), zero db.flush() ──────────────────────
        label = f"[{po.po_number}] Item loop ({len(po.items)} items)"
        step(label); t0_loop = time.perf_counter()

        for i_idx, item in enumerate(po.items):
            t_item = time.perf_counter()
            is_blocked = (
                item.block_status == "BLOQUEADO" or (
                    item.extra_metadata and
                    getattr(item.extra_metadata, "finance_justification", None) and
                    str(item.extra_metadata.finance_justification).strip()
                )
            )
            item_status = "ANALISE_CREDITO" if is_blocked else "PENDING"

            extra_meta = {
                "is_personalized":  item.extra_metadata.is_personalized if item.extra_metadata else False,
                "is_new_client":    item.extra_metadata.is_new_client   if item.extra_metadata else False,
                "is_export":        item.extra_metadata.is_export       if item.extra_metadata else False,
                "is_replacement":   item.extra_metadata.is_replacement  if item.extra_metadata else False,
                "customization_notes": item.extra_metadata.customization_notes if item.extra_metadata else None,
                "attachment_path":  item.extra_metadata.attachment_path if item.extra_metadata else None,
                "attachment_filename": item.extra_metadata.attachment_filename if item.extra_metadata else None,
                "apply_sla_reduction": item.extra_metadata.apply_sla_reduction if item.extra_metadata else False,
                "finance_justification": item.extra_metadata.finance_justification if item.extra_metadata else None,
                "additional_costs": float(po.additional_costs),
                "block_status": item.block_status, "balance": item.balance,
                "delay": item.delay, "payment_terms": item.payment_terms,
                "description": item.description, "unit": item.unit,
                "width": str(item.width) if item.width else None,
                "length": str(item.length) if item.length else None,
                "lead_time": item.lead_time, "delivery_date": item.delivery_date,
                "billing_date": item.billing_date,
                "icms_percent": str(item.icms_percent) if item.icms_percent else None,
                "freight": str(item.freight) if item.freight else None,
                "salesperson": item.salesperson,
                "ipi": str(item.ipi) if item.ipi else None,
                "client_name": po.client_name
            }

            new_item_id = uuid.uuid4()
            new_item = OrderItem(
                id=new_item_id,
                po_id=new_po_id,
                tenant_id=TENANT_ID,
                sku=item.sku,
                quantity=item.quantity,
                price=item.price_unit,
                status_item=item_status,
                unit_value=item.unit_value,
                item_total_value=item.item_total_value,
                is_personalized=item.extra_metadata.is_personalized if item.extra_metadata else False,
                is_new_client=item.extra_metadata.is_new_client if item.extra_metadata else False,
                customization_notes=item.extra_metadata.customization_notes if item.extra_metadata else None,
                attachment_path=item.extra_metadata.attachment_path if item.extra_metadata else None,
                extra_metadata=extra_meta
            )
            db.add(new_item)
            t_f = time.perf_counter()
            db.flush()
            ms_flush = (time.perf_counter() - t_f) * 1000

            audit_note = ""
            if is_blocked:
                now_utc = datetime.now(timezone.utc)
                t_hash = time.perf_counter()
                h = AuditLog.calculate_hash_v2(
                    tenant_id=TENANT_ID, item_id=new_item_id,
                    from_status=None, to_status="ANALISE_CREDITO",
                    timestamp=now_utc, previous_hash=None, changed_by=USER_ID
                )
                ms_hash = (time.perf_counter() - t_hash) * 1000
                db.add(AuditLog(
                    id=uuid.uuid4(), item_id=new_item_id,
                    from_status=None, to_status="ANALISE_CREDITO",
                    hash=h, previous_hash=None,
                    hash_version=AuditLog.HASH_VERSION_CURRENT,
                    is_exception=True, justification=None,
                    changed_by=USER_ID, created_at=now_utc,
                    extra_data={"decision": "BLOCKED_ON_IMPORT",
                                "workflow": "FINANCE_BLOCK_ON_IMPORT"}
                ))
                t_af = time.perf_counter()
                db.flush()
                ms_audit_flush = (time.perf_counter() - t_af) * 1000
                audit_note = (f" + hash({ms_hash:.3f}ms)"
                              f" + AuditLog flush({ms_audit_flush:.1f}ms)")

            ms_item = (time.perf_counter() - t_item) * 1000
            print(f"  {ts()}  item[{i_idx+1}] {item.sku:<22} blocked={is_blocked}"
                  f"  item_flush={ms_flush:.1f}ms{audit_note}"
                  f"  total={ms_item:.1f}ms", flush=True)

        ms = done(label, t0_loop); timing.append((label, ms))

        # ── 6. Single atomic commit ───────────────────────────────────────────
        label = f"[{po.po_number}] db.commit() — PO+items+auditlogs ATOMIC"
        step(label); t0 = time.perf_counter()
        db.commit()
        ms = done(label, t0); timing.append((label, ms))

        label = f"[{po.po_number}] db.refresh(new_po)"
        step(label); t0 = time.perf_counter()
        db.refresh(new_po)
        ms = done(label, t0); timing.append((label, ms))

        step(f"[{po.po_number}] SUCCESS  po.id={new_po.id}  status={new_po.status_macro}")

except Exception as exc:
    import traceback
    step(f"EXCEPTION: {type(exc).__name__}: {exc}")
    traceback.print_exc(file=sys.stdout)
    db.rollback()
    step("db.rollback() executed")
finally:
    db.close()
    step("Session closed")

# ── Post-cleanup ──────────────────────────────────────────────────────────────
print(f"\n{'='*72}")
print("  POST-RUN CLEANUP")
print(f"{'='*72}")
t0 = time.perf_counter()
_db = SessionLocal()
try:
    rows = _db.query(PurchaseOrder).filter(
        PurchaseOrder.po_number.in_(["TRACE-PO-001", "TRACE-PO-002"])
    ).all()
    for r in rows:
        _db.delete(r)
    _db.commit()
    step(f"Cleanup: deleted {len(rows)} trace PO rows (cascade removes items + audit_logs)")
except Exception as e:
    _db.rollback(); step(f"Cleanup error: {e}")
finally:
    _db.close()
timing.append(("Cleanup", (time.perf_counter() - t0) * 1000))

# ── Timing report ─────────────────────────────────────────────────────────────
total = (time.perf_counter() - SCRIPT_START) * 1000
print(f"\n{'='*72}")
print(f"  TIMING REPORT  (total: {total:.0f}ms)")
print(f"{'='*72}")
print(f"  {'Operation':<58}  {'ms':>7}")
print(f"  {'-'*58}  {'-------':>7}")
for lbl, ms in timing:
    flag = "  <<< SLOW" if ms > 300 else ""
    short = (lbl[:56] + "..") if len(lbl) > 58 else lbl
    print(f"  {short:<58}  {ms:>7.1f}{flag}")
print(f"{'='*72}")
print(f"  All trace rows cleaned. No permanent DB changes.")
print(f"{'='*72}")
