"""Endpoint dokumen (Peran 3 — Backend & Templating).

Tidak mengubah kode Peran 1 (parser_service.py, ingestion_service.py) atau
Peran 2 (llm_service.py) — hanya mengimpor & memanggil apa yang sudah
mereka sediakan."""

import base64
import logging
from typing import Callable

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse

from app.api.deps import get_current_user
from app.services import auth_service
from app.services.auth_service import Principal

from app.api.schemas_document import GenerateDocumentRequest, ZipFileIn
from app.domain.exceptions import (
    ContextWindowExceededError,
    DiagramRenderError,
    DocumentTruncatedError,
    PandocUnavailableError,
    SourceProviderError,
)
from app.domain.models import GithubIngestRequest, SourceType, ZipIngestRequest
from app.services import job_store
from app.services import compiler_service
from app.services.compiler_service import decode_logo, generate_docx, validate_template
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
        logger.exception("Gagal merender diagram PlantUML")
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


def _decode_zip_files(zip_files: list[ZipFileIn]) -> list[ZipIngestRequest]:
    """base64 (dari JSON) -> ZipIngestRequest berisi bytes, divalidasi SINKRON.

    Prinsip yang sama dengan decode_logo: base64 rusak ditolak 422 saat POST,
    sebelum job dibuat & jauh sebelum LLM berbayar. Isi ZIP-nya sendiri (struktur,
    zip-bomb) tetap divalidasi di lapisan ingestion (SourceProviderError -> 422 di
    job) — sama seperti repo GitHub yang gagal diambil."""
    requests = []
    for zf in zip_files:
        payload = zf.zip_base64.strip()
        # data-URL dari browser ("data:application/zip;base64,...") — buang prefiks.
        if payload.startswith("data:"):
            payload = payload.partition(",")[2]
        try:
            raw = base64.b64decode(payload, validate=True)
        except ValueError as e:
            raise ValueError(f"ZIP '{zf.repo_tag}' bukan base64 yang valid.") from e
        if not raw:
            raise ValueError(f"ZIP '{zf.repo_tag}' kosong.")
        requests.append(
            ZipIngestRequest(repo_tag=zf.repo_tag, filename=zf.filename, zip_bytes=raw)
        )
    return requests


def _run_generation(
    job_id: str,
    body: GenerateDocumentRequest,
    logo_bytes: bytes | None = None,
    zip_requests: list[ZipIngestRequest] | None = None,
) -> None:
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
        output_path = _generate_document(
            doc_type,
            body,
            logo_bytes=logo_bytes,
            on_progress=lambda text: job_store.set_progress(job_id, text),
            zip_requests=zip_requests,
        )
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
        logger.exception("Gagal merender diagram PlantUML")
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
    body: GenerateDocumentRequest, background_tasks: BackgroundTasks,
    principal: Principal = Depends(get_current_user),
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

    # Prinsip yang sama untuk pilihan template: kombinasi template x jenis
    # dokumen yang tidak tersedia ditolak SEKARANG, bukan jadi job gagal.
    try:
        validate_template(body.template_id, doc_type)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    # Prinsip yang sama untuk logo: decode + validasi gambar itu murah, jadi
    # file yang rusak/kebesaran ditolak 422 di sini — SEBELUM job dibuat dan
    # jauh sebelum ada panggilan LLM berbayar.
    logo_bytes = None
    if body.logo_base64:
        try:
            logo_bytes = decode_logo(body.logo_base64)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e

    # Jalur ZIP: base64 didecode SINKRON (base64 rusak = 422 sekarang, sebelum job
    # & LLM). Kalau ada, ZIP jadi sumber kode; kalau tidak, jatuh ke GitHub.
    zip_requests = None
    if body.zip_files:
        try:
            zip_requests = _decode_zip_files(body.zip_files)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e

    job_id = job_store.create_job(
        document_type=doc_type,
        project_name=body.project_name,
        template_id=body.template_id,
        owner=principal.id,
    )
    background_tasks.add_task(_run_generation, job_id, body, logo_bytes, zip_requests)
    return {
        "job_id": job_id,
        "status": job_store.STATUS_QUEUED,
        "status_url": f"/documents/jobs/{job_id}",
    }


def _job_payload(job: dict) -> dict:
    """Bentuk job untuk klien — dipakai status detail DAN daftar "Dokumen Saya",
    satu sumber supaya keduanya tak menyimpang. `download_url`/`diagrams_url` cuma
    disertakan kalau file-nya benar-benar ada (menawarkan tautan yang berujung
    404 lebih buruk daripada tak menawarkan)."""
    payload = {
        "job_id": job["id"],
        "status": job["status"],
        "document_type": job["document_type"],
        # Gaya dokumen — riwayat dulu tak bisa menjawab "dokumen ini gaya apa".
        # None untuk job dari DB lama (sebelum kolomnya ada).
        "template_id": job["template_id"],
        "project_name": job["project_name"],
        # Tahap yang sedang dikerjakan, kalimat siap tampil.
        "progress": job["progress"],
        "created_at": job["created_at"],
        "updated_at": job["updated_at"],
    }
    if job["status"] == job_store.STATUS_DONE:
        payload["download_url"] = f"/documents/jobs/{job['id']}/download"
        if compiler_service.drawio_bundle_for(job["docx_path"]).exists():
            payload["diagrams_url"] = f"/documents/jobs/{job['id']}/diagrams"
    elif job["status"] == job_store.STATUS_FAILED:
        payload["error"] = job["error"]
        payload["error_status"] = job["error_status"]
    return payload


@router.get("/jobs")
def list_my_jobs(principal: Principal = Depends(get_current_user)):
    """Riwayat dokumen milik pemanggil — "Dokumen Saya", terbaru dulu.

    Owner-scoped di query (`job_store.list_jobs`), jadi tak pernah menyentuh
    dokumen pengguna lain. Dideklarasikan SEBELUM `/jobs/{job_id}` supaya path
    literal "/jobs" tak tertelan sebagai job_id."""
    job_store.reap_stale_jobs()
    job_store.purge_expired_documents()
    jobs = job_store.list_jobs(principal.id)
    return {"jobs": [_job_payload(job) for job in jobs]}


@router.get("/jobs/{job_id}")
def get_job_status(job_id: str, principal: Principal = Depends(get_current_user)):
    """Status job. 200 walau job-nya gagal — pertanyaannya ("job ini bagaimana?")
    berhasil dijawab; kegagalan generation-nya ada di dalam payload, lengkap
    dengan `error_status` supaya klien tahu ini kegagalan permanen atau bukan."""
    # Pungut job basi lebih dulu: kalau proses yang menjalankan job ini mati
    # (restart/OOM/worker crash), tanpa ini job tergantung di `running` selamanya
    # dan klien polling tanpa akhir. Sapuan murah (tabel job kecil) & idempoten;
    # job yang ditanya di sini yang paling mungkin sedang dipoll, jadi ini titik
    # paling tepat untuk deteksi lazy pada job milik worker yang mati.
    job_store.reap_stale_jobs()
    job_store.purge_expired_documents()
    job = job_store.get_job(job_id)
    # 404 (bukan 403) untuk job milik orang lain: samakan dengan "tidak ada" supaya
    # keberadaan job orang lain tak bocor lewat beda kode status.
    if job is None or not auth_service.owns(job.get("owner"), principal):
        raise HTTPException(status_code=404, detail=f"Job {job_id} tidak ditemukan.")
    return _job_payload(job)


@router.get("/jobs/{job_id}/download")
def download_job_document(job_id: str, principal: Principal = Depends(get_current_user)):
    job = job_store.get_job(job_id)
    if job is None or not auth_service.owns(job.get("owner"), principal):
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


@router.get("/jobs/{job_id}/diagrams")
def download_job_diagrams(job_id: str, principal: Principal = Depends(get_current_user)):
    """Bundel `.drawio` activity diagram dokumen ini — versi yang bisa DISUNTING.

    Gambar di dokumen digambar dari geometri yang dihitung sendiri
    (`app/diagram/activity_render.py`), jadi file suntingan ini lahir dari
    koordinat yang SAMA — bentuknya mustahil berbeda dari yang tercetak. Gunanya:
    diagram yang 90% benar bisa dirapikan tangan di draw.io tanpa menggambar
    ulang dari nol.

    404 kalau job tak ada ATAU dokumennya memang tak punya activity diagram
    (UAT, atau SDD yang diagramnya jatuh ke jalur PlantUML).
    """
    job = job_store.get_job(job_id)
    if job is None or not auth_service.owns(job.get("owner"), principal):
        raise HTTPException(status_code=404, detail=f"Job {job_id} tidak ditemukan.")
    if job["status"] != job_store.STATUS_DONE:
        raise HTTPException(
            status_code=409,
            detail=f"Job {job_id} belum selesai (status: {job['status']}).",
        )
    bundle = compiler_service.drawio_bundle_for(job["docx_path"])
    if not bundle.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} tidak punya activity diagram yang bisa disunting.",
        )
    return FileResponse(bundle, media_type="application/zip",
                        filename=f"activity-diagrams-{job_id[:8]}.zip")


def _describe_parsed(parsed_repo_context: dict) -> str:
    """Ringkasan Contract A dalam kalimat untuk pengguna.

    Angkanya diambil dari repo PENGGUNA, dan itu intinya: muncul di detik ke-5,
    dan jadi bukti pertama bahwa sistem benar-benar membaca kodenya — sebelum
    LLM menulis sebaris pun. Tanpa ini, dua menit pertama cuma angka berjalan
    yang tidak bisa dibedakan dari hang.
    """
    files = [f for repo in parsed_repo_context["repositories"] for f in repo["files"]]
    endpoints = sum(len(f["api_endpoints"]) for f in files)
    classes = sum(len(f["classes"]) for f in files)
    return f"Membaca kode: {len(files)} file, {endpoints} endpoint, {classes} class."


def _generate_document(
    doc_type: str,
    body: GenerateDocumentRequest,
    logo_bytes: bytes | None = None,
    on_progress: Callable[[str], None] = lambda _: None,
    zip_requests: list[ZipIngestRequest] | None = None,
) -> str:
    """Pipeline murni: tidak tahu-menahu soal job maupun HTTP.

    Dipisah dari _run_generation supaya yang satu mengurus PEKERJAAN dan yang
    lain mengurus KEGAGALAN — tanpa ini, tujuh blok except membungkus tiga puluh
    baris orkestrasi dan keduanya jadi sulit dibaca.

    `on_progress` sengaja callback, bukan `job_store` yang diimpor langsung:
    fungsi ini tidak boleh tahu job disimpan di mana, sama seperti dia tidak tahu
    soal HTTP. Default no-op supaya pemanggil yang tidak peduli (mis. test) tidak
    perlu menyediakan apa pun.
    """
    # Exception dibiarkan naik apa adanya — _run_generation yang memetakannya ke
    # kode HTTP dan menyimpannya ke job. Fungsi ini sengaja tidak tahu HTTP.
    # Dua sumber kode yang saling menggantikan: ZIP (kalau di-upload) atau GitHub.
    if zip_requests:
        on_progress(f"Membongkar {len(zip_requests)} berkas ZIP...")
        workspaces = _ingestion_service.ingest(SourceType.ZIP_UPLOAD, zip_requests)
    else:
        ingest_requests = [
            GithubIngestRequest(
                repo_tag=r.repo_tag,
                repo_url=r.repo_url,
                branch=r.branch,
                access_token=body.github_token,
            )
            for r in body.repositories
        ]
        on_progress(f"Mengunduh {len(ingest_requests)} repo dari GitHub...")
        workspaces = _ingestion_service.ingest(SourceType.GITHUB, ingest_requests)

    parsed_repo_context = build_parsed_repo_context(
        project_name=body.project_name or "generated-project",
        workspaces=workspaces,
    )
    on_progress(_describe_parsed(parsed_repo_context))

    # Tahap terlama: ~72% dari total. Sebutkan perkiraannya — menunggu dua menit
    # itu wajar kalau tahu itu dua menit, dan menyiksa kalau tidak tahu.
    on_progress("Menganalisis dengan AI dan menyusun isi dokumen... (~2 menit)")
    document_content = _llm_service.generate_document_content(
        parsed_repo_context=parsed_repo_context,
        target_doc_type=doc_type,
    )

    diagrams = document_content.get("diagrams") or {}
    # +4 = arsitektur, integrasi komponen, flow proses bisnis, use case
    n_diagrams = len(diagrams.get("activity_diagrams") or []) + 4
    on_progress(f"Menggambar {n_diagrams} diagram lalu menyusun .docx...")
    try:
        return generate_docx(
            doc_type,
            document_content,
            project_name=body.project_name or "",
            document_metadata=(
                body.document_metadata.model_dump() if body.document_metadata else None
            ),
            logo_bytes=logo_bytes,
            template_id=body.template_id,
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
