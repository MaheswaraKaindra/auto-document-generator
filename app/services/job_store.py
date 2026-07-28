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

import logging
import shutil
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from app.core import config

logger = logging.getLogger(__name__)

# Dibiarkan module-level (bukan konstanta beku) supaya test bisa mengarahkannya
# ke tmp_path — pola yang sama dengan OUTPUT_DIR di compiler_service.
DB_PATH = Path(config.DATABASE_PATH)

STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_DONE = "done"
STATUS_FAILED = "failed"

# Ambang "job basi": job running/queued yang TIDAK di-update selama ini dianggap
# mati (proses di-restart/crash/OOM saat job jalan). 30 menit dipilih supaya AMAN
# di atas jeda update terlama yang WAJAR untuk job SEHAT: client LLM diberi
# timeout 25 menit (llm_service) untuk repo besar, dan selama panggilan LLM itu
# tak ada set_progress — jadi job sehat bisa "diam" sampai ~25 menit. Ambang di
# bawah itu akan salah-bunuh job yang sebenarnya masih menunggu LLM. Sengaja =
# POLL_TIMEOUT frontend (30 menit): setelah itu klien pun sudah menyerah.
STALE_JOB_SECONDS = 30 * 60

# Pesan & kode untuk job yang dipungut reaper. 503 (bukan 500/413): proses mati
# itu kegagalan SEMENTARA — mengulang wajar — beda dari kegagalan PERMANEN (413
# repo kebesaran, 500 dokumen terpotong). Menjaga pemisahan permanen vs sementara
# yang jadi guna error_status (lihat mark_failed).
_STALE_ERROR = (
    "Job berhenti sebelum selesai — proses server kemungkinan di-restart atau "
    "mati saat job berjalan. Jalankan ulang; ini bukan masalah pada repo atau "
    "masukan Anda."
)
_STALE_STATUS = 503

# Umur dokumen sebelum dibersihkan. `data/documents/` tumbuh SELAMANYA tanpa ini
# — satu docx ~700 KB (terukur pada esteler), jadi pemakaian rutin mengisi disk
# tanpa ada yang menyadarinya sampai server penuh. 30 hari: jauh lebih lama dari
# umur pakai nyata sebuah unduhan (orang mengunduh dokumennya di hari yang sama),
# tapi masih menyisakan riwayat sebulan untuk "generate ulang bulan lalu mana ya".
DOCUMENT_TTL_SECONDS = 30 * 24 * 60 * 60

# Pesan & kode untuk job yang dokumennya sudah kedaluwarsa. 410 GONE, bukan 404:
# job-nya ADA dan dulu memang berhasil — yang hilang filenya, dan itu memang
# disengaja. Membedakannya dari 404 ("job_id salah") penting supaya pengguna
# tahu harus generate ulang, bukan mencari-cari id yang benar.
_EXPIRED_ERROR = (
    "Dokumen sudah dibersihkan otomatis karena berumur lebih dari 30 hari. "
    "Silakan generate ulang."
)
_EXPIRED_STATUS = 410

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id            TEXT PRIMARY KEY,
    status        TEXT NOT NULL,
    document_type TEXT NOT NULL,
    project_name  TEXT,
    template_id   TEXT,
    progress      TEXT,
    docx_path     TEXT,
    error         TEXT,
    error_status  INTEGER,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
"""

# Kolom yang ditambahkan SESUDAH ada DB di alam liar. `CREATE TABLE IF NOT EXISTS`
# tidak menyentuh tabel yang sudah ada, jadi tanpa ini DB lama akan meledak dengan
# "no such column: progress" — dan cuma di mesin yang sudah pernah menjalankan
# versi sebelumnya, bukan di test yang selalu mulai dari DB kosong. Bug yang tidak
# akan pernah terlihat di CI.
_MIGRATIONS = [
    ("progress", "ALTER TABLE jobs ADD COLUMN progress TEXT"),
    ("template_id", "ALTER TABLE jobs ADD COLUMN template_id TEXT"),
]


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
    """Bikin tabel kalau belum ada, lalu tambal kolom yang kurang. Aman dipanggil
    berkali-kali — dan wajib begitu, karena dipanggil tiap startup."""
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(jobs)")}
        for column, statement in _MIGRATIONS:
            if column not in existing:
                conn.execute(statement)


def create_job(
    document_type: str,
    project_name: Optional[str],
    template_id: Optional[str] = None,
) -> str:
    """`template_id` dicatat supaya riwayat job bisa menjawab "dokumen ini gaya
    apa" — sebelumnya tidak bisa, dan itu jadi pertanyaan begitu ada lebih dari
    satu gaya (default/premco/hasil-upload). Opsional supaya pemanggil lama
    (dan job di DB lama) tetap sah."""
    job_id = uuid.uuid4().hex
    now = _now()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO jobs (id, status, document_type, project_name, template_id,"
            " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (job_id, STATUS_QUEUED, document_type, project_name, template_id, now, now),
        )
    return job_id


def mark_running(job_id: str) -> None:
    _update(job_id, status=STATUS_RUNNING)


def set_progress(job_id: str, progress: str) -> None:
    """Catat tahap yang sedang dikerjakan, dalam kalimat yang dibaca PENGGUNA.

    Bukan untuk mempercepat apa pun — generation tetap ~2-3 menit, dan 72%-nya
    ada di panggilan LLM yang memang tidak bisa dipercepat tanpa menukar kualitas
    (yaitu satu-satunya nilai produk ini). Yang diperbaiki: sebelumnya status cuma
    "running", jadi frontend cuma bisa menghitung detik — angka berjalan yang
    tidak memberi tahu apa pun, dan tidak bisa dibedakan dari hang.

    Isinya sengaja menyertakan ANGKA NYATA dari repo pengguna ("22 file, 38
    endpoint"). Itu bukan hiasan: di detik ke-5 dia jadi bukti pertama bahwa
    sistem benar-benar membaca kode mereka, bukan mengarang.
    """
    _update(job_id, progress=progress)


def mark_done(job_id: str, docx_path: str) -> None:
    """Pindahkan docx ke tempat permanen, baru catat path-nya.

    Urutannya penting: kalau path dicatat duluan lalu penyalinan gagal, job
    terlihat 'done' padahal filenya tidak ada.
    """
    from app.services.compiler_service import drawio_bundle_for

    documents_dir = _documents_dir()
    documents_dir.mkdir(parents=True, exist_ok=True)
    stored = documents_dir / f"{job_id}{Path(docx_path).suffix}"
    shutil.copyfile(docx_path, stored)
    # Bundel .drawio ikut kalau ada — berkas BONUS, jadi ketiadaannya normal dan
    # kegagalannya tak boleh menggagalkan job yang dokumennya sudah jadi.
    bundle = drawio_bundle_for(docx_path)
    if bundle.exists():
        try:
            shutil.copyfile(bundle, drawio_bundle_for(stored))
        except OSError:
            logger.warning("Gagal menyalin bundel .drawio job %s", job_id, exc_info=True)
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


def reap_stale_jobs(max_age_seconds: float = STALE_JOB_SECONDS) -> int:
    """Tandai job `running`/`queued` yang macet (tak di-update > max_age) jadi
    `failed`, kembalikan jumlah yang dipungut.

    Kenapa perlu: BackgroundTasks menjalankan job DI DALAM proses yang menerima
    POST. Kalau proses itu mati (deploy, crash, OOM) saat job jalan, job-nya
    berhenti selamanya di `running` — tak ada yang memungutnya, dan klien akan
    polling tanpa akhir. Reaper inilah pemungutnya: dipanggil (1) saat startup —
    proses baru membersihkan job basi milik proses lama yang mati; dan (2) lazy
    saat GET status — satu worker yang hidup memungut job basi milik worker yang
    mati. Nol infrastruktur baru: tak ada thread/scheduler, cuma satu sapuan di
    titik yang memang sudah dijalankan.

    Aman karena `updated_at` disegarkan tiap set_progress — job SEHAT tak akan
    terlihat basi selama masih menulis progress; yang melewati ambang praktis
    pasti mati. Idempoten & aman lintas-worker: UPDATE ke `failed` menghasilkan
    nilai yang sama walau dua worker menyapu bersamaan.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=max_age_seconds)
    reaped = 0
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, updated_at FROM jobs WHERE status IN (?, ?)",
            (STATUS_RUNNING, STATUS_QUEUED),
        ).fetchall()
        for row in rows:
            try:
                updated = datetime.fromisoformat(row["updated_at"])
            except ValueError:
                # Timestamp tak terbaca (tak seharusnya terjadi): jangan sentuh —
                # lebih baik job tergantung daripada dibunuh atas dasar tebakan.
                continue
            if updated < cutoff:
                conn.execute(
                    "UPDATE jobs SET status = ?, error = ?, error_status = ?, "
                    "updated_at = ? WHERE id = ?",
                    (STATUS_FAILED, _STALE_ERROR, _STALE_STATUS, _now(), row["id"]),
                )
                reaped += 1
    return reaped


def purge_expired_documents(max_age_seconds: float = DOCUMENT_TTL_SECONDS) -> int:
    """Hapus docx yang lebih tua dari `max_age_seconds`, kembalikan jumlahnya.

    `data/documents/` tumbuh selamanya tanpa ini — satu docx ~700 KB, jadi
    pemakaian rutin akan mengisi disk tanpa ada yang menyadarinya.

    File DAN catatannya dibereskan bersama, dan urutannya kebalikan dari
    `mark_done`: di sana path dicatat SESUDAH file ada; di sini path dilepas
    SESUDAH file hilang. Dua-duanya menjaga aturan yang sama — DB tidak boleh
    menunjuk ke file yang tidak ada. Job-nya sendiri TIDAK dihapus: riwayat
    "pernah generate ini" tetap berguna, yang kedaluwarsa cuma filenya. Status
    jadi `failed`+410 supaya endpoint unduh punya jawaban jujur ("dulu ada,
    sudah dibersihkan") alih-alih meledak saat mengirim path yang kosong.

    Dipanggil di titik yang sama dengan `reap_stale_jobs` (startup + lazy saat
    GET status): nol infrastruktur baru, tak ada scheduler yang harus hidup.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=max_age_seconds)
    purged = 0
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, docx_path, updated_at FROM jobs"
            " WHERE status = ? AND docx_path IS NOT NULL",
            (STATUS_DONE,),
        ).fetchall()
        for row in rows:
            try:
                updated = datetime.fromisoformat(row["updated_at"])
            except ValueError:
                # Timestamp tak terbaca: jangan hapus apa pun atas dasar tebakan
                # — aturan yang sama dengan reap_stale_jobs.
                continue
            if updated >= cutoff:
                continue
            from app.services.compiler_service import drawio_bundle_for

            Path(row["docx_path"]).unlink(missing_ok=True)
            # Bundel .drawio lahir & mati bersama dokumennya. Membiarkannya
            # tertinggal mengulang persis masalah yang fungsi ini ada untuk
            # menyelesaikan: folder yang tumbuh selamanya.
            drawio_bundle_for(row["docx_path"]).unlink(missing_ok=True)
            conn.execute(
                "UPDATE jobs SET status = ?, docx_path = NULL, error = ?,"
                " error_status = ?, updated_at = ? WHERE id = ?",
                (STATUS_FAILED, _EXPIRED_ERROR, _EXPIRED_STATUS, _now(), row["id"]),
            )
            purged += 1
    return purged


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
