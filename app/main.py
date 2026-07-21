from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_auth import router as auth_router
from app.api.routes_document import router as document_router
from app.api.routes_ingestion import router as ingestion_router
from app.api.routes_template import router as template_router
from app.services import job_store

app = FastAPI(title="Auto Document Generator")

# Tabel job dibuat saat import, bukan di event startup: TestClient dan sebagian
# jalur deploy tidak selalu menjalankan startup hook, dan tabel yang belum ada
# baru ketahuan sebagai OperationalError di dalam background task — di mana tidak
# ada request yang bisa menampung errornya. init_db() aman dipanggil berkali-kali.
job_store.init_db()

# Pungut job yang macet di `running`/`queued` dari proses SEBELUMNYA yang mati
# saat job jalan (deploy/crash/OOM). Di sini — bukan di event startup — dengan
# alasan yang sama seperti init_db di atas: TestClient & sebagian jalur deploy
# tak menjalankan startup hook. Idempoten; di DB tanpa job basi ini no-op.
job_store.reap_stale_jobs()

# Bersihkan docx yang kedaluwarsa (lihat DOCUMENT_TTL_SECONDS). Alasan & titik
# panggil yang sama dengan reaper di atas: nol scheduler, cuma satu sapuan murah
# di tempat yang memang sudah dijalankan.
job_store.purge_expired_documents()

# Kerangka frontend (frontend/) dipanggil dari origin terpisah (dibuka
# langsung sebagai file atau lewat dev server), jadi butuh CORS.
# allow_origins="*" hanya untuk kebutuhan development; persempit sebelum
# dipakai di produksi.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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


@app.get("/health")
def health():
    return {"status": "ok"}
