"""Tes seam auth (`auth_service`). JWT ditandatangani LOKAL dengan HS256 —
deterministik, tanpa jaringan, tanpa akun Supabase. Jalur JWKS asimetris sengaja
tak dites di sini (butuh mock endpoint jaringan); yang diuji adalah kontrak yang
dipakai route: siapa pemanggilnya & apa yang ditolak."""
import time

import jwt
import pytest

from app.core import config
from app.services import auth_service


@pytest.fixture
def supabase_hs256(monkeypatch):
    """Aktifkan mode auth dengan JWT secret simetris (project Supabase lama)."""
    monkeypatch.setattr(config, "SUPABASE_URL", "https://proj.supabase.co")
    monkeypatch.setattr(config, "SUPABASE_JWT_SECRET", "rahasia-super-panjang-minimal-tiga-puluh-dua-byte")
    monkeypatch.setattr(config, "SUPABASE_JWT_AUD", "authenticated")
    return "rahasia-super-panjang-minimal-tiga-puluh-dua-byte"


def _token(secret, *, sub="user-123", aud="authenticated", email="a@b.com", exp_delta=3600):
    payload = {"sub": sub, "aud": aud, "email": email,
               "exp": int(time.time()) + exp_delta}
    return jwt.encode(payload, secret, algorithm="HS256")


def test_mode_dev_selalu_anonymous_tanpa_supabase(monkeypatch):
    """SUPABASE_URL kosong = aplikasi jalan penuh tanpa login. Ini yang menjaga
    perilaku lama (sebelum auth) DAN membuat repo tetap bisa dites $0."""
    monkeypatch.setattr(config, "SUPABASE_URL", None)

    p = auth_service.principal_from_header("Bearer apa-pun-diabaikan")

    assert p is auth_service.ANONYMOUS
    assert p.is_anonymous is True
    assert auth_service.auth_enabled() is False


def test_token_sah_jadi_principal(supabase_hs256):
    p = auth_service.principal_from_header(f"Bearer {_token(supabase_hs256)}")

    assert p.id == "user-123"
    assert p.email == "a@b.com"
    assert p.is_anonymous is False


def test_auth_aktif_tanpa_header_ditolak(supabase_hs256):
    with pytest.raises(auth_service.AuthError):
        auth_service.principal_from_header(None)


def test_token_kadaluarsa_ditolak(supabase_hs256):
    expired = _token(supabase_hs256, exp_delta=-10)
    with pytest.raises(auth_service.AuthError):
        auth_service.principal_from_header(f"Bearer {expired}")


def test_tanda_tangan_salah_ditolak(supabase_hs256):
    palsu = _token("secret-yang-salah-tapi-cukup-panjang-32byte")
    with pytest.raises(auth_service.AuthError):
        auth_service.principal_from_header(f"Bearer {palsu}")


def test_audience_salah_ditolak(supabase_hs256):
    """Token untuk audience lain (mis. service role) tak boleh lolos sebagai user."""
    salah_aud = _token(supabase_hs256, aud="bukan-authenticated")
    with pytest.raises(auth_service.AuthError):
        auth_service.principal_from_header(f"Bearer {salah_aud}")


def test_alg_tak_ditebak_dari_token(supabase_hs256):
    """Token tanpa tanda tangan (alg=none) harus ditolak — kelas kerentanan
    'alg confusion'. Jalur HS256 dipilih dari ADANYA secret, bukan dari header token."""
    tak_bertanda = jwt.encode({"sub": "x", "aud": "authenticated"}, key=None, algorithm="none")
    with pytest.raises(auth_service.AuthError):
        auth_service.principal_from_header(f"Bearer {tak_bertanda}")


def test_owns_mengizinkan_owner_none_dan_pemilik_yang_sama():
    caller = auth_service.Principal(id="u1", email=None, is_anonymous=False)
    # None = job lama / dibuat saat dev sebelum auth aktif — tak ada pemilik untuk
    # dilanggar, jadi diizinkan (kompatibilitas mundur).
    assert auth_service.owns(None, caller) is True
    assert auth_service.owns("u1", caller) is True
    assert auth_service.owns("u2", caller) is False


def test_base_url_dinormalkan_dari_salah_tempel(monkeypatch):
    """Dashboard kadang memberi URL berakhiran /rest/v1/. JWKS ada di /auth/v1/,
    jadi ekor yang umum salah-tempel dipangkas supaya konfigurasi tak rapuh."""
    from app.services.auth_service import _base_url
    for masuk in ("https://p.supabase.co",
                  "https://p.supabase.co/",
                  "https://p.supabase.co/rest/v1/",
                  "https://p.supabase.co/auth/v1"):
        monkeypatch.setattr(config, "SUPABASE_URL", masuk)
        assert _base_url() == "https://p.supabase.co"
