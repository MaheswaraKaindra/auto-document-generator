"""Dependency FastAPI bersama antar-router.

`get_current_user` adalah SATU titik tempat HTTP bertemu auth: ia menerjemahkan
header `Authorization` jadi `Principal`, dan `AuthError` jadi HTTP 401. Route
tinggal `principal: Principal = Depends(get_current_user)` tanpa tahu Supabase/JWT.

Dependency rate limit di bawahnya mengikuti pola yang sama: kebijakannya di
`rate_limit_service` (tak tahu HTTP), penerjemahannya jadi 429 + `Retry-After`
cuma di sini. Route memakainya sebagai PENGGANTI `get_current_user` — jadi batas
kuota terlihat di tanda tangan fungsi endpoint-nya, bukan tersembunyi di tengah
badan fungsi.
"""
from fastapi import Depends, Header, HTTPException

from app.core import config
from app.services import auth_service, rate_limit_service
from app.services.auth_service import Principal
from app.services.rate_limit_service import RateLimitDecision


def get_current_user(authorization: str | None = Header(default=None)) -> Principal:
    """Pemanggil saat ini. Mode dev (SUPABASE_URL kosong) → selalu ANONYMOUS;
    mode aktif → verifikasi JWT, 401 kalau tak ada/tak sah."""
    try:
        return auth_service.principal_from_header(authorization)
    except auth_service.AuthError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e


def _humanize_seconds(seconds: int) -> str:
    """"~12 menit" / "~45 detik" — angka yang bisa dipakai orang untuk memutuskan
    menunggu atau pergi. "Coba lagi dalam 731 detik" memaksa pembacanya membagi."""
    if seconds < 90:
        return f"~{seconds} detik"
    return f"~{round(seconds / 60)} menit"


def _enforce(decision: RateLimitDecision, activity: str) -> None:
    """Keputusan kuota → 429 + `Retry-After`, atau lewat begitu saja.

    429 (bukan 403): ini kegagalan SEMENTARA yang boleh diulang — pemisahan
    permanen vs sementara yang sama seperti `error_status` pada job. `Retry-After`
    dalam DETIK (bentuk yang dipahami klien HTTP & proxy), sementara pesannya
    memakai satuan manusia; keduanya menyebut angka yang sama.
    """
    if decision.allowed:
        return
    window_minutes = round(config.RATE_LIMIT_WINDOW_SECONDS / 60)
    raise HTTPException(
        status_code=429,
        detail=(
            f"Batas pemakaian tercapai: {decision.limit} {activity} per "
            f"{window_minutes} menit untuk akun ini. "
            f"Coba lagi dalam {_humanize_seconds(decision.retry_after_seconds)}."
        ),
        headers={"Retry-After": str(decision.retry_after_seconds)},
    )


def rate_limited_generate(
    principal: Principal = Depends(get_current_user),
) -> Principal:
    """Pemanggil, SESUDAH kuota generate diperiksa. 429 kalau habis.

    Diperiksa sebelum apa pun yang lain di endpoint, dan itu disengaja: yang
    memakan kuota adalah job yang BERHASIL DIBUAT, jadi request yang salah bentuk
    tak pernah mengurangi jatah siapa pun — dan pemanggil yang kuotanya habis tak
    perlu diberi tahu hasil validasi request yang tak akan dikerjakan.
    """
    _enforce(rate_limit_service.check_generate(principal), "generate dokumen")
    return principal


def rate_limited_template_upload(
    principal: Principal = Depends(get_current_user),
) -> Principal:
    """Pemanggil, SESUDAH kuota upload template diperiksa. 429 kalau habis."""
    _enforce(rate_limit_service.check_template_upload(principal), "upload template")
    return principal
