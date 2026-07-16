import io
import re
import tarfile

import requests
from github import Auth, BadCredentialsException, Github, GithubException, UnknownObjectException

from app.domain.exceptions import SourceAuthError, SourceNotFoundError, SourceProviderError
from app.domain.models import GithubIngestRequest, Workspace, WorkspaceFile
from app.domain.ports import SourceProvider
from app.ingestion.filters import (
    MAX_FILE_SIZE_BYTES,
    MAX_TOTAL_FILES,
    MAX_TOTAL_UNCOMPRESSED_BYTES,
    is_relevant_path,
)

# Tarball terkompresi. Repo yang lebih besar dari ini hampir pasti bukan target
# realistis produk ini, dan menolaknya lebih baik daripada menghabiskan memori.
MAX_ARCHIVE_BYTES = 100_000_000

_ARCHIVE_TIMEOUT_SECONDS = 180


def _parse_repo_full_name(repo_url: str) -> str:
    cleaned = re.sub(r"\.git$", "", repo_url.strip().rstrip("/"))
    match = re.search(r"github\.com[/:]([^/]+/[^/]+)$", cleaned)
    if match:
        return match.group(1)
    if re.fullmatch(r"[\w.-]+/[\w.-]+", cleaned):
        return cleaned
    raise SourceNotFoundError(f"Tidak bisa mem-parsing owner/repo dari URL: {repo_url}")


def _strip_archive_root(member_name: str) -> str:
    """Buang folder pembungkus tarball GitHub.

    Isi tarball selalu dibungkus TEPAT SATU folder root, jadi
    `expressjs-express-4f0e5f6/lib/express.js` harus jadi `lib/express.js`.
    Nama folder itu sendiri tidak konsisten — endpoint API memberi
    `owner-repo-sha`, URL arsip web memberi `repo-branch` — makanya yang dibuang
    komponen path pertama apa pun namanya, bukan pola nama tertentu.

    Kalau prefix ini tidak dibuang, file_path di Contract A berubah bentuk dan
    heuristik tipe file di parser (yang membaca path) ikut meleset.
    """
    _, _, rest = member_name.partition("/")
    return rest


def _download_archive(url: str, repo_url: str) -> bytes:
    """Unduh tarball repo dalam SATU request.

    Ini menggantikan pendekatan lama yang memanggil get_git_blob() sekali per
    file. Repo 200 file dulu berarti 200 request berurutan — lambat, dan batas
    anonim GitHub (60 request/jam) habis sebelum satu repo pun selesai.
    """
    try:
        response = requests.get(url, timeout=_ARCHIVE_TIMEOUT_SECONDS, stream=True)
        response.raise_for_status()
    except requests.RequestException as e:
        raise SourceProviderError(f"Gagal mengunduh arsip {repo_url}: {e}") from e

    chunks = []
    total = 0
    for chunk in response.iter_content(chunk_size=1 << 16):
        total += len(chunk)
        if total > MAX_ARCHIVE_BYTES:
            response.close()
            raise SourceProviderError(
                f"Arsip {repo_url} melebihi batas {MAX_ARCHIVE_BYTES} byte."
            )
        chunks.append(chunk)
    return b"".join(chunks)


class GithubSourceProvider(SourceProvider):
    """Menarik file esensial (source code + config) dari satu repositori GitHub.

    Mengunduh tarball repo sekali jalan lalu membongkarnya di memori, bukan
    mengambil file satu per satu lewat API. access_token boleh berasal dari PAT
    yang di-paste user atau dari hasil OAuth handshake - keduanya sama-sama
    diteruskan lewat GithubIngestRequest.access_token.
    """

    @staticmethod
    def _not_found(request: GithubIngestRequest) -> str:
        """Pesan untuk 404 GitHub.

        GitHub membalas **404 untuk dua hal yang sangat berbeda**: repo yang memang
        tidak ada, DAN repo privat yang tidak bisa diakses pemanggil. Itu disengaja
        — 403 akan membocorkan bahwa repo privat itu ada. Jadi dari luar keduanya
        MUSTAHIL dibedakan, dan pesan lama ("Repository/branch tidak ditemukan")
        memilih salah satu lalu menyembunyikan yang lain.

        Akibatnya bukan sekadar kurang informatif — dia mengarahkan ke perbaikan
        yang SALAH: pengguna disuruh mencurigai URL-nya, padahal URL itu biasanya
        disalin dari browser sendiri (jadi pasti ada) dan yang kurang cuma token.
        Terjadi di gladi bersih pertama, pada percobaan pertama.

        Yang tidak bisa kita ketahui: repo-nya ada atau tidak. Yang KITA TAHU:
        token diberikan atau tidak — dan itu mengubah saran yang benar.
        """
        target = f"{request.repo_url} (branch: {request.branch})" if request.branch else request.repo_url
        if not request.access_token:
            return (
                f"Tidak bisa mengakses {target}. GitHub membalas 404, dan itu berarti SALAH SATU "
                f"dari dua hal: repo-nya memang tidak ada, ATAU repo-nya privat dan permintaan ini "
                f"tanpa token. Keduanya terlihat sama dari luar — GitHub sengaja tidak "
                f"membedakannya. Kalau repo ini privat, isi GitHub Token (Personal Access Token) "
                f"dengan scope `repo`."
            )
        return (
            f"Tidak bisa mengakses {target} walau token diberikan. Berarti SALAH SATU dari: "
            f"URL/branch-nya salah ketik, atau token-nya tidak punya akses ke repo ini "
            f"(repo privat butuh scope `repo`; token milik akun yang bukan anggota org juga "
            f"akan ditolak)."
        )

    def fetch(self, request: GithubIngestRequest) -> Workspace:
        client = Github(auth=Auth.Token(request.access_token)) if request.access_token else Github()


        try:
            repo = client.get_repo(_parse_repo_full_name(request.repo_url))
            ref = request.branch or repo.default_branch
            archive_url = repo.get_archive_link("tarball", ref)
        except BadCredentialsException as e:
            raise SourceAuthError(f"Token GitHub tidak valid untuk {request.repo_url}") from e
        except UnknownObjectException as e:
            raise SourceNotFoundError(self._not_found(request)) from e
        except GithubException as e:
            raise SourceProviderError(f"GitHub API error saat mengakses {request.repo_url}: {e}") from e

        archive_bytes = _download_archive(archive_url, request.repo_url)

        try:
            archive = tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:gz")
        except tarfile.TarError as e:
            raise SourceProviderError(f"Arsip {request.repo_url} tidak bisa dibuka: {e}") from e

        workspace = Workspace(repo_tag=request.repo_tag, source_ref=request.repo_url)
        seen_files = 0
        total_size = 0

        with archive:
            for member in archive:
                if not member.isfile():
                    continue

                path = _strip_archive_root(member.name)
                if not path or member.size > MAX_FILE_SIZE_BYTES or not is_relevant_path(path):
                    continue

                # Guard dihitung SESUDAH filter relevansi, sebelum extractfile().
                # member.size dibaca dari header tar (gratis, tanpa ekstraksi),
                # jadi menyaring duluan tidak mengurangi perlindungan sama sekali
                # — yang berbahaya justru extractfile() di bawah. Sebelumnya
                # pencacahnya di atas sini, jadi monorepo ditolak karena punya
                # banyak dokumentasi/gambar. Lihat catatan di filters.py.
                seen_files += 1
                if seen_files > MAX_TOTAL_FILES:
                    raise SourceProviderError(
                        f"{request.repo_url}: terlalu banyak file relevan (> {MAX_TOTAL_FILES})"
                    )
                total_size += member.size
                if total_size > MAX_TOTAL_UNCOMPRESSED_BYTES:
                    raise SourceProviderError(
                        f"{request.repo_url}: ukuran total setelah extract terlalu besar"
                    )

                extracted = archive.extractfile(member)
                if extracted is None:
                    continue
                try:
                    content = extracted.read().decode("utf-8")
                except UnicodeDecodeError:
                    continue

                workspace.files.append(
                    WorkspaceFile(
                        file_name=path.split("/")[-1],
                        file_path=path,
                        content=content,
                    )
                )

        return workspace
