"""Tes kebijakan rate limit per-akun (`rate_limit_service`).

Sengaja menguji lewat `check_generate`/`check_template_upload` — bukan cuma
matematika jendelanya — supaya PENGHITUNGNYA ikut terkunci: kuota dihitung dari
baris `jobs` & manifest template yang benar-benar tersimpan, dan itulah yang
membuatnya benar lintas-worker & tahan restart. Menguji `_decide` sendirian akan
hijau walau penghitungnya menghitung akun yang salah.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.core import config
from app.services import compiler_service, job_store, rate_limit_service
from app.services.auth_service import ANONYMOUS, Principal
from app.services.rate_limit_service import _decide

ALICE = Principal(id="alice", email="alice@contoh.id", is_anonymous=False)
BOB = Principal(id="bob", email="bob@contoh.id", is_anonymous=False)


@pytest.fixture(autouse=True)
def isolated_stores(tmp_path, monkeypatch):
    """DB job & store template ke tmp — jangan sentuh data/ pengembang."""
    monkeypatch.setattr(job_store, "DB_PATH", tmp_path / "jobs.db")
    monkeypatch.setattr(compiler_service, "TEMPLATES_STORE", tmp_path / "templates")
    job_store.init_db()


@pytest.fixture(autouse=True)
def auth_on(monkeypatch):
    """Batas per-akun cuma berlaku saat auth aktif (mode dev sengaja dilewati),
    jadi mayoritas tes di sini butuh auth menyala."""
    monkeypatch.setattr(config, "SUPABASE_URL", "https://proj.supabase.co")


@pytest.fixture(autouse=True)
def small_limits(monkeypatch):
    monkeypatch.setattr(config, "RATE_LIMIT_GENERATE_PER_WINDOW", 3)
    monkeypatch.setattr(config, "RATE_LIMIT_TEMPLATE_UPLOAD_PER_WINDOW", 2)
    monkeypatch.setattr(config, "RATE_LIMIT_WINDOW_SECONDS", 3600)


def _jobs(owner, count):
    for _ in range(count):
        job_store.create_job(document_type="SDD", project_name=None, owner=owner)


def test_batas_menggigit_tepat_di_permintaan_ke_n_plus_1():
    _jobs("alice", 2)
    keputusan = rate_limit_service.check_generate(ALICE)
    assert keputusan.allowed and keputusan.remaining == 1

    _jobs("alice", 1)                       # sekarang 3 = batas
    keputusan = rate_limit_service.check_generate(ALICE)
    assert not keputusan.allowed
    assert keputusan.limit == 3 and keputusan.remaining == 0
    assert 0 < keputusan.retry_after_seconds <= 3600


def test_batas_per_akun_bukan_global():
    """Akun lain tak boleh ikut terhukum — kalau ini gagal, satu pengguna berisik
    mematikan layanan untuk semua orang (dan itu bukan rate limit, itu bug)."""
    _jobs("alice", 5)
    assert not rate_limit_service.check_generate(ALICE).allowed
    assert rate_limit_service.check_generate(BOB).allowed


def test_jendela_sliding_melepas_kuota_setelah_lewat():
    """Bukan reset di jam bulat: kuota longgar tepat ketika permintaan tertua
    keluar dari jendela, dihitung dari waktu permintaan itu sendiri."""
    _jobs("alice", 3)
    assert not rate_limit_service.check_generate(ALICE).allowed

    nanti = datetime.now(timezone.utc) + timedelta(seconds=3601)
    assert rate_limit_service.check_generate(ALICE, now=nanti).allowed


def test_retry_after_menunjuk_saat_kuota_benar_benar_longgar():
    """Retry-After yang kependekan mengundang 429 kedua; yang kepanjangan menahan
    pengguna lebih lama dari perlunya. Diuji dengan waktu yang dikendalikan."""
    sekarang = datetime(2026, 7, 28, 12, 0, 0, tzinfo=timezone.utc)
    # Tiga permintaan: 50, 30, dan 10 menit lalu. Batas 3, jendela 60 menit.
    times = [sekarang - timedelta(minutes=m) for m in (10, 30, 50)]

    keputusan = _decide(times, limit=3, window_seconds=3600, now=sekarang)

    assert not keputusan.allowed
    # Yang harus kedaluwarsa adalah yang TERTUA (50 menit lalu) → 10 menit lagi.
    assert keputusan.retry_after_seconds == 600


def test_limit_nol_mematikan_batas():
    """Escape hatch yang jujur: instance internal satu tim tak butuh kuota, dan
    mematikannya lewat env lebih terang daripada menyetel angka raksasa."""
    _jobs("alice", 50)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(config, "RATE_LIMIT_GENERATE_PER_WINDOW", 0)
        assert rate_limit_service.check_generate(ALICE).allowed


def test_mode_dev_auth_mati_tak_dibatasi(monkeypatch):
    """SUPABASE_URL kosong = semua pemanggil satu Principal anonim yang sama, jadi
    "per-akun" tak punya arti — yang tersisa cuma batas global yang akan
    menghentikan sesi dev/demo di tengah jalan. Mode dev harus tetap jalan penuh."""
    monkeypatch.setattr(config, "SUPABASE_URL", None)
    _jobs(None, 50)
    assert rate_limit_service.check_generate(ANONYMOUS).allowed


def test_job_lama_di_luar_jendela_tak_ikut_dihitung(monkeypatch):
    """Kuota menghitung PERMINTAAN DALAM JENDELA, bukan seluruh riwayat akun —
    kalau tidak, akun lama akan terkunci permanen."""
    lampau = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    monkeypatch.setattr(job_store, "_now", lambda: lampau)
    _jobs("alice", 10)
    monkeypatch.undo()

    assert rate_limit_service.check_generate(ALICE).allowed


def test_env_batas_yang_salah_ketik_menggagalkan_startup(monkeypatch):
    """Batas salah-ketik tak boleh diam-diam jatuh ke default: yang dikira "batas
    10/jam" bisa jadi tanpa batas sama sekali, dan itu baru ketahuan lewat tagihan."""
    from app.core.config import _int_env

    monkeypatch.setenv("RL_UJI", "sepuluh")
    with pytest.raises(ValueError, match="bilangan bulat"):
        _int_env("RL_UJI", 10)

    monkeypatch.setenv("RL_UJI", "-5")
    with pytest.raises(ValueError, match="negatif"):
        _int_env("RL_UJI", 10)

    monkeypatch.setenv("RL_UJI", "  7 ")        # spasi di sekitar angka tetap sah
    assert _int_env("RL_UJI", 10) == 7
    monkeypatch.setenv("RL_UJI", "")            # kosong = pakai default
    assert _int_env("RL_UJI", 10) == 10


def test_upload_template_dihitung_dari_manifest_tersimpan():
    """Penghitung kedua: manifest `data/templates/<id>/template.json` yang sudah
    membawa `owner` + `created_at`. Tanpa store baru, tanpa dependency baru."""
    spec = {"outline": [{"level": 1, "text": "Deskripsi Aplikasi"}],
            "doc_kind_guess": "SDD"}
    from app.services import template_compiler_service

    assert rate_limit_service.check_template_upload(ALICE).allowed
    for i in range(2):
        template_compiler_service.compile_template(spec, f"Punya Alice {i}",
                                                   doc_types=["SDD"], owner="alice")

    assert not rate_limit_service.check_template_upload(ALICE).allowed
    # Template Alice tak mengurangi jatah Bob.
    assert rate_limit_service.check_template_upload(BOB).allowed
