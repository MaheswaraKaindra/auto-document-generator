"""Test job_store — fokus reaper job basi (reap_stale_jobs).

Jalur job store lain (create/mark/get) ter-cover tidak langsung lewat
test_routes_document.py yang menjalankan pipeline end-to-end. File ini menguji
satu-satunya cabang yang TIDAK terlatih di sana: apa yang terjadi pada job yang
proses-nya mati di tengah jalan (stuck `running`/`queued`).
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from docx import Document

from app.services import job_store


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Arahkan SQLite ke tmp_path — jangan sentuh data/jobs.db pengembang."""
    monkeypatch.setattr(job_store, "DB_PATH", tmp_path / "jobs.db")
    job_store.init_db()


def _make_aged_job(monkeypatch, *, minutes_ago: float, mark=job_store.mark_running):
    """Buat job dengan updated_at `minutes_ago` menit di masa lalu.

    Ditua-kan lewat monkeypatch `_now` (yang dipakai create_job & _update untuk
    menstempel updated_at), lalu _now dikembalikan ke asli — reap_stale_jobs
    sendiri memakai datetime.now() sungguhan untuk cutoff, jadi UMUR job yang
    menentukan, bukan waktu reap.
    """
    real_now = job_store._now
    aged = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()
    monkeypatch.setattr(job_store, "_now", lambda: aged)
    job_id = job_store.create_job("SDD", None)
    if mark is not None:
        mark(job_id)
    monkeypatch.setattr(job_store, "_now", real_now)
    return job_id


def test_reap_marks_stale_running_as_failed(monkeypatch):
    job_id = _make_aged_job(monkeypatch, minutes_ago=45)

    reaped = job_store.reap_stale_jobs()

    assert reaped == 1
    job = job_store.get_job(job_id)
    assert job["status"] == job_store.STATUS_FAILED
    # 503 = sementara (proses mati), bukan permanen — klien harus tahu boleh ulang.
    assert job["error_status"] == 503
    assert job["error"]  # ada pesan yang menjelaskan, bukan kosong


def test_reap_marks_stale_queued_as_failed(monkeypatch):
    # Job yang mati SEBELUM sempat mark_running (proses tumbang tepat setelah
    # create_job) juga harus dipungut, bukan cuma yang running.
    job_id = _make_aged_job(monkeypatch, minutes_ago=45, mark=None)

    assert job_store.reap_stale_jobs() == 1
    assert job_store.get_job(job_id)["status"] == job_store.STATUS_FAILED


def test_reap_ignores_fresh_running(monkeypatch):
    # Job yang baru saja update (mis. sedang menunggu LLM) TIDAK boleh dibunuh.
    job_id = _make_aged_job(monkeypatch, minutes_ago=2)

    assert job_store.reap_stale_jobs() == 0
    assert job_store.get_job(job_id)["status"] == job_store.STATUS_RUNNING


def test_reap_leaves_done_and_failed_untouched(monkeypatch, tmp_path):
    src = tmp_path / "src.docx"
    Document().save(str(src))
    done_id = _make_aged_job(monkeypatch, minutes_ago=90, mark=None)
    job_store.mark_done(done_id, str(src))
    failed_id = _make_aged_job(monkeypatch, minutes_ago=90, mark=None)
    job_store.mark_failed(failed_id, "gagal asli", 413)

    assert job_store.reap_stale_jobs() == 0
    assert job_store.get_job(done_id)["status"] == job_store.STATUS_DONE
    # Kegagalan permanen (413) tidak ditimpa jadi 503 oleh reaper.
    assert job_store.get_job(failed_id)["error_status"] == 413


def test_reap_counts_multiple(monkeypatch):
    _make_aged_job(monkeypatch, minutes_ago=45)
    _make_aged_job(monkeypatch, minutes_ago=60, mark=None)
    _make_aged_job(monkeypatch, minutes_ago=1)  # segar → tak terhitung

    assert job_store.reap_stale_jobs() == 2


# --- TTL dokumen (purge_expired_documents) ---


def _make_done_job(monkeypatch, tmp_path, *, days_ago: float, name: str):
    """Job `done` dengan docx sungguhan, di-tua-kan `days_ago` hari."""
    src = tmp_path / f"{name}.docx"
    Document().save(str(src))
    real_now = job_store._now
    aged = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    monkeypatch.setattr(job_store, "_now", lambda: aged)
    job_id = job_store.create_job("SDD", None)
    job_store.mark_done(job_id, str(src))
    monkeypatch.setattr(job_store, "_now", real_now)
    return job_id


def test_purge_deletes_expired_document_and_its_path(monkeypatch, tmp_path):
    """Inti TTL: file DIHAPUS, dan DB berhenti menunjuk ke file yang tak ada."""
    job_id = _make_done_job(monkeypatch, tmp_path, days_ago=40, name="lama")
    stored = job_store.get_job(job_id)["docx_path"]
    assert Path(stored).exists()

    assert job_store.purge_expired_documents() == 1

    job = job_store.get_job(job_id)
    assert not Path(stored).exists()
    assert job["docx_path"] is None
    # Job-nya tetap ada — yang kedaluwarsa filenya, bukan riwayatnya.
    assert job["error_status"] == 410


def test_purge_keeps_fresh_documents(monkeypatch, tmp_path):
    job_id = _make_done_job(monkeypatch, tmp_path, days_ago=3, name="baru")

    assert job_store.purge_expired_documents() == 0
    assert Path(job_store.get_job(job_id)["docx_path"]).exists()
    assert job_store.get_job(job_id)["status"] == job_store.STATUS_DONE


def test_purge_leaves_failed_jobs_untouched(monkeypatch, tmp_path):
    """Job gagal tak punya dokumen untuk dibersihkan, dan alasan gagalnya yang
    asli (413 permanen) tidak boleh ditimpa jadi 410."""
    job_id = _make_aged_job(monkeypatch, minutes_ago=60 * 24 * 40, mark=None)
    job_store.mark_failed(job_id, "repo kebesaran", 413)

    assert job_store.purge_expired_documents() == 0
    assert job_store.get_job(job_id)["error_status"] == 413


def test_purge_is_idempotent(monkeypatch, tmp_path):
    """Dipanggil tiap GET status, jadi sapuan kedua harus no-op — bukan error
    karena filenya sudah hilang."""
    _make_done_job(monkeypatch, tmp_path, days_ago=40, name="dua-kali")

    assert job_store.purge_expired_documents() == 1
    assert job_store.purge_expired_documents() == 0


def test_job_records_its_template_id(monkeypatch):
    """Riwayat job harus bisa menjawab "dokumen ini gaya apa"."""
    job_id = job_store.create_job("SDD", "Proyek X", template_id="premco")

    assert job_store.get_job(job_id)["template_id"] == "premco"


def test_template_id_is_optional_for_old_callers(monkeypatch):
    """Pemanggil lama (dan baris DB lama) tetap sah — kolomnya nullable."""
    job_id = job_store.create_job("UAT", None)

    assert job_store.get_job(job_id)["template_id"] is None
