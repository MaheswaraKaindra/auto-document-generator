from dataclasses import replace

from app.domain.models import SourceType, Workspace
from app.ingestion.filters import ESSENTIAL_FILENAMES
from app.ingestion.manifest import find_product_paths, is_product_path
from app.ingestion.provider_factory import get_provider


def narrow_to_product(workspace: Workspace) -> Workspace:
    """Buang file yang bukan bagian dari produk yang dikirim repo ini.

    Dijalankan SETELAH provider selesai, bukan di dalamnya, karena keputusannya
    butuh melihat seluruh isi repo (manifest-nya salah satu file). Ditaruh di
    sini supaya jalur GitHub dan ZIP tunduk pada aturan yang sama — Workspace
    dari keduanya harus tidak bisa dibedakan oleh Parser.

    Kalau manifest tidak memberi jawaban, workspace dikembalikan APA ADANYA.
    Lihat app/ingestion/manifest.py untuk alasan lengkap gagal-membuka.
    """
    path_to_content = {f.file_path: f.content for f in workspace.files}
    roots = find_product_paths(path_to_content)
    if not roots:
        return workspace

    kept = [
        f
        for f in workspace.files
        # Manifest di root tetap disimpan walau di luar root produk: dari situ
        # LLM tahu dependency dan nama proyeknya.
        if is_product_path(f.file_path, roots) or f.file_path in ESSENTIAL_FILENAMES
    ]
    if not kept:
        return workspace  # deteksi meleset total -> jangan buang apa pun

    return replace(workspace, files=kept)


class IngestionService:
    def __init__(self, provider_lookup=get_provider):
        self._provider_lookup = provider_lookup

    def ingest(self, source_type: SourceType, requests: list) -> list[Workspace]:
        provider = self._provider_lookup(source_type)
        return [narrow_to_product(provider.fetch(request)) for request in requests]
