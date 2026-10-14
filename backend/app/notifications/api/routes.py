"""Notifications (PROJECT-NOTIFY-001): every user's own inbox (no permission needed: one reads only one's own) and the
announcements written by holders of notifications:announcements:send."""
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.pagination import PageParams, page_params
from app.dependencies import CurrentUserContext, get_current_user, get_db, require_any_permission, require_permission
from app.notifications.application.service import AnnouncementService, InboxService
from app.notifications.domain import permissions as P
from app.notifications.domain import rules as R
from app.notifications.domain.rules import NotificationError

router = APIRouter(prefix="/notifications", tags=["notifications"])
announcements = APIRouter(prefix="/announcements", tags=["announcements"])
SENDS = require_any_permission([P.ANNOUNCEMENTS_SEND, P.ANNOUNCEMENTS_MANAGE])


def _run(fn):
    try:
        return fn()
    except NotificationError as exc:
        raise HTTPException(exc.status_code, detail=exc.code) from exc


def _inbox(current: CurrentUserContext, db: Session) -> InboxService:
    return InboxService(db, current.tenant)


@router.get("")
def inbox(kind: str = Query("all", pattern="^(" + "|".join(R.FILTERS) + ")$"), params: PageParams = Depends(page_params),
          current: CurrentUserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    """One page of the user's notifications, newest first (ARCH-PAGE-001)."""
    return _inbox(current, db).page(params, kind)


@router.get("/summary")
def summary(current: CurrentUserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    """The bell: unread count, the latest few, and announcements awaiting acknowledgement."""
    return _inbox(current, db).summary()


@router.post("/read-all")
def read_all(current: CurrentUserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return _inbox(current, db).read_all()


@router.post("/{item_id}/read")
def read(item_id: UUID, current: CurrentUserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return _run(lambda: _inbox(current, db).read(item_id))


@router.post("/hide-read")
def hide_read(current: CurrentUserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return _inbox(current, db).hide_read()


@router.post("/{item_id}/hide")
def hide(item_id: UUID, current: CurrentUserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return _run(lambda: _inbox(current, db).hide(item_id))


@router.post("/{item_id}/acknowledge")
def acknowledge(item_id: UUID, current: CurrentUserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return _run(lambda: _inbox(current, db).acknowledge(item_id))


class AnnouncementCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=R.TITLE_MAX)
    body: str = Field(min_length=1, max_length=R.BODY_MAX)
    severity: str = Field("info", pattern="^(info|important|urgent)$")
    requires_ack: bool = False
    audience: str = Field(pattern="^(users|role|everyone)$")
    user_ids: list[UUID] = Field(default_factory=list, max_length=500)
    role_id: UUID | None = None
    expires_at: datetime | None = None


def _announcements(current: CurrentUserContext, db: Session) -> AnnouncementService:
    return AnnouncementService(db, current.tenant, current.auth_user.permissions)


@announcements.get("")
def announcement_list(search: str | None = Query(None, max_length=120), state: str | None = Query(None, pattern="^(live|expired|withdrawn)$"),
                      params: PageParams = Depends(page_params),
                      current: CurrentUserContext = Depends(SENDS), db: Session = Depends(get_db)):
    """The announcements the user sent (all of them for a manager), with how many read and acknowledged."""
    return _announcements(current, db).page(params, search, state)


@announcements.get("/options")
def announcement_options(current: CurrentUserContext = Depends(require_permission(P.ANNOUNCEMENTS_SEND)), db: Session = Depends(get_db)):
    return _announcements(current, db).options()


@announcements.post("", status_code=201)
def announcement_create(body: AnnouncementCreate, current: CurrentUserContext = Depends(require_permission(P.ANNOUNCEMENTS_SEND)),
                        db: Session = Depends(get_db)):
    return _run(lambda: _announcements(current, db).create(body))


@announcements.get("/{announcement_id}")
def announcement_detail(announcement_id: UUID, current: CurrentUserContext = Depends(SENDS), db: Session = Depends(get_db)):
    return _run(lambda: _announcements(current, db).detail(announcement_id))


@announcements.post("/{announcement_id}/withdraw")
def announcement_withdraw(announcement_id: UUID, current: CurrentUserContext = Depends(SENDS), db: Session = Depends(get_db)):
    return _run(lambda: _announcements(current, db).withdraw(announcement_id))
