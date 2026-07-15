"""Penyimpanan job generate dokumen (Peran 3).

Ada karena generation itu ASYNC sekarang: POST balik duluan (<1 detik), kerjanya
jalan di latar belakang, jadi harus ada tempat menaruh status dan hasilnya.
Sebelum ini tidak ada tempat sama sekali — `FileResponse(output_path)` mengirim
file dari temp, dan begitu response terkirim tidak ada jejak apa pun: tidak ada
riwayat, tidak bisa unduh ulang, tidak bisa tahu job kemarin berhasil atau gagal.

sqlite3 dari stdlib, BUKAN SQLAlchemy: nol dependency baru, nol layanan yang
harus hidup saat deploy. Skemanya sengaja rata (bukan ORM) supaya pindah ke
Postgres nanti cuma soal mengganti isi modul ini, bukan membongkar pemanggilnya.

SATU KONEKSI PER OPERASI, bukan koneksi global. BackgroundTasks menjalankan
fungsi sync di threadpool, dan koneksi sqlite3 tidak boleh dipakai lintas thread
(default `check_same_thread=True`). Koneksi global akan meledak dengan
ProgrammingError begitu job kedua jalan di thread berbeda — jenis bug yang cuma
muncul saat ada beban, bukan saat dites satu-satu.
"""

import shutil
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.core import config

# Dibiarkan module-level (bukan konstanta beku) supaya test bisa mengarahkannya
# ke tmp_path — pola yang sama dengan OUTPUT_DIR di compiler_service.
DB_PATH = Path(config.DATABASE_PATH)

STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_DONE = "done"
STATUS_FAILED = "failed"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id            TEXT PRIMARY KEY,
    status        TEXT NOT NULL,
    document_type TEXT NOT NULL,
    project_name  TEXT,
    docx_path     TEXT,
    error         TEXT,
    error_status  INTEGER,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
"""


def _documents_dir() -> Path:
    """Tempat docx disimpan: di sebelah DB, bukan di temp.

    compiler_service menulis ke temp — cocok untuk hasil sekali pakai, tapi
    salah untuk sesuatu yang path-nya dicatat di database yang bertahan melewati
    restart. Path di DB yang menunjuk ke file yang sudah dibersihkan OS itu
    kebohongan yang baru ketahuan saat pengguna klik unduh.
    """
    return DB_PATH.parent / "documents"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Bikin tabel kalau belum ada. Aman dipanggil berkali-kali."""
    with _connect() as conn:
        conn.executescript(_SCHEMA)


def create_job(document_type: str, project_name: Optional[str]) -> str:
    job_id = uuid.uuid4().hex
    now = _now()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO jobs (id, status, document_type, project_name, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (job_id, STATUS_QUEUED, document_type, project_name, now, now),
        )
    return job_id


def mark_running(job_id: str) -> None:
    _update(job_id, status=STATUS_RUNNING)


def mark_done(job_id: str, docx_path: str) -> None:
    """Pindahkan docx ke tempat permanen, baru catat path-nya.

    Urutannya penting: kalau path dicatat duluan lalu penyalinan gagal, job
    terlihat 'done' padahal filenya tidak ada.
    """
    documents_dir = _documents_dir()
    documents_dir.mkdir(parents=True, exist_ok=True)
    stored = documents_dir / f"{job_id}{Path(docx_path).suffix}"
    shutil.copyfile(docx_path, stored)
    _update(job_id, status=STATUS_DONE, docx_path=str(stored))


def mark_failed(job_id: str, error: str, error_status: int) -> None:
    """error_status = kode HTTP yang SEHARUSNYA dikembalikan kalau ini sinkron.

    Ini yang menjaga kerja error handling sebelumnya tetap hidup: 413 (repo
    kebesaran) dan 500 (dokumen terpotong) itu kegagalan permanen, dan pengguna
    harus tetap tahu bedanya dengan 502 (layanan AI sedang bermasalah — silakan
    ulang). Tanpa kolom ini, semua kegagalan job kembali terlihat sama —
    persis penyamaran yang sudah tiga kali diperbaiki di project ini.
    """
    _update(job_id, status=STATUS_FAILED, error=error, error_status=error_status)


def _update(job_id: str, **fields: Any) -> None:
    fields["updated_at"] = _now()
    assignments = ", ".join(f"{k} = ?" for k in fields)
    with _connect() as conn:
        conn.execute(
            f"UPDATE jobs SET {assignments} WHERE id = ?", (*fields.values(), job_id)
        )


def get_job(job_id: str) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return dict(row) if row else None
