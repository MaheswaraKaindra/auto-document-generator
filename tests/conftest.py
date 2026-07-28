"""Konfigurasi pytest bersama.

Tes HARUS hermetik terhadap `.env` pengembang. Contoh nyata yang melahirkan file
ini: begitu `.env` lokal diisi `SUPABASE_URL`, auth aktif saat app di-impor, dan
19 tes route yang tak mengirim token mendadak kena 401 — padahal tak ada kode
tes yang berubah. Lingkungan tes tak boleh menyetir hasil tes.
"""
import pytest

from app.core import config


@pytest.fixture(autouse=True)
def _disable_auth_by_default(monkeypatch):
    """Default: mode dev/anonymous (auth mati), lepas dari `.env` mesin ini.

    Tes yang MEMANG menguji auth menyetel `config.SUPABASE_URL` sendiri (mis. lewat
    monkeypatch di test_auth_service / helper _hs256_token) — setelan itu menang
    di dalam tes tersebut karena dijalankan SESUDAH fixture ini."""
    monkeypatch.setattr(config, "SUPABASE_URL", None)
    monkeypatch.setattr(config, "SUPABASE_JWT_SECRET", None)
