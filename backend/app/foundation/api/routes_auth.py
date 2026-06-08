from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies import CurrentUserContext, get_current_user, get_db
from app.foundation.api.schemas import CurrentUserResponse, LoginRequest, LoginResponse
from app.foundation.application.services import FoundationService


router = APIRouter(tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    service = FoundationService(db)
    response = service.login(payload)
    if response is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        )
    return response


@router.get("/me", response_model=CurrentUserResponse)
def me(current: CurrentUserContext = Depends(get_current_user)) -> CurrentUserResponse:
    return current.profile
