from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.api.schemas import GithubIngestBody
from app.domain.exceptions import SourceProviderError
from app.domain.models import GithubIngestRequest, SourceType, ZipIngestRequest
from app.services.ingestion_service import IngestionService
from app.services.parser_service import build_parsed_repo_context

router = APIRouter(prefix="/ingest", tags=["ingest"])
_ingestion_service = IngestionService()


@router.post("/github")
def ingest_github(body: GithubIngestBody):
    """Menerima repo dari PAT (user paste token) maupun OAuth (token hasil /auth/github/callback) -
    keduanya lewat field access_token yang sama, karena GithubSourceProvider tidak peduli asal token."""
    requests = [
        GithubIngestRequest(
            repo_tag=r.repo_tag,
            repo_url=r.repo_url,
            branch=r.branch,
            access_token=body.access_token,
        )
        for r in body.repos
    ]
    try:
        workspaces = _ingestion_service.ingest(SourceType.GITHUB, requests)
    except SourceProviderError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    return build_parsed_repo_context(project_name="github-ingest", workspaces=workspaces)


@router.post("/zip")
def ingest_zip(files: list[UploadFile] = File(...), repo_tags: list[str] = Form(...)):
    """files dan repo_tags dipasangkan berdasarkan urutan (file ke-i -> repo_tags[i])."""
    if len(files) != len(repo_tags):
        raise HTTPException(status_code=422, detail="Jumlah files dan repo_tags harus sama")

    requests = [
        ZipIngestRequest(repo_tag=tag, filename=file.filename, zip_bytes=file.file.read())
        for file, tag in zip(files, repo_tags)
    ]
    try:
        workspaces = _ingestion_service.ingest(SourceType.ZIP_UPLOAD, requests)
    except SourceProviderError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    return build_parsed_repo_context(project_name="zip-ingest", workspaces=workspaces)
