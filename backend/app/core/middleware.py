from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from uuid import uuid4
import re

from app.core.config import settings

_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        supplied = request.headers.get("x-request-id", "")
        request_id = supplied if _SAFE_REQUEST_ID.fullmatch(supplied) else str(uuid4())
        correlation = request.headers.get("x-correlation-id", "")
        request.state.request_id = request_id
        request.state.correlation_id = correlation if _SAFE_REQUEST_ID.fullmatch(correlation) else None
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


def register_middleware(app: FastAPI) -> None:
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
