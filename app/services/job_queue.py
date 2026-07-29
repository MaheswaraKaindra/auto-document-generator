"""Seam EKSEKUSI job: di mana pipeline dokumen benar-benar dijalankan (#13).

DUA MODE, dipilih dari env — bukan flag terpisah yang bisa lupa disetel. Pola yang
sama persis dengan `auth_service` (`SUPABASE_URL` kosong → mode dev):

- **`REDIS_URL` kosong → INLINE.** Pipeline jalan lewat `BackgroundTasks`, DI DALAM
  proses web. Nol layanan tambahan yang harus hidup. Ini perilaku sebelum #13, dan
  issue #13 sendiri menyatakan itu cukup untuk satu instance — jadi dia tetap
  default, bukan jalur warisan yang dibiarkan membusuk.
- **`REDIS_URL` terisi → RQ.** Web cuma MENGANTRI (milidetik), worker terpisah yang
  mengeksekusi. Job selamat dari restart/crash/deploy proses web, dan web bisa
  diperbanyak tanpa menggandakan eksekutor.

Kenapa seam, bukan pindah total ke RQ: menjadikan Redis WAJIB berarti tiap sesi
dev, tiap test, dan tiap demo $0 menuntut satu layanan tambahan hidup — harga yang
tak sebanding untuk pemakaian satu instance. Seam membuat "punya Redis" jadi
keputusan deploy, bukan keputusan arsitektur yang mengikat semua orang.

Yang SENGAJA tidak ada di sini: pipeline itu sendiri. Modul ini cuma tahu cara
menaruh pekerjaan, tidak tahu isi pekerjaannya — supaya `routes_document` tetap
satu-satunya tempat yang memahami apa itu "generate dokumen".
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from app.core import config

logger = logging.getLogger(__name__)

# Batas hidup satu job di worker. Sengaja SAMA dengan STALE_JOB_SECONDS di
# job_store (30 menit): dua ambang untuk pertanyaan yang sama ("job ini sudah
# mati atau belum?") yang menyimpang satu sama lain menghasilkan zona abu-abu —
# RQ menganggap job masih hidup sementara reaper sudah memvonisnya gagal, atau
# sebaliknya. Nilainya sendiri di atas timeout LLM (1500 detik) supaya generation
# yang memang lama tidak dipotong di tengah.
JOB_TIMEOUT_SECONDS = 30 * 60

# Hasil job disimpan sebentar saja: kebenaran status ada di tabel `jobs`, bukan di
# Redis. Redis di sini antrian, bukan database.
RESULT_TTL_SECONDS = 600

_queue = None


def queue_enabled() -> bool:
    """True kalau eksekusi dipindah ke worker terpisah. Dibaca saat dipanggil
    (bukan di-cache) supaya test bisa menyetel `config.REDIS_URL` per-kasus."""
    return bool(config.REDIS_URL)


def get_queue():
    """Antrian RQ (lazy + di-cache). Mengimpor `redis`/`rq` HANYA saat dipakai.

    Import di dalam fungsi, bukan di kepala modul: dua paket itu opsional. Mode
    inline harus tetap jalan di mesin yang tak punya keduanya — kalau tidak,
    "Redis opsional" cuma benar di dokumentasi.
    """
    global _queue
    if _queue is None:
        from redis import Redis                      # noqa: PLC0415
        from rq import Queue                         # noqa: PLC0415
        _queue = Queue(
            config.JOB_QUEUE_NAME,
            connection=Redis.from_url(config.REDIS_URL),
            default_timeout=JOB_TIMEOUT_SECONDS,
        )
    return _queue


def reset_queue_cache() -> None:
    """Buang antrian yang di-cache. Untuk test yang mengganti `REDIS_URL`."""
    global _queue
    _queue = None


def requeue_abandoned(max_attempts: Optional[int] = None) -> int:
    """Antre ulang job yang mati BERSAMA worker-nya. Kembalikan jumlahnya.

    Inilah bagian #13 yang tidak bisa ditiru reaper. Reaper cuma memvonis:
    job yang macet ditandai `failed` 503 dan kerjanya HILANG — pengguna harus
    generate ulang, dan pipeline berbayar itu dijalankan dari nol. Di sini
    kerjanya benar-benar dilanjutkan, karena RQ masih menyimpan argumen job-nya
    di Redis. Itu sebabnya payload TIDAK perlu diduplikasi ke tabel `jobs`:
    antriannya sendiri sudah jadi tempat penyimpanan yang tahan restart.

    Kenapa isi FailedJobRegistry aman diulang: `_run_generation` menangkap SEMUA
    exception pipeline dan menuliskannya ke job sebagai kegagalan bernomor
    (413/422/500/502), lalu kembali normal — jadi dari sudut pandang RQ dia
    SUKSES. Yang tersisa di registry gagal karenanya bukan "dokumen ini tak bisa
    dibuat", melainkan "prosesnya mati sebelum sempat menjawab": SIGKILL, OOM,
    deploy di tengah jalan. Persis kelas yang layak diulang, dan pemisahan yang
    sama dengan 503-vs-permanen yang sudah dipakai `error_status`.

    Batas percobaan dijaga di DB (`jobs.attempts`), bukan di meta RQ, supaya
    mengosongkan Redis tidak diam-diam mengembalikan jatah ulang setiap job.
    """
    if not queue_enabled():
        return 0
    limit = config.JOB_MAX_ATTEMPTS if max_attempts is None else max_attempts
    if limit <= 0:
        return 0

    from rq.job import Job                           # noqa: PLC0415
    from rq.registry import FailedJobRegistry, StartedJobRegistry  # noqa: PLC0415

    from app.services import job_store               # noqa: PLC0415

    queue = get_queue()
    # Worker yang di-SIGKILL tak sempat memindahkan job-nya ke mana pun: job itu
    # tertinggal di StartedJobRegistry sampai ada yang menyapu. `cleanup()` yang
    # memindahkannya ke registry gagal begitu lease-nya lewat.
    StartedJobRegistry(queue=queue).cleanup()

    registry = FailedJobRegistry(queue=queue)
    requeued = 0
    for rq_job_id in registry.get_job_ids():
        try:
            rq_job = Job.fetch(rq_job_id, connection=queue.connection)
        except Exception:
            logger.warning("Job RQ %s tak bisa dibaca saat re-queue", rq_job_id,
                           exc_info=True)
            continue

        job_id = (rq_job.meta or {}).get("job_id")
        if not job_id:
            continue    # bukan job pipeline dokumen — bukan urusan kita
        if job_store.get_job(job_id) is None:
            # Job RQ menunjuk baris `jobs` yang sudah tak ada: DB diganti/dibersihkan,
            # atau antrian ini sisa dari instance lain yang berbagi Redis. Menjalankannya
            # ulang berarti membayar Claude untuk pekerjaan yang tak punya pemilik dan
            # tak akan pernah bisa diunduh siapa pun. Buang dari registry supaya dia
            # tidak diperiksa lagi setiap sapuan.
            logger.info("Job RQ %s menunjuk job %s yang tak ada di DB — dibuang",
                        rq_job_id, job_id)
            try:
                registry.remove(rq_job_id, delete_job=True)
            except Exception:
                logger.warning("Gagal membuang job RQ yatim %s", rq_job_id, exc_info=True)
            continue
        if job_store.attempts_of(job_id) >= limit:
            continue    # jatah ulangnya habis; biarkan tercatat gagal

        try:
            registry.requeue(rq_job_id)
        except Exception:
            logger.warning("Gagal antre ulang job %s", job_id, exc_info=True)
            continue

        attempts = job_store.mark_requeued(job_id)
        requeued += 1
        logger.info("Job %s diantre ulang (percobaan ke-%s) sesudah worker mati",
                    job_id, attempts + 1)
    return requeued


def enqueue(background_tasks: Any, func: Callable, *args: Any,
            domain_job_id: Optional[str] = None) -> str:
    """Jalankan `func(*args)` di latar belakang lewat mode yang sedang aktif.

    Mengembalikan nama mode ("rq" / "inline") supaya pemanggil bisa mencatatnya —
    berguna saat menerangkan kenapa sebuah job selamat (atau tidak) dari restart.

    Kegagalan meng-antri TIDAK ditelan diam-diam: kalau Redis mati, job yang
    sudah terlanjur dibuat di DB akan tergantung di `queued` selamanya tanpa ada
    yang mengerjakannya. Pemanggil yang menangkap ini bisa menandainya gagal
    dengan sebab yang benar — persis pemisahan sementara-vs-permanen yang sudah
    dipakai `error_status`.
    """
    if queue_enabled():
        get_queue().enqueue(
            func, *args,
            job_timeout=JOB_TIMEOUT_SECONDS,
            result_ttl=RESULT_TTL_SECONDS,
            # Jejak balik ke baris `jobs`. Tanpa ini, job RQ yang terbengkalai
            # tak bisa dihubungkan ke job domain mana pun, dan re-queue harus
            # menebak dari posisi argumen — yang berarti modul ini jadi tahu
            # bentuk pipeline-nya.
            meta={"job_id": domain_job_id} if domain_job_id else {},
        )
        return "rq"

    background_tasks.add_task(func, *args)
    return "inline"


def enqueue_by_id(func: Callable, *args: Any) -> Optional[str]:
    """Antri TANPA `BackgroundTasks` — untuk pemanggil yang tak punya request HTTP
    (mis. re-queue job terbengkalai saat startup).

    Mode inline tak punya jawaban di sini: `BackgroundTasks` hidup dari sebuah
    request, dan menjalankan pipeline 3 menit di dalam startup hook akan menahan
    proses web sebelum dia sempat melayani apa pun. Jadi mode inline mengembalikan
    None (= "tak diantri"), dan pemanggil memutuskan apa artinya.
    """
    if not queue_enabled():
        return None
    job = get_queue().enqueue(
        func, *args,
        job_timeout=JOB_TIMEOUT_SECONDS,
        result_ttl=RESULT_TTL_SECONDS,
    )
    return job.id
