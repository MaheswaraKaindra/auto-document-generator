import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes_auth import router as auth_router
from app.api.routes_billing import router as billing_router
from app.api.routes_document import router as document_router
from app.api.routes_ingestion import router as ingestion_router
from app.api.routes_template import router as template_router
from app.core import config
from app.core.logging_config import configure_logging
from app.services import billing_service, job_queue, job_store, readiness_service, telemetry

# Observability (#14): pasang format log + error tracking SEBELUM apa pun yang
# bisa gagal di bawah — supaya kegagalan startup pun ikut terformat & terlacak.
configure_logging()
telemetry.init_sentry()

app = FastAPI(title="Auto Document Generator")

# Tabel job dan billing dibuat saat import
job_store.init_db()
billing_service.init_billing_db()

# Lanjutkan job yang mati BERSAMA worker-nya (#13). Dijalankan SEBELUM reaper:
# selama argumennya masih ada di antrian, job itu layak diteruskan, bukan
# divonis gagal. No-op di mode inline (tanpa REDIS_URL) — di sana tak ada
# antrian yang menyimpan pekerjaannya, jadi reaper di bawah tetap jawabannya.
#
# Dibungkus try: Redis yang belum siap (urutan start container) tak boleh
# menggagalkan boot proses web. Status job hidup di DB, dan sapuan ini diulang
# lagi lazy tiap GET status.
try:
    job_queue.requeue_abandoned()
except Exception:
    logging.getLogger(__name__).warning(
        "Re-queue job terbengkalai dilewati saat startup", exc_info=True)

# Pungut job yang macet di `running`/`queued` dari proses SEBELUMNYA yang mati
# saat job jalan (deploy/crash/OOM). Di sini — bukan di event startup — dengan
# alasan yang sama seperti init_db di atas: TestClient & sebagian jalur deploy
# tak menjalankan startup hook. Idempoten; di DB tanpa job basi ini no-op.
job_store.reap_stale_jobs()

# Bersihkan docx yang kedaluwarsa (lihat DOCUMENT_TTL_SECONDS). Alasan & titik
# panggil yang sama dengan reaper di atas: nol scheduler, cuma satu sapuan murah
# di tempat yang memang sudah dijalankan.
job_store.purge_expired_documents()

# CORS diperketat dari `*` ke daftar origin (#15): dibaca dari
# `CORS_ALLOW_ORIGINS` (lihat config), default origin dev Vite. Saat container
# menyajikan frontend SAME-ORIGIN, CORS tak terpakai — ini cuma relevan untuk
# frontend yang dilayani dari origin berbeda (mis. dev `npm run dev`).
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ALLOW_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
    # `allow_headers` mengizinkan header REQUEST; ini yang mengizinkan JavaScript
    # MEMBACA header response. Dua hal berbeda, dan tanpa baris ini browser
    # menyembunyikan Content-Disposition secara diam-diam: server mengirim
    # "Solution_Design_Document.docx", frontend tidak bisa membacanya, lalu jatuh
    # ke nama cadangan — jadi SETIAP pengguna mengunduh "dokumen.docx".
    # Tidak ada error, tidak ada peringatan; cuma nama file yang tidak berguna.
    # Ketahuan di gladi bersih demo, dari nama file yang terunduh.
    expose_headers=["Content-Disposition"],
)

app.include_router(ingestion_router)
app.include_router(auth_router)
app.include_router(document_router)
app.include_router(template_router)
app.include_router(billing_router)



@app.get("/health")
def health():
    """Liveness: proses ini hidup & bisa menjawab. Sengaja TANPA cek dependency —
    orchestrator memakainya untuk memutuskan restart, dan me-restart karena
    pandoc hilang tak menyembuhkan apa pun."""
    return {"status": "ok"}


@app.get("/ready")
def ready():
    """Readiness: proses ini bisa MENGERJAKAN pekerjaannya (DB + pandoc + Java +
    plantuml.jar ada). 503 kalau satu saja hilang — sinyal ke orchestrator untuk
    tidak mengarahkan trafik ke instance ini sampai dependency-nya lengkap."""
    result = readiness_service.readiness()
    status = 200 if result["ready"] else 503
    return JSONResponse(result, status_code=status)


# Frontend hasil build (SPA) disajikan dari origin yang SAMA dengan API — satu
# `docker run` = aplikasi utuh, tanpa CORS. Di-mount PALING AKHIR supaya semua
# route API (/health, /documents, /templates, ...) menang lebih dulu; mount "/"
# cuma menangkap sisanya (index.html + /assets). `html=True` menyajikan
# index.html untuk "/". Hanya aktif kalau build ADA: dev (`npm run dev`) dan
# test tak punya dist, jadi baris ini no-op di sana.
_frontend_dist = Path(config.FRONTEND_DIST)
if _frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True),
              name="frontend")
