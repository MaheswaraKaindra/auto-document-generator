"""Schema khusus endpoint dokumen (Peran 3). Tidak mengubah app/api/schemas.py
milik Peran 1 — file terpisah supaya tidak ada resiko konflik/campur tanggung jawab."""

from typing import Optional

from pydantic import BaseModel


class GithubRepoIn(BaseModel):
    repo_tag: str
    repo_url: str
    branch: Optional[str] = None


class GenerateDocumentRequest(BaseModel):
    """Body untuk endpoint orkestrator penuh: POST /documents/generate."""

    project_name: Optional[str] = None
    document_type: str  # "SDD" atau "UAT"
    github_token: Optional[str] = None
    repositories: list[GithubRepoIn]
