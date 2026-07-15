from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_auth import router as auth_router
from app.api.routes_document import router as document_router
from app.api.routes_ingestion import router as ingestion_router
from app.services import job_store

app = FastAPI(title="Auto Document Generator")

# Tabel job dibuat saat import, bukan di event startup: TestClient dan sebagian
# jalur deploy tidak selalu menjalankan startup hook, dan tabel yang belum ada
# baru ketahuan sebagai OperationalError di dalam background task — di mana tidak
# ada request yang bisa menampung errornya. init_db() aman dipanggil berkali-kali.
job_store.init_db()

# Kerangka frontend (frontend/) dipanggil dari origin terpisah (dibuka
# langsung sebagai file atau lewat dev server), jadi butuh CORS.
# allow_origins="*" hanya untuk kebutuhan development; persempit sebelum
# dipakai di produksi.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingestion_router)
app.include_router(auth_router)
app.include_router(document_router)


@app.get("/health")
def health():
    return {"status": "ok"}
