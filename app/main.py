from fastapi import FastAPI

from app.api.routes_auth import router as auth_router
from app.api.routes_ingestion import router as ingestion_router

app = FastAPI(title="Auto Document Generator")

app.include_router(ingestion_router)
app.include_router(auth_router)


@app.get("/health")
def health():
    return {"status": "ok"}
