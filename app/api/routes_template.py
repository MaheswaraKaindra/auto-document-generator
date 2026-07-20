"""Endpoint template (V2 — upload template dokumen user jadi template terdaftar).

Deterministik & cepat ($0, tanpa LLM), jadi **SINKRON** — beda dari
`/documents/generate` yang async karena menunggu LLM. User meng-upload `.docx`
template perusahaannya; sistem mengukur + meng-generate template terdaftar, lalu
`template_id` itu bisa dipakai di `POST /documents/generate` seperti
"default"/"premco" (jalurnya sudah tersambung: `validate_template` di endpoint
generate menerima template terkompilasi).
"""
import logging
import tempfile
import zipfile
from pathlib import Path

from docx.opc.exceptions import PackageNotFoundError
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.services import compiler_service
from app.services.template_compiler_service import (
    compile_template_from_docx,
    load_compiled_detail,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/templates", tags=["templates"])

# Template vendor bisa berat karena mockup/gambar ter-embed (docx PREMCO asli ~40
# MB). Diukur SEKALI lalu dibebaskan, jadi batasnya soal mencegah abuse, bukan
# memori jangka panjang.
_MAX_UPLOAD_BYTES = 50 * 1024 * 1024


@router.get("")
def list_templates():
    """Semua `template_id` yang bisa dipakai di `POST /documents/generate` —
    built-in ('default'/'premco') + hasil-upload. Buat mengisi dropdown gaya
    dokumen di frontend."""
    return {"templates": compiler_service.list_template_ids()}


@router.post("", status_code=201)
def upload_template(
    file: UploadFile = File(...),
    name: str | None = Form(None),
    doc_types: str | None = Form(None),
    use_llm_mapping: bool = Form(False),
):
    """Upload `.docx` template → ukur + kompilasi jadi template terdaftar. Balik
    `template_id` + rencana peta bab (untuk ditinjau sebelum dipakai). SINKRON.

    `doc_types` opsional (comma-separated "SDD,UAT"); kosong = tebak dari dokumen.
    Menghasilkan template UAT dari outline SDD (atau sebaliknya) cuma menghasilkan
    placeholder, jadi tebakan biasanya yang benar.

    `use_llm_mapping` opsional (default False = peta bab heuristik, $0). True =
    peta bab BER-LLM (BERBAYAR — satu panggilan Claude per doc_type), berguna untuk
    template SDD asing yang nama babnya tak cocok kata kunci heuristik (kalau tidak,
    dokumennya jadi penuh placeholder). Lihat `llm_mapping_service`.
    """
    filename = file.filename or "template.docx"
    lower = filename.lower()
    if lower.endswith(".doc") and not lower.endswith(".docx"):
        raise HTTPException(
            status_code=422,
            detail="Format .doc (Word lama) belum didukung — simpan ulang sebagai .docx dulu.",
        )
    if not lower.endswith(".docx"):
        raise HTTPException(status_code=422, detail="File harus .docx")

    data = file.file.read()
    if not data:
        raise HTTPException(status_code=422, detail="File template kosong.")
    if len(data) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File template kebesaran ({len(data) // 1024 // 1024} MB). "
                   f"Batas {_MAX_UPLOAD_BYTES // 1024 // 1024} MB.",
        )

    requested_doc_types = None
    if doc_types:
        requested_doc_types = [d.strip().upper() for d in doc_types.split(",") if d.strip()]
        for dt in requested_doc_types:
            if dt not in ("SDD", "UAT"):
                raise HTTPException(status_code=422,
                                    detail=f"doc_type tidak dikenal: {dt!r} (harus SDD/UAT)")

    with tempfile.TemporaryDirectory() as tmp:
        docx_path = Path(tmp) / "upload.docx"
        docx_path.write_bytes(data)
        try:
            manifest = compile_template_from_docx(
                docx_path,
                name=name or Path(filename).stem,
                doc_types=requested_doc_types,
                use_llm_mapping=use_llm_mapping,
            )
        except (PackageNotFoundError, zipfile.BadZipFile, KeyError) as e:
            # File bukan .docx valid / rusak — kesalahan INPUT user (422), bukan
            # server. Dibedakan dari kegagalan server (pandoc dsb.) di bawah.
            raise HTTPException(
                status_code=422,
                detail=f"File bukan .docx yang valid atau rusak: {e}",
            ) from e
        except Exception as e:
            # Kegagalan sisi SERVER (mis. pandoc tak terpasang saat sintesis
            # reference.docx) — 500, bukan 422. Jangan salahkan file user.
            logger.exception("Gagal mengompilasi template upload (sisi server)")
            raise HTTPException(
                status_code=500,
                detail=f"Gagal mengompilasi template: {e}",
            ) from e

    return load_compiled_detail(manifest["template_id"])


@router.get("/{template_id}")
def get_template(template_id: str):
    """Detail template terkompilasi: manifest + rencana peta bab (untuk UI
    tinjauan pemetaan). 404 kalau bukan template hasil-upload (mis. built-in)."""
    try:
        return load_compiled_detail(template_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
