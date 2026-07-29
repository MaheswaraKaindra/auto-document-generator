"""Tes seam eksekusi job (#13): inline (BackgroundTasks) vs RQ (worker terpisah).

Redis TIDAK disentuh di sini — antriannya di-mock di boundary `get_queue`, persis
pola yang dipakai untuk LLM & plantuml.jar: test tak boleh menuntut layanan hidup.
Bukti bahwa jalur RQ benar-benar jalan dengan Redis sungguhan ada di verifikasi
end-to-end (lihat CHANGELOG #13), bukan di sini — dan pemisahan itu disengaja:
yang dijaga file ini adalah KEPUTUSANNYA (mode mana, meta apa, siapa yang tak
boleh disentuh), bukan bahwa Redis bisa dihubungi.
"""

import pytest

from app.core import config
from app.services import job_queue, job_store


class _FakeBackgroundTasks:
    def __init__(self):
        self.tasks = []

    def add_task(self, func, *args):
        self.tasks.append((func, args))


class _FakeQueue:
    def __init__(self):
        self.calls = []

    def enqueue(self, func, *args, **kwargs):
        self.calls.append((func, args, kwargs))
        return type("_Job", (), {"id": "rq-job-1"})()


def _noop(*_args):
    pass


@pytest.fixture(autouse=True)
def _bersihkan_cache_antrian():
    job_queue.reset_queue_cache()
    yield
    job_queue.reset_queue_cache()


def test_default_inline_tanpa_redis(monkeypatch):
    """REDIS_URL kosong = perilaku sebelum #13: jalan di proses web.

    Ini yang menjaga dev/test/demo $0 tidak menuntut layanan tambahan hidup.
    """
    monkeypatch.setattr(config, "REDIS_URL", None)
    bg = _FakeBackgroundTasks()

    assert job_queue.queue_enabled() is False
    assert job_queue.enqueue(bg, _noop, "job-1") == "inline"
    assert len(bg.tasks) == 1
    assert bg.tasks[0][1] == ("job-1",)


def test_mode_rq_tak_menyentuh_background_tasks(monkeypatch):
    """REDIS_URL terisi = web cuma mengantri. `BackgroundTasks` harus TETAP kosong —
    kalau dua-duanya terpakai, pipeline berbayar jalan DUA KALI."""
    monkeypatch.setattr(config, "REDIS_URL", "redis://localhost:6379/0")
    fake = _FakeQueue()
    monkeypatch.setattr(job_queue, "get_queue", lambda: fake)
    bg = _FakeBackgroundTasks()

    assert job_queue.enqueue(bg, _noop, "job-2", domain_job_id="job-2") == "rq"
    assert bg.tasks == [], "mode RQ tak boleh ikut menjalankan di proses web"
    assert len(fake.calls) == 1

    func, args, kwargs = fake.calls[0]
    assert func is _noop
    assert args == ("job-2",)
    # Jejak balik ke baris `jobs` — tanpa ini job terbengkalai tak bisa
    # dihubungkan ke job domain mana pun saat re-queue.
    assert kwargs["meta"] == {"job_id": "job-2"}
    assert kwargs["job_timeout"] == job_queue.JOB_TIMEOUT_SECONDS


def test_job_timeout_selaras_dengan_ambang_reaper():
    """Dua ambang untuk pertanyaan yang sama ("job ini sudah mati?") yang
    menyimpang menghasilkan zona abu-abu: RQ menganggap job hidup sementara
    reaper sudah memvonisnya gagal, atau sebaliknya."""
    assert job_queue.JOB_TIMEOUT_SECONDS == job_store.STALE_JOB_SECONDS


def test_requeue_no_op_di_mode_inline(monkeypatch):
    """Tanpa antrian tak ada argumen job yang tersimpan, jadi tak ada yang bisa
    dilanjutkan — reaper (vonis) tetap satu-satunya jawaban di mode inline."""
    monkeypatch.setattr(config, "REDIS_URL", None)
    assert job_queue.requeue_abandoned() == 0


def test_requeue_dimatikan_saat_max_attempts_nol(monkeypatch):
    """JOB_MAX_ATTEMPTS=0 mematikan re-queue sepenuhnya — dan mematikannya lewat
    env lebih jujur daripada menyetel angka yang terlihat seperti batas."""
    monkeypatch.setattr(config, "REDIS_URL", "redis://localhost:6379/0")

    def _boom():
        raise AssertionError("antrian tak boleh disentuh saat re-queue dimatikan")

    monkeypatch.setattr(job_queue, "get_queue", _boom)
    assert job_queue.requeue_abandoned(max_attempts=0) == 0


def test_mark_requeued_mengembalikan_job_ke_antrian(tmp_path, monkeypatch):
    """Job yang dilanjutkan harus terlihat `queued` lagi, tanpa sisa pesan gagal.

    Membiarkan `error` lama menempel pada job yang kini sehat menampilkan
    kegagalan yang sudah tidak berlaku ke pengguna yang sedang polling.
    """
    monkeypatch.setattr(job_store, "DB_PATH", tmp_path / "jobs.db")
    job_store.init_db()

    job_id = job_store.create_job("SDD", "Proj", owner="usr_1")
    job_store.mark_failed(job_id, "Proses berhenti di tengah jalan", 503)
    assert job_store.attempts_of(job_id) == 0

    assert job_store.mark_requeued(job_id) == 1
    job = job_store.get_job(job_id)
    assert job["status"] == job_store.STATUS_QUEUED
    assert job["error"] is None
    assert job["error_status"] is None
    assert job["attempts"] == 1

    # Percobaan berikutnya menaikkan hitungan — inilah yang membatasi job beracun
    # mengulang selamanya sambil membayar Claude tiap putaran.
    assert job_store.mark_requeued(job_id) == 2
    assert job_store.attempts_of(job_id) == 2
