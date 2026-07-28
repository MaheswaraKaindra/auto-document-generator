"""Identitas pengguna — SATU seam auth untuk seluruh aplikasi.

Filosofi: "pasang auth" harus HARFIAH tinggal mengisi env, bukan mengubah kode.
Karena itu seluruh keputusan auth terkumpul di sini, dan sisa aplikasi cuma
bergantung pada `Principal` (siapa pemanggilnya) — bukan pada Supabase, JWT, atau
provider apa pun. Ganti Supabase ke Auth0/Cognito kelak = ganti isi `verify_token`,
tak menyentuh route mana pun.

DUA MODE, dipilih dari env (bukan flag terpisah yang bisa lupa disetel):
- **SUPABASE_URL kosong → ANONYMOUS/dev.** Aplikasi jalan penuh tanpa login;
  semua pemanggil jadi satu `Principal` anonim. Ini yang membuat repo tetap bisa
  dikerjakan & dites $0 tanpa akun Supabase, DAN membuat perilaku lama (sebelum
  auth ada) terjaga persis.
- **SUPABASE_URL terisi → auth AKTIF.** Frontend login ke Supabase, mengirim JWT
  di header `Authorization: Bearer`; di sini token diverifikasi dan `sub`-nya jadi
  identitas pemilik data.

Verifikasi menerima DUA jenis penandatanganan Supabase tanpa konfigurasi tambahan:
- **HS256** (JWT Secret simetris, project lama) bila `SUPABASE_JWT_SECRET` diisi;
- **ES256/RS256** (signing key asimetris, project baru) lewat JWKS yang diturunkan
  dari `SUPABASE_URL` — tak perlu menaruh secret apa pun di backend.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import jwt
from jwt import PyJWKClient

from app.core import config

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Principal:
    """Siapa yang memanggil. `id` dipakai sebagai pemilik data (kolom owner)."""
    id: str
    email: str | None
    is_anonymous: bool


# Satu instance dibagikan untuk mode dev — id stabil supaya job yang dibuat saat
# anonymous tetap bisa diunduh oleh pemanggil anonim berikutnya (owner cocok).
ANONYMOUS = Principal(id="anonymous", email=None, is_anonymous=True)


class AuthError(Exception):
    """Token wajib tapi tak ada / tak sah. Dipetakan ke HTTP 401 di boundary."""


def auth_enabled() -> bool:
    """True kalau isolasi per-pengguna aktif. Dibaca saat dipanggil (bukan
    di-cache) supaya test bisa menyetel `config.SUPABASE_URL` per-kasus."""
    return bool(config.SUPABASE_URL)


def _base_url() -> str:
    """Base URL project, dinormalkan. Dashboard Supabase menampilkan beberapa
    bentuk (kadang berakhiran `/rest/v1/`), sementara JWKS ada di `/auth/v1/...`.
    Memangkas ekor yang umum salah-tempel supaya konfigurasi tak rapuh."""
    url = (config.SUPABASE_URL or "").strip().rstrip("/")
    for suffix in ("/rest/v1", "/auth/v1"):
        if url.endswith(suffix):
            url = url[: -len(suffix)]
    return url


# JWKS client di-cache per-URL: PyJWKClient menyimpan & memutar kunci sendiri,
# jadi cukup satu instance per project — bikin ulang tiap request berarti satu
# fetch jaringan tiap request.
_jwks_clients: dict[str, PyJWKClient] = {}


def _jwks_client(base_url: str) -> PyJWKClient:
    client = _jwks_clients.get(base_url)
    if client is None:
        client = PyJWKClient(f"{base_url}/auth/v1/.well-known/jwks.json")
        _jwks_clients[base_url] = client
    return client


def verify_token(token: str) -> Principal:
    """JWT Supabase → `Principal`. Melempar `AuthError` kalau tak sah.

    Prakondisi: `auth_enabled()` True (ada yang memverifikasi). Memilih jalur
    HS256 vs asimetris dari ADA-TIDAKNYA `SUPABASE_JWT_SECRET` — bukan dari
    menebak `alg` di header token (yang bisa dipalsukan penyerang; menerima `alg`
    dari token adalah kelas kerentanan "alg confusion" yang terkenal).
    """
    options = {"require": ["sub"]}
    common = {"audience": config.SUPABASE_JWT_AUD, "options": options}
    try:
        if config.SUPABASE_JWT_SECRET:
            claims = jwt.decode(token, config.SUPABASE_JWT_SECRET,
                                algorithms=["HS256"], **common)
        else:
            signing_key = _jwks_client(_base_url()).get_signing_key_from_jwt(token)
            claims = jwt.decode(token, signing_key.key,
                                algorithms=["ES256", "RS256"], **common)
    except (jwt.InvalidTokenError, jwt.PyJWKClientError) as e:
        # Sebab spesifik ke log (kadaluarsa vs audience salah vs tanda tangan),
        # pesan generik ke pemanggil — jangan bocorkan detail kripto ke luar.
        logger.info("JWT ditolak: %s", e)
        raise AuthError("Token tidak sah atau kadaluarsa.") from e

    return Principal(id=str(claims["sub"]),
                     email=claims.get("email"),
                     is_anonymous=False)


def principal_from_header(authorization: str | None) -> Principal:
    """Header `Authorization` → `Principal`. Inti logika `get_current_user`,
    dipisah dari FastAPI supaya bisa dites tanpa merakit request HTTP.

    - Auth non-aktif (dev)         → ANONYMOUS, header diabaikan.
    - Auth aktif, tak ada Bearer   → AuthError (401).
    - Auth aktif, Bearer ada       → verifikasi.
    """
    if not auth_enabled():
        return ANONYMOUS
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthError("Header Authorization: Bearer <token> wajib.")
    return verify_token(authorization[7:].strip())


def owns(resource_owner: str | None, caller: Principal) -> bool:
    """Boleh mengakses resource ini?

    - `resource_owner` None → job lama / dibuat saat dev sebelum auth aktif:
      IZINKAN (kompatibilitas mundur; tak ada pemilik untuk dilanggar).
    - selain itu → hanya kalau pemilik == pemanggil.
    """
    return resource_owner is None or resource_owner == caller.id
