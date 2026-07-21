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


def test_irrelevant_files_do_not_count_against_the_file_limit(fake_github, monkeypatch):
    """Guard anti-bomb harus mencacah yang DIAMBIL, bukan seluruh isi arsip.

    Ini bug yang menolak monorepo nyata di pintu: diukur pada medusa, 22.966
    member file tapi cuma 9.459 yang relevan (41%) — sisanya dokumentasi dan
    gambar. Versi lama mencacah dulu lalu menyaring belakangan, jadi repo ditolak
    karena punya banyak dokumentasi, bukan karena punya banyak kode.
    """
    monkeypatch.setattr(github_provider, "MAX_TOTAL_FILES", 5)
    files = {f"docs/img/shot_{i}.png": f"pretend-binary-{i}" for i in range(50)}
    files["app/main.py"] = "print(1)"

    workspace = _fetch(_make_tarball(files))

    assert [f.file_path for f in workspace.files] == ["app/main.py"]


def test_too_many_relevant_files_still_rejected(fake_github, monkeypatch):
    """Pasangan test di atas: batasnya tetap ditegakkan untuk file yang benar-benar
    diambil. Tanpa ini, test di atas bisa lolos dengan cara menghapus guard-nya."""
    monkeypatch.setattr(github_provider, "MAX_TOTAL_FILES", 5)

    with pytest.raises(SourceProviderError, match="terlalu banyak file relevan"):
        _fetch(_make_tarball({f"app/mod_{i}.py": f"x = {i}" for i in range(20)}))


def test_irrelevant_file_bytes_do_not_count_against_the_size_limit(fake_github, monkeypatch):
    """Sama untuk batas byte: yang dihitung harus yang diekstrak. member.size
    dibaca dari header tar (gratis), jadi menyaring duluan tidak mengurangi
    perlindungan — yang berbahaya itu extractfile()."""
    monkeypatch.setattr(github_provider, "MAX_TOTAL_UNCOMPRESSED_BYTES", 200)
    files = {f"docs/img/big_{i}.png": "x" * 500 for i in range(20)}  # 10 KB tak relevan
    files["app/main.py"] = "print(1)"

    workspace = _fetch(_make_tarball(files))

    assert [f.file_path for f in workspace.files] == ["app/main.py"]


def test_fetch_wraps_download_failure_as_source_provider_error(fake_github):
    request = GithubIngestRequest(repo_tag="Backend", repo_url="https://github.com/expressjs/express")

    with patch.object(
        github_provider.requests, "get", side_effect=requests.ConnectionError("putus")
    ):
        with pytest.raises(SourceProviderError, match="Gagal mengunduh arsip"):
            GithubSourceProvider().fetch(request)


# --- Pesan 404: repo privat vs repo tidak ada ---------------------------------
#
# GitHub membalas 404 untuk DUA hal yang sangat berbeda — repo yang memang tidak
# ada, dan repo privat yang tidak bisa diakses pemanggil — dan itu DISENGAJA (403
# akan membocorkan bahwa repo privat itu ada). Diverifikasi langsung ke GitHub:
# repo Labpro-22 yang privat -> 404, repo karangan -> 404. Identik.
#
# Pesan lama ("Repository/branch tidak ditemukan") memilih salah satu sebab lalu
# menyembunyikan yang lain, sehingga pengguna disuruh mencurigai URL-nya —
# padahal URL itu biasanya disalin dari browser sendiri (jadi pasti ada) dan yang
# kurang cuma token. Ini menabrak pengguna pertama pada percobaan pertama, di
# gladi bersih demo.
#
# Yang tidak bisa kita ketahui: repo-nya ada atau tidak. Yang KITA TAHU: token
# diberikan atau tidak — dan itulah yang mengubah saran yang benar.


def _not_found_message(**kwargs) -> str:
    request = GithubIngestRequest(
        repo_tag="Backend", repo_url="https://github.com/org/repo-privat", **kwargs
    )
    return GithubSourceProvider._not_found(request)


def test_not_found_without_token_points_at_the_token():
    """Tanpa token, sebab yang PALING MUNGKIN adalah repo privat — dan itu yang
    bisa ditindaklanjuti pengguna. Pesannya harus menyebut token."""
    message = _not_found_message()

    assert "token" in message.lower()
    assert "privat" in message.lower()


def test_not_found_without_token_still_admits_it_may_not_exist():
    """Tapi JANGAN berbohong ke arah sebaliknya: kita betul-betul tidak tahu
    repo-nya ada atau tidak. Menyebut 'pasti privat' sama menyesatkannya dengan
    'pasti tidak ada' — cuma ke arah yang berlawanan."""
    message = _not_found_message()

    assert "tidak ada" in message.lower()


def test_not_found_with_token_stops_blaming_the_missing_token():
    """Token sudah diberikan -> menyarankan 'isi token' jadi omong kosong.
    Sarannya bergeser ke salah ketik atau scope token."""
    message = _not_found_message(access_token="ghp_x")

    assert "scope" in message.lower() or "salah ketik" in message.lower()
    assert "isi GitHub Token" not in message


def test_not_found_names_the_branch_when_one_was_given():
    """Branch yang salah juga menghasilkan 404. Kalau pengguna mengisi branch,
    itu tersangka yang nyata dan harus terlihat di pesannya."""
    message = _not_found_message(branch="dev", access_token="ghp_x")

    assert "dev" in message


def test_not_found_message_reaches_the_caller(fake_github):
    """Penjaga rantai: pesannya harus benar-benar sampai ke SourceNotFoundError,
    bukan cuma benar di dalam fungsinya sendiri."""
    from github import UnknownObjectException

    from app.domain.exceptions import SourceNotFoundError

    fake_github.get_archive_link.side_effect = UnknownObjectException(404, {}, {})
    request = GithubIngestRequest(repo_tag="Backend", repo_url="https://github.com/org/x")

    with pytest.raises(SourceNotFoundError) as excinfo:
        GithubSourceProvider().fetch(request)

    assert "token" in str(excinfo.value).lower()
