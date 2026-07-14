from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class SourceType(str, Enum):
    GITHUB = "github"
    ZIP_UPLOAD = "zip_upload"


@dataclass
class WorkspaceFile:
    file_name: str
    file_path: str
    content: str


@dataclass
class Workspace:
    repo_tag: str
    source_ref: str
    files: list[WorkspaceFile] = field(default_factory=list)


@dataclass
class GithubIngestRequest:
    repo_tag: str
    repo_url: str
    branch: Optional[str] = None
    access_token: Optional[str] = None


@dataclass
class ZipIngestRequest:
    repo_tag: str
    filename: str
    zip_bytes: bytes
