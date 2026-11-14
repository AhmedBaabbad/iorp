"""Approval delegations and signatures (PROJECT-GOV-004). Foundation is the only writer of both tables.

- Holding a permission "through a role" means a role of the user grants it (or the user is the organization's root).
- A delegation is in force once agreed (domain/delegations.py), on the organization's date between its first and last
  day, while not revoked, while both users are active, and while its delegator still holds the permission through a
  role (checked when it is used).
- A delegated permission is added to the delegate's permissions for the time it is in force, so the existing checks
  (backend dependencies, the screens' buttons) apply it with nothing else to change.
- A signature records whose authority it was and who signed, when it is signed; the signer is always the session's user.
"""
from datetime import datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import aliased

from app.core.pagination import page_of, paginate

from app.core.interfaces.approvals import ApprovalAuthorityError
from app.core.numbering import organization_zone
from app.core.utils import utc_now
from app.foundation.application import notices
from app.foundation.application.audit import DELEGATION_APPROVED, DELEGATION_CREATED, DELEGATION_REJECTED, DELEGATION_REVOKED, log_tenant_audit
from app.foundation.domain import delegations as D
from app.foundation.domain.delegations import DelegationError
from app.foundation.domain.enums import UserStatus
from app.foundation.infrastructure.delegation_models import ApprovalDelegation, ApprovalRecord
from app.foundation.infrastructure.models import Permission, RolePermission, User, UserRole


def today(db, organization_id):
    return datetime.now(organization_zone(db, organization_id)).date()


def holds_by_role(db, user: User, code: str) -> bool:
    """The permission comes from one of the user's roles (or the user is the organization's root); never from a delegation."""
    if user.is_organization_root:
        return True
    return db.scalar(select(Permission.id).join(RolePermission, RolePermission.permission_id == Permission.id)
                     .join(UserRole, UserRole.role_id == RolePermission.role_id)
                     .where(UserRole.user_id == user.id, Permission.organization_id == user.organization_id, Permission.code == code)
                     .limit(1)) is not None


def _active(user: User | None) -> bool:
    return user is not None and user.status == UserStatus.ACTIVE and user.archived_at is None


def usable(db, delegation: ApprovalDelegation, on) -> bool:
    """In force on that date, both users active, and the delegator still holding the permission through a role."""
    if not D.in_force(delegation, on):
        return False
    delegator, delegate = db.get(User, delegation.delegator_user_id), db.get(User, delegation.delegate_user_id)
    return _active(delegator) and _active(delegate) and holds_by_role(db, delegator, delegation.permission_code)


def delegated_permissions(db, user: User) -> set[str]:
    """The permissions the user holds today by a delegation in force (added to the session's permissions)."""
    rows = db.scalars(select(ApprovalDelegation).where(ApprovalDelegation.organization_id == user.organization_id,
                                                       ApprovalDelegation.delegate_user_id == user.id,
                                                       ApprovalDelegation.revoked_at.is_(None))).all()
    if not rows:
        return set()
    on = today(db, user.organization_id)
    return {d.permission_code for d in rows if usable(db, d, on)}


class DelegationService:
    def __init__(self, db, tenant, permissions: frozenset[str] | set[str]):
        self.db, self.tenant, self.org = db, tenant, tenant.organization_id
        self.permissions = permissions  # the session's (from its roles, plus any delegation in force)

    @property
    def manages(self) -> bool:
        return self.tenant.is_organization_root or D.MANAGE in self.permissions

    @property
    def me(self) -> User:
        return self._user(self.tenant.user_id)

    def _user(self, user_id) -> User:
        user = self.db.scalar(select(User).where(User.id == user_id, User.organization_id == self.org))
        if user is None:
            raise DelegationError("USER_NOT_FOUND", 404)
        return user

    def _names(self, ids):
        ids = {i for i in ids if i}
        return dict(self.db.execute(select(User.id, User.full_name).where(User.organization_id == self.org, User.id.in_(ids))).all()) if ids else {}

    def _audit(self, action, d, **extra):
        names = self._people(d)
        log_tenant_audit(self.db, self.org, action, "delegation", d.id, self.tenant.user_id,
                         target_display=f"{names.get(d.delegator_user_id, '')} → {names.get(d.delegate_user_id, '')}",
                         details=dict(delegator=names.get(d.delegator_user_id), delegate=names.get(d.delegate_user_id), permission=d.permission_code,
                                      effective_from=str(d.effective_from), effective_to=str(d.effective_to), **{k: v for k, v in extra.items() if v}))

    def _people(self, d):
        return self._names([d.delegator_user_id, d.delegate_user_id])

    def own_delegable(self) -> list[str]:
        """The approvals this user holds through a role, and so may delegate (asking a manager to agree)."""
        me = self.me
        return [c for c in D.DELEGABLE if holds_by_role(self.db, me, c)]

    def _answerable(self, d, on) -> bool:
        """Is the session's user the one whose agreement this delegation waits for?"""
        if d.revoked_at is not None or on > d.effective_to:
            return False
        if d.approval == D.AWAITING_MANAGER:
            return self.manages and d.delegator_user_id != self.tenant.user_id
        return d.approval == D.AWAITING_HOLDER and d.delegator_user_id == self.tenant.user_id

    # reads
    def view(self, rows):
        names = self._names([u for d in rows for u in (d.delegator_user_id, d.delegate_user_id, d.created_by_user_id, d.revoked_by_user_id,
                                                        d.decided_by_user_id)])
        on = today(self.db, self.org)
        return [dict(id=d.id, delegator_user_id=d.delegator_user_id, delegator_name=names.get(d.delegator_user_id),
                     delegate_user_id=d.delegate_user_id, delegate_name=names.get(d.delegate_user_id), permission_code=d.permission_code,
                     effective_from=d.effective_from, effective_to=d.effective_to, reason=d.reason, status=D.status(d, on),
                     usable=usable(self.db, d, on), created_by_name=names.get(d.created_by_user_id), created_at=d.created_at,
                     decided_by_name=names.get(d.decided_by_user_id), decided_at=d.decided_at, decision_reason=d.decision_reason,
                     revoked_at=d.revoked_at, revoked_by_name=names.get(d.revoked_by_user_id), revoke_reason=d.revoke_reason,
                     can_answer=self._answerable(d, on),
                     can_revoke=d.revoked_at is None and d.approval != D.REJECTED and on <= d.effective_to
                     and (self.manages or d.delegator_user_id == self.tenant.user_id))
                for d in rows]

    def _visible(self):
        """Managers and readers: every delegation of the organization. Others: the ones they gave or received."""
        query = select(ApprovalDelegation).where(ApprovalDelegation.organization_id == self.org)
        if not (self.manages or D.READ in self.permissions):
            query = query.where(or_(ApprovalDelegation.delegator_user_id == self.tenant.user_id,
                                    ApprovalDelegation.delegate_user_id == self.tenant.user_id))
        return query

    def page(self, params, state: str | None = None, search: str | None = None):
        """One page of delegations, newest first, filtered by state (as shown) and by a person's name."""
        on = today(self.db, self.org)
        d = ApprovalDelegation
        waiting = d.approval.in_((D.AWAITING_MANAGER, D.AWAITING_HOLDER))
        live = and_(d.revoked_at.is_(None), d.approval == D.APPROVED)
        states = {
            "waiting": and_(d.revoked_at.is_(None), waiting, d.effective_to >= on),
            "lapsed": and_(d.revoked_at.is_(None), waiting, d.effective_to < on),
            "scheduled": and_(live, d.effective_from > on),
            "active": and_(live, d.effective_from <= on, d.effective_to >= on),
            "ended": and_(live, d.effective_to < on),
            "rejected": and_(d.revoked_at.is_(None), d.approval == D.REJECTED),
            "revoked": d.revoked_at.isnot(None),
        }
        query = self._visible()
        if state in states:
            query = query.where(states[state])
        if search and search.strip():
            giver, taker = aliased(User), aliased(User)
            like = f"%{search.strip()}%"
            query = (query.join(giver, giver.id == d.delegator_user_id).join(taker, taker.id == d.delegate_user_id)
                     .where(or_(giver.full_name.ilike(like), taker.full_name.ilike(like))))
        rows, total = paginate(self.db, query.order_by(d.created_at.desc(), d.id.desc()), params)
        return page_of(self.view(rows), total, params)

    def _waiting_query(self):
        on = today(self.db, self.org)
        query = select(ApprovalDelegation).where(ApprovalDelegation.organization_id == self.org, ApprovalDelegation.revoked_at.is_(None),
                                                 ApprovalDelegation.effective_to >= on)
        holder = and_(ApprovalDelegation.approval == D.AWAITING_HOLDER, ApprovalDelegation.delegator_user_id == self.tenant.user_id)
        if self.manages:
            manager = and_(ApprovalDelegation.approval == D.AWAITING_MANAGER, ApprovalDelegation.delegator_user_id != self.tenant.user_id)
            return query.where(or_(holder, manager))
        return query.where(holder)

    def waiting(self) -> dict:
        """What waits for this user's answer: the number on the menu and the list at the top of the page."""
        rows = list(self.db.scalars(self._waiting_query().order_by(ApprovalDelegation.created_at)))
        return dict(count=len(rows), items=self.view(rows))

    def options(self):
        """Holders: their own approvals. Managers: anyone's, on their behalf (the holder then agrees)."""
        users = list(self.db.scalars(select(User).where(User.organization_id == self.org, User.status == UserStatus.ACTIVE, User.archived_at.is_(None)).order_by(User.full_name)))
        delegators = [u for u in users if self.manages or u.id == self.tenant.user_id]
        return dict(delegators=[dict(id=u.id, name=u.full_name, permissions=held) for u in delegators
                                if (held := [c for c in D.DELEGABLE if holds_by_role(self.db, u, c)])],
                    delegates=[dict(id=u.id, name=u.full_name) for u in users], manages=self.manages)

    # writes
    def create(self, data):
        own = data.delegator_user_id == self.tenant.user_id
        if not own and not self.manages:
            raise DelegationError("DELEGATION_ONLY_OWN", 403)  # a holder delegates only their own approvals
        if data.permission_code not in D.DELEGABLE:
            raise DelegationError("PERMISSION_NOT_DELEGABLE")
        delegator, delegate = self._user(data.delegator_user_id), self._user(data.delegate_user_id)
        if delegator.id == delegate.id:
            raise DelegationError("DELEGATION_TO_SELF")
        if not (_active(delegator) and _active(delegate)):
            raise DelegationError("USER_NOT_ACTIVE")
        if not holds_by_role(self.db, delegator, data.permission_code):
            raise DelegationError("DELEGATOR_LACKS_PERMISSION")  # nor can a delegated approval be delegated again
        D.assert_period(data.effective_from, data.effective_to, today(self.db, self.org))
        # The other side agrees: a manager for a holder, the holder for a manager; at once when one person is both.
        approval = D.APPROVED if own and self.manages else D.AWAITING_MANAGER if own else D.AWAITING_HOLDER
        row = ApprovalDelegation(organization_id=self.org, delegator_user_id=delegator.id, delegate_user_id=delegate.id,
                                 permission_code=data.permission_code, effective_from=data.effective_from, effective_to=data.effective_to,
                                 reason=data.reason.strip(), created_by_user_id=self.tenant.user_id, approval=approval)
        if approval == D.APPROVED:
            row.decided_by_user_id, row.decided_at = self.tenant.user_id, utc_now()
        self.db.add(row)
        self.db.flush()
        notices.delegation_created(self.db, self.org, row, self._people(row), self.tenant.user_id)
        self._audit(DELEGATION_CREATED, row, approval=row.approval)
        self.db.commit()
        return self.view([row])[0]

    def _locked(self, delegation_id) -> ApprovalDelegation:
        row = self.db.scalar(select(ApprovalDelegation).where(ApprovalDelegation.id == delegation_id, ApprovalDelegation.organization_id == self.org)
                             .with_for_update())
        if row is None:
            raise DelegationError("DELEGATION_NOT_FOUND", 404)
        return row

    def answer(self, delegation_id, approve: bool, reason: str | None):
        row = self._locked(delegation_id)
        on = today(self.db, self.org)
        if row.approval not in (D.AWAITING_MANAGER, D.AWAITING_HOLDER) or row.revoked_at is not None:
            raise DelegationError("DELEGATION_NOT_AWAITING", 409)
        if on > row.effective_to:
            raise DelegationError("DELEGATION_LAPSED", 409)
        if not self._answerable(row, on):
            raise DelegationError("DELEGATION_NOT_YOURS_TO_ANSWER", 403)
        if not approve and not (reason or "").strip():
            raise DelegationError("REASON_REQUIRED")
        if approve and not holds_by_role(self.db, self._user(row.delegator_user_id), row.permission_code):
            raise DelegationError("DELEGATOR_LACKS_PERMISSION")
        row.approval = D.APPROVED if approve else D.REJECTED
        row.decided_by_user_id, row.decided_at, row.decision_reason = self.tenant.user_id, utc_now(), (reason or "").strip() or None
        notices.delegation_decided(self.db, self.org, row, self._people(row), self.tenant.user_id)
        self._audit(DELEGATION_APPROVED if approve else DELEGATION_REJECTED, row, reason=row.decision_reason)
        self.db.commit()
        return self.view([row])[0]

    def revoke(self, delegation_id, reason):
        row = self._locked(delegation_id)
        if not (self.manages or row.delegator_user_id == self.tenant.user_id):
            raise DelegationError("DELEGATION_FORBIDDEN", 403)
        if row.revoked_at is not None:
            raise DelegationError("DELEGATION_ALREADY_REVOKED", 409)
        row.revoked_at, row.revoked_by_user_id, row.revoke_reason = utc_now(), self.tenant.user_id, reason.strip()
        notices.delegation_revoked(self.db, self.org, row, self._people(row), self.tenant.user_id)
        self._audit(DELEGATION_REVOKED, row, reason=row.revoke_reason)
        self.db.commit()
        return self.view([row])[0]


class FoundationApprovals:
    """core/interfaces/approvals.py: the record of every signed step."""

    def record(self, db, tenant, resource_type, resource_id, step, permission_code, notes=None):
        signer = db.scalar(select(User).where(User.id == tenant.user_id, User.organization_id == tenant.organization_id))
        if not _active(signer):
            raise ApprovalAuthorityError("SIGNER_NOT_ACTIVE")
        authority, delegation = signer, None
        if not holds_by_role(db, signer, permission_code):
            on = today(db, tenant.organization_id)
            candidates = db.scalars(select(ApprovalDelegation).where(
                ApprovalDelegation.organization_id == tenant.organization_id, ApprovalDelegation.delegate_user_id == signer.id,
                ApprovalDelegation.permission_code == permission_code, ApprovalDelegation.revoked_at.is_(None))
                .order_by(ApprovalDelegation.created_at)).all()
            delegation = next((d for d in candidates if usable(db, d, on)), None)
            if delegation is not None:
                authority = db.get(User, delegation.delegator_user_id)
            elif permission_code not in (tenant.permissions or ()):
                raise ApprovalAuthorityError("NO_AUTHORITY")  # neither a role, nor a delegation in force, nor the session grants it
        row = ApprovalRecord(organization_id=tenant.organization_id, resource_type=resource_type, resource_id=resource_id, step=step,
                             permission_code=permission_code, authority_user_id=authority.id, signed_by_user_id=signer.id,
                             delegation_id=delegation.id if delegation else None, authority_name=authority.full_name,
                             signer_name=signer.full_name, notes=notes)
        db.add(row)
        return dict(step=step, authority_name=authority.full_name, signer_name=signer.full_name, delegated=delegation is not None)

    def signatures(self, db, organization_id, resource_type, resource_ids):
        out = {i: [] for i in resource_ids}
        if not resource_ids:
            return out
        for r in db.scalars(select(ApprovalRecord).where(ApprovalRecord.organization_id == organization_id,
                                                         ApprovalRecord.resource_type == resource_type, ApprovalRecord.resource_id.in_(resource_ids))
                            .order_by(ApprovalRecord.signed_at, ApprovalRecord.id)):
            out.setdefault(r.resource_id, []).append(dict(step=r.step, authority_name=r.authority_name, signer_name=r.signer_name,
                                                          delegated=r.delegation_id is not None, delegation_id=r.delegation_id,
                                                          signed_at=r.signed_at, notes=r.notes))
        return out
