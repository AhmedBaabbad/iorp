"""COMPLAINTS-001, third step: the shorter flow (ISO 10002).

- The "assessment" stage is gone: assigning an owner is the initial assessment and starts the processing. A complaint
  still in assessment moves to processing (the history keeps the entries that took it there).
- waiting_reason is dropped: what a complaint waits for is a follow-up. A non-empty value is kept as a follow-up entry.
- A complaint links a sales order, a shipment, a return or a non-conformance report; a sample is a line's
  specification source, and production orders and inspections are reached through the quality report. Links of the
  other kinds are refused here rather than dropped: none exist (the module is not released).
"""
import json
import uuid

from alembic import op
import sqlalchemy as sa

revision = "f6a1b2n3"
down_revision = "f6a1b2n2"
branch_labels = None
depends_on = None

KEPT_LINKS = ("order", "shipment", "return", "ncr")


def upgrade():
    bind = op.get_bind()
    other = bind.execute(sa.text("SELECT count(*) FROM commercial_complaint_links WHERE kind NOT IN :kinds")
                         .bindparams(sa.bindparam("kinds", expanding=True)), dict(kinds=list(KEPT_LINKS))).scalar()
    if other:
        raise RuntimeError(f"{other} complaint link(s) of a kind no longer linkable; review them before upgrading")
    moved = bind.execute(sa.text("UPDATE commercial_complaints SET status = 'processing' WHERE status = 'assessment'")).rowcount
    kept = 0
    for cid, org, actor, text in bind.execute(sa.text(
            "SELECT id, organization_id, coalesce(owner_user_id, created_by), waiting_reason FROM commercial_complaints WHERE coalesce(waiting_reason, '') <> ''")).all():
        bind.execute(sa.text("INSERT INTO commercial_complaint_events (id, organization_id, complaint_id, actor_id, action, notes, details, created_at) "
                             "VALUES (:i, :o, :c, :a, 'note', :n, :d, CURRENT_TIMESTAMP)"),
                     dict(i=uuid.uuid4(), o=org, c=cid, a=actor, n=text, d=json.dumps({})))
        kept += 1
    with op.batch_alter_table("commercial_complaints") as batch:
        batch.drop_column("waiting_reason")
    print(f"commercial_complaints: {moved} moved from assessment to processing; {kept} waiting reason(s) kept as follow-ups")


def downgrade():
    with op.batch_alter_table("commercial_complaints") as batch:
        batch.add_column(sa.Column("waiting_reason", sa.Text()))
