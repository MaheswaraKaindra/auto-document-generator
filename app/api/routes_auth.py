import secrets

from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from app.domain.exceptions import SourceAuthError
from app.services.github_oauth_service import build_authorize_url, exchange_code_for_token

router = APIRouter(prefix="/auth/github", tags=["auth"])

# Placeholder CSRF-state store. There's no session/user system in this codebase yet -
# replace with real server-side session storage before this goes anywhere near production.
_pending_states: set[str] = set()


@router.get("/login")
def login():
    state = secrets.token_urlsafe(16)
    _pending_states.add(state)
    try:
        authorize_url = build_authorize_url(state)
    except SourceAuthError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return RedirectResponse(authorize_url)


@router.get("/callback")
def callback(code: str, state: str):
    if state not in _pending_states:
        raise HTTPException(status_code=400, detail="Invalid or expired state")
    _pending_states.discard(state)

    try:
        access_token = exchange_code_for_token(code)
    except SourceAuthError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # Placeholder response shape: returns the raw GitHub token directly because there's no
    # session/user system yet. Do not ship this to a browser-facing frontend as-is - a real
    # implementation should set its own session cookie/JWT here instead of exposing the token.
    return {"access_token": access_token}
