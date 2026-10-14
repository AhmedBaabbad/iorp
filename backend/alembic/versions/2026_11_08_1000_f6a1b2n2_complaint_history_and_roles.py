"""COMPLAINTS-001, second step: a readable history, the three values of each property, numbering, and the approved roles.

- commercial_complaint_events.details: each decision's facts by name (department, owner, dates, statuses, references);
  `notes` keeps only what the person wrote. Existing entries are converted from their combined text (e.g.
  "commercial; <id>; 2026-10-12: reason" becomes department, owner, due date and the reason).
- commercial_complaint_item_properties: one row per property with the agreed, reported and measured values (from the
  item's JSON column, which is then dropped). Items gain the confirmed affected quantity and the source of the agreed
  specification (a sales order line, a sample, or typed by hand).
- commercial_complaint_code_counters: CC-<year>-0001 numbering. Existing complaints keep their numbers.
- Roles (approved): organization administrator and commercial manager all complaint permissions; sales representative read (own customers), create,
  update; quality manager read, investigate, resolve; viewer read. Each grant added is recorded for the downgrade.
"""
import json
import re
import uuid

from alembic import op
import sqlalchemy as sa

revision = "f6a1b2n2"
down_revision = "f6a1b2n1"
branch_labels = None
depends_on = None

TRANSITIONS = ("assess", "start", "request_close", "approve_close", "return", "reopen", "cancel")
GRANTS = {
    # The organization administrator holds every permission (as every earlier permission migration grants it).
    "organization_admin": {a: "organization" for a in ("read", "create", "update", "assign", "investigate", "resolve", "close", "reopen", "cancel", "report")},
    "commercial_manager": {a: "organization" for a in ("read", "create", "update", "assign", "investigate", "resolve", "close", "reopen", "cancel", "report")},
    "sales_rep": {"read": "own", "create": "organization", "update": "organization"},
    "quality_manager": {"read": "organization", "investigate": "organization", "resolve": "organization"},
    "viewer": {"read": "organization"},
}
ADDED = "rbac_n2_added_grants"


def _details(action, notes, statement):
    """(details, notes) from an entry written as one text."""
    notes = notes or ""
    if action == "assign":
        m = re.match(r"^(\w+); ([0-9a-fA-F-]{36}); (\d{4}-\d{2}-\d{2}): (.*)$", notes, re.S)
        if m:
            return dict(department=m[1], owner_user_id=m[2], due_date=m[3]), m[4]
    if action in TRANSITIONS:
        m = re.match(r"^(\w+) → (\w+): (.*)$", notes, re.S)
        if m:
            return dict(from_status=m[1], to_status=m[2]), m[3]
    if action in ("investigate", "resolve"):
        fields = {}
        for block in notes.split("\n\n"):
            key, _, value = block.partition(": ")
            if key in ("finding", "investigation", "containment", "waiting_reason", "resolution", "implementation_evidence", "customer_response"):
                fields[key] = value
        if fields:
            finding = fields.pop("finding", None)
            return ({"finding": finding} if finding else {}) | {"fields": fields}, ""
    if action == "linked" and ": " in notes:
        kind, _, label = notes.partition(": ")
        return dict(kind=kind, label=label), ""
    if action == "refer_quality" and ": " in notes:
        number, _, rest = notes.partition(": ")
        return dict(ncr_number=number), rest
    if action == "attachment":
        return dict(filename=notes), ""
    if action == "created" and notes == statement:
        return {}, ""  # the statement is the complaint's own field
    return {}, notes


def _notes(action, details, notes, statement):
    """The old combined text, for the downgrade."""
    d = details or {}
    if action == "assign" and d.get("department"):
        return f'{d["department"]}; {d.get("owner_user_id", "")}; {d.get("due_date", "")}: {notes}'
    if action in TRANSITIONS and d.get("from_status"):
        return f'{d["from_status"]} → {d["to_status"]}: {notes}'
    if action in ("investigate", "resolve") and d.get("fields"):
        parts = ({"finding": d["finding"]} if d.get("finding") else {}) | d["fields"]
        return "\n\n".join(f"{k}: {v}" for k, v in parts.items())
    if action == "linked" and d.get("kind"):
        return f'{d["kind"]}: {d.get("label", "")}'
    if action == "refer_quality" and d.get("ncr_number"):
        return f'{d["ncr_number"]}: {notes}'
    if action == "attachment" and d.get("filename"):
        return d["filename"]
    if action == "created" and not notes:
        return statement
    return notes


def upgrade():
    bind = op.get_bind()
    # ── history ──────────────────────────────────────────────────────────────────────────────────
    op.add_column("commercial_complaint_events", sa.Column("details", sa.JSON(), nullable=True))
    rows = bind.execute(sa.text("SELECT e.id, e.action, e.notes, c.statement FROM commercial_complaint_events e "
                                "JOIN commercial_complaints c ON c.id = e.complaint_id")).all()
    converted = 0
    for event_id, action, notes, statement in rows:
        details, rest = _details(action, notes, statement)
        if details or rest != notes:
            converted += 1
        bind.execute(sa.text("UPDATE commercial_complaint_events SET details = :d, notes = :n WHERE id = :i"),
                     dict(d=json.dumps(details, ensure_ascii=False), n=rest, i=event_id))
    with op.batch_alter_table("commercial_complaint_events") as batch:
        batch.alter_column("details", existing_type=sa.JSON(), nullable=False)
    print(f"commercial_complaint_events: {converted} of {len(rows)} entr(ies) turned into named facts")

    # ── items and their properties ───────────────────────────────────────────────────────────────
    with op.batch_alter_table("commercial_complaint_items") as batch:
        batch.add_column(sa.Column("line_no", sa.Integer(), nullable=False, server_default="1"))
        batch.add_column(sa.Column("confirmed_quantity", sa.Numeric(15, 3)))
        batch.add_column(sa.Column("source_kind", sa.String(16), nullable=False, server_default="manual"))
        batch.add_column(sa.Column("source_id", sa.Uuid()))
        batch.add_column(sa.Column("source_label", sa.String(120)))
        batch.create_check_constraint("ck_complaint_confirmed", "confirmed_quantity IS NULL OR (confirmed_quantity >= 0 AND confirmed_quantity <= delivered_quantity)")
        batch.create_check_constraint("ck_complaint_item_source", "source_kind IN ('order', 'sample', 'manual')")
    op.create_table(
        "commercial_complaint_item_properties",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("foundation_organizations.id"), nullable=False),
        sa.Column("item_id", sa.Uuid(), sa.ForeignKey("commercial_complaint_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(120), nullable=False),
        sa.Column("name_ar", sa.String(255), nullable=False),
        sa.Column("name_en", sa.String(255), nullable=False),
        sa.Column("unit", sa.String(32)),
        sa.Column("expected", sa.String(1000), nullable=False),
        sa.Column("reported", sa.String(1000), nullable=False),
        sa.Column("measured", sa.String(1000), nullable=False),
        sa.UniqueConstraint("item_id", "key", name="uq_complaint_item_property"),
    )
    op.create_index("ix_commercial_complaint_item_properties_item_id", "commercial_complaint_item_properties", ["item_id"])
    op.create_index("ix_commercial_complaint_item_properties_organization_id", "commercial_complaint_item_properties", ["organization_id"])
    moved = 0
    for item_id, org, raw in bind.execute(sa.text("SELECT id, organization_id, properties FROM commercial_complaint_items")).all():
        values = raw if isinstance(raw, list) else json.loads(raw or "[]")
        for n, p in enumerate(values, 1):
            bind.execute(sa.text("INSERT INTO commercial_complaint_item_properties (id, organization_id, item_id, line_no, key, name_ar, name_en, unit, "
                                 "expected, reported, measured) VALUES (:id, :o, :i, :n, :k, :ar, :en, :u, :e, :r, '')"),
                         dict(id=uuid.uuid4(), o=org, i=item_id, n=n, k=p.get("key", ""), ar=p.get("name_ar") or p.get("key", ""),
                              en=p.get("name_en") or p.get("key", ""), u=p.get("unit"), e=p.get("expected", ""), r=p.get("reported", "")))
            moved += 1
    with op.batch_alter_table("commercial_complaint_items") as batch:
        batch.drop_column("properties")
    print(f"commercial_complaint_item_properties: {moved} propert(ies) moved from JSON")

    op.create_table("commercial_complaint_code_counters",
                    sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("foundation_organizations.id"), primary_key=True),
                    sa.Column("year", sa.Integer(), primary_key=True),
                    sa.Column("last_value", sa.Integer(), nullable=False))

    # ── the approved roles ───────────────────────────────────────────────────────────────────────
    op.create_table(ADDED, sa.Column("id", sa.Uuid(), primary_key=True))
    granted = 0
    for org, role_id, code in bind.execute(sa.text("SELECT organization_id, id, code FROM foundation_roles WHERE is_system = :t AND code IN :codes")
                                           .bindparams(sa.bindparam("codes", expanding=True)), dict(t=True, codes=list(GRANTS))).all():
        for action, scope in GRANTS[code].items():
            permission = bind.execute(sa.text("SELECT id FROM foundation_permissions WHERE organization_id = :o AND code = :c"),
                                      dict(o=org, c=f"commercial:complaints:{action}")).scalar()
            if permission is None or bind.execute(sa.text("SELECT 1 FROM foundation_role_permissions WHERE role_id = :r AND permission_id = :p"),
                                                  dict(r=role_id, p=permission)).first():
                continue
            grant = uuid.uuid4()
            bind.execute(sa.text("INSERT INTO foundation_role_permissions (id, role_id, permission_id, scope) VALUES (:g, :r, :p, :s)"),
                         dict(g=grant, r=role_id, p=permission, s=scope))
            bind.execute(sa.text(f"INSERT INTO {ADDED} (id) VALUES (:g)"), dict(g=grant))
            granted += 1
    print(f"roles: {granted} complaint permission grant(s) added to the approved system roles")


def downgrade():
    bind = op.get_bind()
    bind.execute(sa.text(f"DELETE FROM foundation_role_permissions WHERE id IN (SELECT id FROM {ADDED})"))
    op.drop_table(ADDED)
    op.drop_table("commercial_complaint_code_counters")
    with op.batch_alter_table("commercial_complaint_items") as batch:
        batch.add_column(sa.Column("properties", sa.JSON(), nullable=True))
    by_item = {}
    for item_id, key, ar, en, unit, expected, reported in bind.execute(sa.text(
            "SELECT item_id, key, name_ar, name_en, unit, expected, reported FROM commercial_complaint_item_properties ORDER BY line_no")).all():
        by_item.setdefault(item_id, []).append(dict(key=key, expected=expected, reported=reported, name_ar=ar, name_en=en, unit=unit))
    for (item_id,) in bind.execute(sa.text("SELECT id FROM commercial_complaint_items")).all():
        bind.execute(sa.text("UPDATE commercial_complaint_items SET properties = :p WHERE id = :i"),
                     dict(p=json.dumps(by_item.get(item_id, []), ensure_ascii=False), i=item_id))
    op.drop_table("commercial_complaint_item_properties")
    with op.batch_alter_table("commercial_complaint_items") as batch:
        batch.alter_column("properties", existing_type=sa.JSON(), nullable=False)
        batch.drop_constraint("ck_complaint_item_source", type_="check")
        batch.drop_constraint("ck_complaint_confirmed", type_="check")
        for column in ("source_label", "source_id", "source_kind", "confirmed_quantity", "line_no"):
            batch.drop_column(column)
    for event_id, action, notes, details, statement in bind.execute(sa.text(
            "SELECT e.id, e.action, e.notes, e.details, c.statement FROM commercial_complaint_events e JOIN commercial_complaints c ON c.id = e.complaint_id")).all():
        d = details if isinstance(details, dict) else json.loads(details or "{}")
        bind.execute(sa.text("UPDATE commercial_complaint_events SET notes = :n WHERE id = :i"), dict(n=_notes(action, d, notes, statement), i=event_id))
    with op.batch_alter_table("commercial_complaint_events") as batch:
        batch.drop_column("details")
