"""Entrypoint WORKER (#13) — proses yang benar-benar mengeksekusi pipeline.

    python -m app.worker

Dijalankan sebagai proses/container TERPISAH dari web. Itu seluruh gunanya: web
yang mati (deploy, crash, OOM) tak lagi ikut membunuh pekerjaan yang sedang jalan,
dan jumlah web bisa dinaikkan tanpa menggandakan eksekutor.

Butuh `REDIS_URL`. Tanpa itu aplikasi berjalan mode inline (`BackgroundTasks`) dan
worker ini tak punya pekerjaan — jadi dia menolak start dengan pesan yang menyebut
sebabnya, bukan diam menunggu antrian yang tak akan pernah ada.

WINDOWS: `Worker` bawaan RQ memakai `os.fork()` yang tidak ada di Windows, jadi di
sana dipakai `SimpleWorker` (eksekusi di proses yang sama, tanpa fork). Bedanya
nyata dan sengaja dicatat: SimpleWorker TIDAK menegakkan `job_timeout` — job yang
menggantung akan menggantung bersamanya. Untuk produksi jalankan worker ini di
Linux/container (`docker compose`), di mana jalur fork yang dipakai. Windows di
sini untuk pengembangan, bukan target deploy.
"""

from __future__ import annotations

import logging
import os
import sys

from app.core import config
from app.services import job_queue, job_store

logger = logging.getLogger(__name__)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if not job_queue.queue_enabled():
        print(
            "REDIS_URL kosong — aplikasi sedang jalan mode INLINE, jadi tak ada\n"
            "antrian yang perlu dikerjakan worker. Isi REDIS_URL di .env "
            "(mis. redis://localhost:6379/0)\nlalu jalankan ulang.",
            file=sys.stderr,
        )
        return 2

    # Skema DB disiapkan di sini juga, bukan cuma di main.py: worker bisa jadi
    # proses PERTAMA yang menyentuh DB (container worker start lebih dulu dari
    # web), dan job yang jatuh ke tabel yang belum ada gagal dengan pesan yang
    # tak menyebut sebab aslinya. Idempoten — sama seperti pemanggilan di web.
    job_store.init_db()

    from redis import Redis                          # noqa: PLC0415
    from rq import Queue, SimpleWorker, Worker       # noqa: PLC0415

    connection = Redis.from_url(config.REDIS_URL)
    queue = Queue(config.JOB_QUEUE_NAME, connection=connection)

    worker_class = SimpleWorker if os.name == "nt" else Worker
    if worker_class is SimpleWorker:
        logger.warning(
            "Windows terdeteksi: memakai SimpleWorker (tanpa fork), jadi "
            "job_timeout TIDAK ditegakkan. Untuk produksi jalankan worker di "
            "container/Linux."
        )

    logger.info("Worker siap. Antrian=%r, redis=%s, kelas=%s",
                config.JOB_QUEUE_NAME, config.REDIS_URL, worker_class.__name__)
    worker_class([queue], connection=connection).work(with_scheduler=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
