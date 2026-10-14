"""A user's sign-ins (SEC-001): each person sees and ends their own; an administrator ends a user's sign-ins without ever
knowing their password. Ending one stops its access token at once; every ending is in the security log, and the user is
told when someone else ended theirs."""
from uuid import UUID

from app.core.security import active_sessions, describe_device, end_sessions
from app.foundation.application import notices
from app.foundation.application.security_log import TENANT_SESSIONS_ENDED, log_tenant_security


def view(sessions, current: str | None) -> list[dict]:
    return [dict(id=s["id"], device=describe_device(s["user_agent"]), ip_address=s["ip_address"], started_at=s["started_at"],
                 last_active_at=s["last_active_at"], current=str(s["id"]) == str(current)) for s in sessions]


class SessionService:
    def __init__(self, db, organization_id):
        self.db, self.org = db, organization_id

    def mine(self, user, current) -> list[dict]:
        return view(active_sessions(self.db, "tenant", user.id), current)

    def end_mine(self, user, family_ids, current) -> int:
        """Ends the user's own sign-ins (never the one making the request: that is signing out)."""
        own = {str(s["id"]) for s in active_sessions(self.db, "tenant", user.id)}
        ids = [f for f in family_ids if str(f) in own and str(f) != str(current)]
        ended = end_sessions(self.db, "tenant", user.id, ids, reason="ended_by_user")
        if ended:
            log_tenant_security(self.db, self.org, TENANT_SESSIONS_ENDED, user.id, user.email, details={"reason": "ended_by_user", "sessions": len(ids)})
        self.db.commit()
        return len(ids)

    def of_user(self, user_id: UUID) -> list[dict]:
        return view(active_sessions(self.db, "tenant", user_id), None)

    def end_all_of_user(self, user, actor) -> int:
        """An administrator ends every sign-in of a user (a lost phone, a leaver): they must sign in again."""
        ids = [s["id"] for s in active_sessions(self.db, "tenant", user.id)]
        end_sessions(self.db, "tenant", user.id, ids, reason="ended_by_admin")
        if ids:
            log_tenant_security(self.db, self.org, TENANT_SESSIONS_ENDED, user.id, user.email,
                                details={"reason": "ended_by_admin", "sessions": len(ids), "by": actor.full_name})
            notices.sessions_ended_by_admin(self.db, self.org, user.id, actor.id)
        self.db.commit()
        return len(ids)
