"""What foundation tells people (PROJECT-NOTIFY-001), through core/interfaces/notifications: their access (roles given or
removed, a role's permissions changed), their account's security, and approval delegations. Each notice is added to the
session of the change it reports, and committed with it."""
from app.core.interfaces.notifications import ACCESS, DELEGATION, IMPORTANT, SECURITY, Audience, Notice, notify, settle
from app.foundation.domain import delegations as D

PROFILE = "/admin/profile"
DELEGATIONS = "/admin/delegations"


def role_assigned(db, organization_id, user_id, role, actor_id):
    notify(db, organization_id, Audience.to(user_id), Notice("foundation.role.assigned", ACCESS, dict(role=role.name), PROFILE, IMPORTANT), actor_id)


def role_removed(db, organization_id, user_id, role, actor_id):
    notify(db, organization_id, Audience.to(user_id), Notice("foundation.role.removed", ACCESS, dict(role=role.name), PROFILE, IMPORTANT), actor_id)


def role_permissions_changed(db, organization_id, role, actor_id):
    """To the role's members; several changes in a row make one notice while it is unread."""
    notify(db, organization_id, Audience(role_id=role.id),
           Notice("foundation.role.permissions_changed", ACCESS, dict(role=role.name), PROFILE, resource_type="role", resource_id=role.id), actor_id)


def password_reset(db, organization_id, user_id, actor_id):
    notify(db, organization_id, Audience.to(user_id), Notice("foundation.user.password_reset", SECURITY, {}, PROFILE, IMPORTANT), actor_id)


def account_unlocked(db, organization_id, user_id, actor_id):
    notify(db, organization_id, Audience.to(user_id), Notice("foundation.user.unlocked", SECURITY, {}, PROFILE), actor_id)


def _delegation_params(delegation, names):
    return dict(delegator=names.get(delegation.delegator_user_id, ""), delegate=names.get(delegation.delegate_user_id, ""),
                permission=delegation.permission_code, start=delegation.effective_from, end=delegation.effective_to)


def _notice(event, delegation, names, severity="info"):
    return Notice(event, DELEGATION, _delegation_params(delegation, names), DELEGATIONS, severity,
                  resource_type="delegation", resource_id=delegation.id)


def delegation_created(db, organization_id, delegation, names, actor_id):
    """Asks the side whose agreement it waits for; once in force, tells the delegate."""
    if delegation.approval == D.AWAITING_MANAGER:
        notify(db, organization_id, Audience.holders(D.MANAGE, exclude=(delegation.delegator_user_id,)),
               _notice("foundation.delegation.awaiting_manager", delegation, names, IMPORTANT), actor_id)
    elif delegation.approval == D.AWAITING_HOLDER:
        notify(db, organization_id, Audience.to(delegation.delegator_user_id),
               _notice("foundation.delegation.awaiting_holder", delegation, names, IMPORTANT), actor_id)
    else:
        delegation_decided(db, organization_id, delegation, names, actor_id)


def delegation_decided(db, organization_id, delegation, names, actor_id):
    """The request is answered: those still asked have nothing left to do; the people concerned are told the answer."""
    settle(db, organization_id, "delegation", delegation.id)
    approved = delegation.approval == D.APPROVED
    notify(db, organization_id, Audience.to(delegation.delegator_user_id, delegation.created_by_user_id),
           _notice("foundation.delegation.approved" if approved else "foundation.delegation.rejected", delegation, names), actor_id)
    if approved:
        notify(db, organization_id, Audience.to(delegation.delegate_user_id),
               _notice("foundation.delegation.granted", delegation, names, IMPORTANT), actor_id)


def delegation_revoked(db, organization_id, delegation, names, actor_id):
    settle(db, organization_id, "delegation", delegation.id)
    notify(db, organization_id, Audience.to(delegation.delegator_user_id, delegation.delegate_user_id),
           _notice("foundation.delegation.revoked", delegation, names, IMPORTANT), actor_id)


# SEC-001: sessions
def new_device(db, organization_id, user_id, device, ip):
    """A sign-in from a browser this user never signed in from: they are told, in case it was not them."""
    notify(db, organization_id, Audience.to(user_id, include_actor=True),
           Notice("foundation.user.new_device", SECURITY, dict(device=device, ip=ip or "—"), "/admin/sessions", IMPORTANT), None)


def sessions_ended_by_limit(db, organization_id, user_id, count, limit):
    notify(db, organization_id, Audience.to(user_id, include_actor=True),
           Notice("foundation.user.session_limit", SECURITY, dict(count=count, limit=limit), "/admin/sessions"), None)


def sessions_ended_by_admin(db, organization_id, user_id, actor_id):
    notify(db, organization_id, Audience.to(user_id), Notice("foundation.user.sessions_ended", SECURITY, {}, None, IMPORTANT), actor_id)
