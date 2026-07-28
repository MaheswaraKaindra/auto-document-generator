"""Dependency FastAPI bersama antar-router.

`get_current_user` adalah SATU titik tempat HTTP bertemu auth: ia menerjemahkan
header `Authorization` jadi `Principal`, dan `AuthError` jadi HTTP 401. Route
tinggal `principal: Principal = Depends(get_current_user)` tanpa tahu Supabase/JWT.
"""
from fastapi import Header, HTTPException

from app.services import auth_service
from app.services.auth_service import Principal


def get_current_user(authorization: str | None = Header(default=None)) -> Principal:
    """Pemanggil saat ini. Mode dev (SUPABASE_URL kosong) → selalu ANONYMOUS;
    mode aktif → verifikasi JWT, 401 kalau tak ada/tak sah."""
    try:
        return auth_service.principal_from_header(authorization)
    except auth_service.AuthError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
