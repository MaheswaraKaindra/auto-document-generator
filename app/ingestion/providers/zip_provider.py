import io
import zipfile

from app.domain.exceptions import SourceNotFoundError, SourceProviderError
from app.domain.models import Workspace, WorkspaceFile, ZipIngestRequest
from app.domain.ports import SourceProvider
from app.ingestion.filters import (
    MAX_FILE_SIZE_BYTES,
    MAX_TOTAL_FILES,
    MAX_TOTAL_UNCOMPRESSED_BYTES,
    is_relevant_path,
)


class ZipUploadProvider(SourceProvider):
    """Mengekstrak file esensial dari satu ZIP yang di-upload user, langsung di memori
    (tidak ditulis ke disk). Menerapkan filter yang sama dengan GithubSourceProvider
    supaya hasilnya (Workspace) tidak bisa dibedakan oleh Parser dari sumber lain."""

    def fetch(self, request: ZipIngestRequest) -> Workspace:
        try:
            archive = zipfile.ZipFile(io.BytesIO(request.zip_bytes))
        except zipfile.BadZipFile as e:
            raise SourceNotFoundError(f"File ZIP tidak valid/rusak: {request.filename}") from e

        # Saring DULU, cacah belakangan — sama seperti jalur tarball GitHub.
        # info.file_size dibaca dari header ZIP (gratis, tanpa ekstraksi), jadi
        # menyaring duluan tidak mengurangi perlindungan: yang berbahaya itu
        # archive.read() di bawah. Versi sebelumnya mencacah seluruh isi arsip,
        # sehingga ZIP berisi banyak dokumentasi/gambar ditolak karena "terlalu
        # banyak file" padahal kode produknya sedikit. Lihat catatan di filters.py.
        relevant = [
            info
            for info in archive.infolist()
            if not info.is_dir()
            and info.file_size <= MAX_FILE_SIZE_BYTES
            and is_relevant_path(info.filename)
        ]
        if len(relevant) > MAX_TOTAL_FILES:
            raise SourceProviderError(
                f"{request.filename}: terlalu banyak file relevan ({len(relevant)} > {MAX_TOTAL_FILES})"
            )
        total_size = sum(info.file_size for info in relevant)
        if total_size > MAX_TOTAL_UNCOMPRESSED_BYTES:
            raise SourceProviderError(
                f"{request.filename}: ukuran total setelah extract terlalu besar ({total_size} bytes)"
            )

        workspace = Workspace(repo_tag=request.repo_tag, source_ref=request.filename)
        with archive:
            for info in relevant:
                path = info.filename
                try:
                    content = archive.read(info).decode("utf-8")
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
