from datetime import timedelta
from decimal import Decimal
from sqlalchemy import func, select
from app.core.dashboard import Card, Dashboard, breakdown, card, count_by_day, as_day, window
from app.procurement.infrastructure.models import GoodsReceipt, PurchaseOrder, Supplier
from app.procurement.domain import permissions as P


def build_dashboard(db, tenant, can, period):
    w = window(period)
    board = Dashboard(module='procurement', period=period, start=w.start, end=w.end - timedelta(days=1))
    for model, permission, key, href, statuses in [
        (Supplier, P.SUPPLIERS_READ, 'approved_suppliers', '/suppliers', ('approved',)),
        (PurchaseOrder, P.PO_READ, 'open_purchase_orders', '/purchase-orders', ('draft', 'approved', 'sent', 'partially_received')),
        (GoodsReceipt, P.RECEIPTS_READ, 'draft_receipts', '/goods-receipts', ('draft',)),
    ]:
        if not can(permission):
            continue
        rows = db.execute(select(model.status, func.count(model.id)).where(model.organization_id == tenant.organization_id).group_by(model.status)).all()
        board.cards.append(Card(key=key, style='count', value=Decimal(sum(n for status, n in rows if status in statuses)), href=href))
        board.breakdowns.append(breakdown(key, rows, style='bars'))
    if can(P.RECEIPTS_READ):
        received = db.scalars(select(GoodsReceipt.received_at).where(GoodsReceipt.organization_id == tenant.organization_id,
            GoodsReceipt.status == 'received', GoodsReceipt.received_at >= w.at(w.previous_start), GoodsReceipt.received_at < w.at(w.end))).all()
        board.cards.append(card('received_receipts', w, count_by_day(as_day(day) for day in received), href='/goods-receipts'))
    return board
