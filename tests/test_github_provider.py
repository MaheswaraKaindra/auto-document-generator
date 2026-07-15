"""Test GithubSourceProvider (Peran 1) — ingest lewat tarball.

GitHub selalu di-mock: tarball sintetis dibangun di memori, jadi test ini tidak
butuh koneksi, token, maupun jatah rate limit. Bentuk tarball-nya sengaja meniru
GitHub sungguhan, termasuk folder pembungkus `owner-repo-sha/`.
"""

import io
import tarfile
from unittest.mock import Mock, patch

import pytest
import requests

from app.domain.exceptions import SourceProviderError
from app.domain.models import GithubIngestRequest
from app.ingestion.providers import github_provider
from app.ingestion.providers.github_provider import GithubSourceProvider

_ARCHIVE_ROOT = "expressjs-express-4f0e5f6"


def _make_tarball(files: dict[str, bytes | str], root: str = _ARCHIVE_ROOT) -> bytes:
    """Bangun tarball berformat GitHub: semua isi dibungkus satu folder root."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for path, content in files.items():
            data = content.encode("utf-8") if isinstance(content, str) else content
            info = tarfile.TarInfo(name=f"{root}/{path}")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


@pytest.fixture
def fake_github(monkeypatch):
    """Ganti client PyGithub supaya tidak menyentuh jaringan."""
    repo = Mock(default_branch="main")
    repo.get_archive_link.return_value = "https://codeload.github.com/fake/tarball/main"
    client = Mock()
    client.get_repo.return_value = repo
    monkeypatch.setattr(github_provider, "Github", Mock(return_value=client))
    return repo


def _mock_download(tarball: bytes):
    response = Mock()
    response.raise_for_status = Mock()
    response.iter_content = Mock(return_value=iter([tarball]))
    return patch.object(github_provider.requests, "get", return_value=response)


def _fetch(tarball: bytes) -> "object":
    request = GithubIngestRequest(repo_tag="Backend", repo_url="https://github.com/expressjs/express")
    with _mock_download(tarball):
        return GithubSourceProvider().fetch(request)


def test_fetch_downloads_archive_in_a_single_request(fake_github):
    """Inti perbaikannya. Versi lama memanggil get_git_blob() sekali PER FILE,
    jadi repo 200 file = 200 request dan jatah anonim (60/jam) habis sebelum satu
    repo pun selesai. Berapa pun jumlah filenya, unduhan harus tetap satu kali."""
    tarball = _make_tarball({f"src/module_{i}.py": f"x = {i}" for i in range(50)})
    request = GithubIngestRequest(repo_tag="Backend", repo_url="https://github.com/expressjs/express")

    with _mock_download(tarball) as mocked_get:
        workspace = GithubSourceProvider().fetch(request)

    assert len(workspace.files) == 50
    assert mocked_get.call_count == 1
    assert not hasattr(fake_github, "get_git_blob") or not fake_github.get_git_blob.called


def test_fetch_strips_archive_root_folder(fake_github):
    """Tarball GitHub membungkus isinya dalam owner-repo-sha/. Kalau prefix itu
    ikut terbawa, file_path di Contract A berubah bentuk dan heuristik tipe file
    di parser (yang membaca path) ikut meleset."""
    workspace = _fetch(_make_tarball({"lib/express.js": "module.exports = 1"}))

    assert len(workspace.files) == 1
    assert workspace.files[0].file_path == "lib/express.js"
    assert workspace.files[0].file_name == "express.js"
    assert _ARCHIVE_ROOT not in workspace.files[0].file_path


def test_fetch_applies_the_same_filters_as_zip_upload(fake_github):
    """Workspace dari GitHub harus tidak bisa dibedakan Parser dari Workspace ZIP."""
    workspace = _fetch(
        _make_tarball(
            {
                "app/main.py": "print(1)",  # ikut
                "package.json": "{}",  # ikut (essential filename)
                "README.md": "# docs",  # dibuang: bukan source
                "node_modules/lib/index.js": "junk",  # dibuang: dir diabaikan
            }
        )
    )

    assert sorted(f.file_path for f in workspace.files) == ["app/main.py", "package.json"]


def test_fetch_skips_binary_files_without_crashing(fake_github):
    """File berekstensi source tapi isinya bukan UTF-8 harus dilewati, bukan
    meledakkan ingest seluruh repo."""
    workspace = _fetch(
        _make_tarball({"app/ok.py": "print(1)", "app/broken.py": b"\xff\xfe\x00binary"})
    )

    assert [f.file_path for f in workspace.files] == ["app/ok.py"]


def test_fetch_rejects_archive_larger_than_limit(fake_github):
    monkeypatch_target = github_provider.MAX_ARCHIVE_BYTES
    try:
        github_provider.MAX_ARCHIVE_BYTES = 10
        with pytest.raises(SourceProviderError, match="melebihi batas"):
            _fetch(_make_tarball({"app/main.py": "print(1)" * 100}))
    finally:
        github_provider.MAX_ARCHIVE_BYTES = monkeypatch_target


def test_fetch_wraps_download_failure_as_source_provider_error(fake_github):
    request = GithubIngestRequest(repo_tag="Backend", repo_url="https://github.com/expressjs/express")

    with patch.object(
        github_provider.requests, "get", side_effect=requests.ConnectionError("putus")
    ):
        with pytest.raises(SourceProviderError, match="Gagal mengunduh arsip"):
            GithubSourceProvider().fetch(request)
