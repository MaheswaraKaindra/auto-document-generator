"""Endpoint dokumen (Peran 3 — Backend & Templating).

Tidak mengubah kode Peran 1 (parser_service.py, ingestion_service.py) atau
Peran 2 (llm_service.py) — hanya mengimpor & memanggil apa yang sudah
mereka sediakan."""

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.api.schemas_document import GenerateDocumentRequest
from app.domain.exceptions import DiagramRenderError, SourceProviderError
from app.domain.models import GithubIngestRequest, SourceType
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


def _render_docx_or_502(doc_type: str, content: dict, project_name: str = "") -> str:
    """Bungkus generate_docx() supaya kegagalan pihak ketiga (render diagram,
    pandoc) tidak bocor sebagai HTTP 500 mentah ke klien."""
    try:
        return generate_docx(doc_type, content, project_name=project_name)
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


@router.post("/generate")
def generate_document_full_pipeline(body: GenerateDocumentRequest):
    """Endpoint orkestrator penuh: ingest repo -> parse (Peran 1)
    -> generate content (Peran 2) -> render & export docx (Peran 3),
    jadi satu request. Ini titik masuk sistem sesungguhnya untuk end user."""
    doc_type = body.document_type.upper()
    if doc_type not in _FILENAME_BY_TYPE:
        raise HTTPException(status_code=422, detail="document_type harus 'SDD' atau 'UAT'")

    ingest_requests = [
        GithubIngestRequest(
            repo_tag=r.repo_tag,
            repo_url=r.repo_url,
            branch=r.branch,
            access_token=body.github_token,
        )
        for r in body.repositories
    ]

    try:
        workspaces = _ingestion_service.ingest(SourceType.GITHUB, ingest_requests)
    except SourceProviderError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    parsed_repo_context = build_parsed_repo_context(
        project_name=body.project_name or "generated-project",
        workspaces=workspaces,
    )

    try:
        document_content = _llm_service.generate_document_content(
            parsed_repo_context=parsed_repo_context,
            target_doc_type=doc_type,
        )
    except Exception as e:
        logger.exception("Pemanggilan LLM gagal")
        raise HTTPException(
            status_code=502,
            detail="Gagal menghasilkan konten dokumen dari AI. Coba lagi beberapa saat.",
        ) from e

    output_path = _render_docx_or_502(doc_type, document_content, project_name=body.project_name or "")

    return FileResponse(output_path, media_type=_DOCX_MEDIA_TYPE, filename=_FILENAME_BY_TYPE[doc_type])
