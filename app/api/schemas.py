from typing import Optional

from pydantic import BaseModel


class GithubRepoInput(BaseModel):
    repo_tag: str
    repo_url: str
    branch: Optional[str] = None


class GithubIngestBody(BaseModel):
    repos: list[GithubRepoInput]
    access_token: Optional[str] = None
