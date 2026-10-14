"""Public system facts the screens need before anyone is signed in (setup, platform)."""
from fastapi import APIRouter

from app.core import files

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/file-policy")
def file_policy():
    """What each kind of upload accepts (PROJECT-FILES-003): types and sizes only, nothing about any organization."""
    return files.policy()
