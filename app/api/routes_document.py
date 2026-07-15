"""Endpoint dokumen (Peran 3 — Backend & Templating).

Tidak mengubah kode Peran 1 (parser_service.py, ingestion_service.py) atau
Peran 2 (llm_service.py) — hanya mengimpor & memanggil apa yang sudah
mereka sediakan."""

import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse

from app.api.schemas_document import GenerateDocumentRequest
from app.domain.exceptions import (
    ContextWindowExceededError,
    DiagramRenderError,
    DocumentTruncatedError,
    PandocUnavailableError,
    SourceProviderError,
)
from app.domain.models import GithubIngestRequest, SourceType
from app.services import job_store
from app.services.compiler_service import generate_docx
from app.services.ingestion_service import IngestionService
from app.services.llm_service import DocumentContent, LLMService
from app.services.parser_service import build_parsed_repo_context

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])

_ingestion_service = IngestionService()
_llm_service = LLMService()

_DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_FILENAME_BY_TYPE = {
    "SDD": "Solution_Design_Document.docx",
    "UAT": "User_Acceptance_Test.docx",
}


def _render_docx_or_502(
    doc_type: str,
    content: dict,
    project_name: str = "",
    document_metadata: dict | None = None,
) -> str:
    """Bungkus generate_docx() supaya kegagalan pihak ketiga (render diagram,
    pandoc) tidak bocor sebagai HTTP 500 mentah ke klien."""
    try:
        return generate_docx(
            doc_type,
            content,
            project_name=project_name,
            document_metadata=document_metadata,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except DiagramRenderError as e:
        # Teruskan sebab aslinya apa adanya. Versi sebelumnya meratakan SEMUA
        # kegagalan jadi "layanan tidak merespons", yang menyembunyikan HTTP 414
        # (script kepanjangan) dan bikin bugnya lama tidak terdiagnosis.
        logger.exception("Gagal merender diagram Mermaid")
        raise HTTPException(status_code=502, detail=f"Gagal merender diagram: {e}") from e
    except RuntimeError as e:
        logger.exception("Pandoc tidak tersedia saat export docx")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/sdd")
def generate_sdd_from_content(body: DocumentContent):
    """Endpoint testing: terima DocumentContent.json (Contract B) langsung,
    tanpa lewat ingestion/LLM. Dipakai untuk mengembangkan & menguji
    template dengan data dummy sebelum pipeline penuh siap."""
    output_path = _render_docx_or_502("SDD", body.model_dump())
    return FileResponse(output_path, media_type=_DOCX_MEDIA_TYPE, filename=_FILENAME_BY_TYPE["SDD"])


@router.post("/uat")
def generate_uat_from_content(body: DocumentContent):
    """Sama seperti /documents/sdd, untuk dokumen UAT."""
    output_path = _render_docx_or_502("UAT", body.model_dump())
    return FileResponse(output_path, media_type=_DOCX_MEDIA_TYPE, filename=_FILENAME_BY_TYPE["UAT"])


def _run_generation(job_id: str, body: GenerateDocumentRequest) -> None:
    """Pipeline penuh, dijalankan di LATAR BELAKANG: ingest -> parse (Peran 1)
    -> generate content (Peran 2) -> render & export docx (Peran 3).

    Seluruh pemetaan exception -> kode HTTP yang dulu ada di endpoint pindah ke
    sini, tapi TIDAK melempar HTTPException — tidak ada request yang menunggu
    lagi. Kodenya disimpan ke job supaya GET /jobs/{id} bisa mengembalikannya apa
    adanya. Ini yang menjaga kerja error handling sebelumnya tetap hidup:
    413 (repo kebesaran) dan 500 (dokumen terpotong) itu kegagalan PERMANEN, dan
    pengguna harus tetap bisa membedakannya dari 502 (layanan AI sedang
    bermasalah, silakan ulang). Kalau semua kegagalan job dilaporkan sama, kita
    balik ke penyamaran yang sudah tiga kali diperbaiki di project ini.
    """
    doc_type = body.document_type.upper()
    job_store.mark_running(job_id)
    try:
        output_path = _generate_document(doc_type, body)
    except SourceProviderError as e:
        job_store.mark_failed(job_id, str(e), 422)
    except ContextWindowExceededError as e:
        logger.warning("Contract A melebihi context window: %s", e)
        job_store.mark_failed(job_id, str(e), 413)
    except DocumentTruncatedError as e:
        logger.error("Dokumen terpotong karena max_tokens: %s", e)
        job_store.mark_failed(
            job_id,
            f"{e} Laporkan ke tim pengembang — ini batas di sisi sistem, bukan di repo Anda.",
            500,
        )
    except DiagramRenderError as e:
        logger.exception("Gagal merender diagram Mermaid")
        job_store.mark_failed(job_id, f"Gagal merender diagram: {e}", 502)
    except ValueError as e:
        job_store.mark_failed(job_id, str(e), 400)
    except PandocUnavailableError as e:
        logger.exception("Pandoc tidak tersedia saat export docx")
        job_store.mark_failed(job_id, str(e), 500)
    except Exception:
        # Jaring terakhir. Cuma DI SINI "coba lagi" itu saran yang jujur —
        # sebab yang tidak dikenal memang bisa sementara.
        logger.exception("Job %s gagal karena sebab tak dikenal", job_id)
        job_store.mark_failed(
            job_id, "Gagal menghasilkan dokumen. Coba lagi beberapa saat.", 502
        )
    else:
        job_store.mark_done(job_id, output_path)


@router.post("/generate", status_code=202)
def generate_document_full_pipeline(
    body: GenerateDocumentRequest, background_tasks: BackgroundTasks
):
    """Titik masuk sistem untuk end user. ASYNC sejak 2026-07-16.

    Balik <1 detik dengan job_id; kerjanya jalan di latar belakang. Versi
    sebelumnya menahan SELURUH pipeline di satu request HTTP — terukur 191 detik
    pada repo nyata — sementara proxy/load balancer umumnya memutus di 30-60
    detik (Heroku 30, nginx & AWS ALB 60, Vercel 10-60). Di localhost tidak ada
    satu pun batas itu, jadi bug-nya tidak terlihat sampai di-deploy; dan ketika
    koneksinya diputus, server tetap lanjut bekerja dan tetap membayar LLM untuk
    dokumen yang tidak pernah sampai ke siapa pun.
    """
    doc_type = body.document_type.upper()
    if doc_type not in _FILENAME_BY_TYPE:
        # Validasi murah dikerjakan SINKRON: request yang salah bentuk harus
        # ditolak sekarang, bukan jadi job yang gagal 3 menit kemudian.
        raise HTTPException(status_code=422, detail="document_type harus 'SDD' atau 'UAT'")

    job_id = job_store.create_job(document_type=doc_type, project_name=body.project_name)
    background_tasks.add_task(_run_generation, job_id, body)
    return {
        "job_id": job_id,
        "status": job_store.STATUS_QUEUED,
        "status_url": f"/documents/jobs/{job_id}",
    }


@router.get("/jobs/{job_id}")
def get_job_status(job_id: str):
    """Status job. 200 walau job-nya gagal — pertanyaannya ("job ini bagaimana?")
    berhasil dijawab; kegagalan generation-nya ada di dalam payload, lengkap
    dengan `error_status` supaya klien tahu ini kegagalan permanen atau bukan."""
    job = job_store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} tidak ditemukan.")

    payload = {
        "job_id": job["id"],
        "status": job["status"],
        "document_type": job["document_type"],
        "created_at": job["created_at"],
        "updated_at": job["updated_at"],
    }
    if job["status"] == job_store.STATUS_DONE:
        payload["download_url"] = f"/documents/jobs/{job_id}/download"
    elif job["status"] == job_store.STATUS_FAILED:
        payload["error"] = job["error"]
        payload["error_status"] = job["error_status"]
    return payload


@router.get("/jobs/{job_id}/download")
def download_job_document(job_id: str):
    job = job_store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} tidak ditemukan.")
    if job["status"] != job_store.STATUS_DONE:
        # 409, bukan 404: job-nya ADA, cuma belum siap. 404 akan bikin klien
        # mengira job_id-nya salah.
        raise HTTPException(
            status_code=409,
            detail=f"Job {job_id} belum selesai (status: {job['status']}).",
        )
    return FileResponse(
        job["docx_path"],
        media_type=_DOCX_MEDIA_TYPE,
        filename=_FILENAME_BY_TYPE[job["document_type"]],
    )


def _generate_document(doc_type: str, body: GenerateDocumentRequest) -> str:
    """Pipeline murni: tidak tahu-menahu soal job maupun HTTP.

    Dipisah dari _run_generation supaya yang satu mengurus PEKERJAAN dan yang
    lain mengurus KEGAGALAN — tanpa ini, tujuh blok except membungkus tiga puluh
    baris orkestrasi dan keduanya jadi sulit dibaca.
    """
    ingest_requests = [
        GithubIngestRequest(
            repo_tag=r.repo_tag,
            repo_url=r.repo_url,
            branch=r.branch,
            access_token=body.github_token,
        )
        for r in body.repositories
    ]

    # Exception dibiarkan naik apa adanya — _run_generation yang memetakannya ke
    # kode HTTP dan menyimpannya ke job. Fungsi ini sengaja tidak tahu HTTP.
    workspaces = _ingestion_service.ingest(SourceType.GITHUB, ingest_requests)

    parsed_repo_context = build_parsed_repo_context(
        project_name=body.project_name or "generated-project",
        workspaces=workspaces,
    )
    document_content = _llm_service.generate_document_content(
        parsed_repo_context=parsed_repo_context,
        target_doc_type=doc_type,
    )
    try:
        return generate_docx(
            doc_type,
            document_content,
            project_name=body.project_name or "",
            document_metadata=(
                body.document_metadata.model_dump() if body.document_metadata else None
            ),
        )
    except RuntimeError as e:
        # compiler_service melempar RuntimeError POLOS untuk "pandoc tidak ada".
        # Ditangkap DI SINI, di sekeliling panggilan yang bersangkutan saja.
        # Menangkapnya di _run_generation (yang membungkus seluruh pipeline) akan
        # melabeli RuntimeError dari MANA PUN sebagai "Pandoc tidak tersedia" —
        # persis penyamaran sebab yang sudah tiga kali diperbaiki di project ini.
        # Test menangkap ini: RuntimeError dari LLM sempat dilaporkan sebagai 500
        # "Pandoc" alih-alih 502.
        raise PandocUnavailableError(str(e)) from e
