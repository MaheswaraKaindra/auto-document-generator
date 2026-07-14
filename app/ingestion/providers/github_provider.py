import base64
import re

from github import Auth, BadCredentialsException, Github, GithubException, UnknownObjectException

from app.domain.exceptions import SourceAuthError, SourceNotFoundError, SourceProviderError
from app.domain.models import GithubIngestRequest, Workspace, WorkspaceFile
from app.domain.ports import SourceProvider
from app.ingestion.filters import MAX_FILE_SIZE_BYTES, is_relevant_path


def _parse_repo_full_name(repo_url: str) -> str:
    cleaned = re.sub(r"\.git$", "", repo_url.strip().rstrip("/"))
    match = re.search(r"github\.com[/:]([^/]+/[^/]+)$", cleaned)
    if match:
        return match.group(1)
    if re.fullmatch(r"[\w.-]+/[\w.-]+", cleaned):
        return cleaned
    raise SourceNotFoundError(f"Tidak bisa mem-parsing owner/repo dari URL: {repo_url}")


class GithubSourceProvider(SourceProvider):
    """Menarik file esensial (source code + config) dari satu repositori GitHub.
    access_token boleh berasal dari PAT yang di-paste user atau dari hasil OAuth
    handshake - keduanya sama-sama diteruskan lewat GithubIngestRequest.access_token."""

    def fetch(self, request: GithubIngestRequest) -> Workspace:
        client = Github(auth=Auth.Token(request.access_token)) if request.access_token else Github()

        try:
            repo = client.get_repo(_parse_repo_full_name(request.repo_url))
            ref = request.branch or repo.default_branch
            tree = repo.get_git_tree(sha=ref, recursive=True)
        except BadCredentialsException as e:
            raise SourceAuthError(f"Token GitHub tidak valid untuk {request.repo_url}") from e
        except UnknownObjectException as e:
            raise SourceNotFoundError(f"Repository/branch tidak ditemukan: {request.repo_url}") from e
        except GithubException as e:
            raise SourceProviderError(f"GitHub API error saat mengakses {request.repo_url}: {e}") from e

        workspace = Workspace(repo_tag=request.repo_tag, source_ref=request.repo_url)
        for entry in tree.tree:
            if entry.type != "blob" or entry.size is None or entry.size > MAX_FILE_SIZE_BYTES:
                continue
            if not is_relevant_path(entry.path):
                continue

            blob = repo.get_git_blob(entry.sha)
            if blob.encoding == "base64":
                try:
                    content = base64.b64decode(blob.content).decode("utf-8")
                except UnicodeDecodeError:
                    continue
            else:
                content = blob.content

            workspace.files.append(
                WorkspaceFile(
                    file_name=entry.path.split("/")[-1],
                    file_path=entry.path,
                    content=content,
                )
            )

        return workspace
