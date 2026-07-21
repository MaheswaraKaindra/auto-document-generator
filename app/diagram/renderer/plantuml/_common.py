"""Helper kecil bersama untuk renderer PlantUML — kutip & pembersihan label.

Renderer PlantUML sengaja meng-emit STRUKTUR saja (tanpa `!theme`/`skinparam`):
gaya visual disuntik terpusat oleh compiler_service._normalize_plantuml (theme +
dpi), sama seperti perlakuan pada PlantUML karangan LLM. Jadi output renderer ini
masuk ke jalur render yang SAMA tanpa perubahan.
"""
from __future__ import annotations


def q(label: str) -> str:
    """Bungkus label dengan kutip ganda (PlantUML mewajibkannya untuk label
    ber-spasi/karakter khusus); escape kutip ganda di dalamnya."""
    return '"' + (label or "").replace('"', "'").replace("\n", " ").strip() + '"'


def action_label(label: str) -> str:
    """Teks aksi activity `:...;`. Buang `;` (penutup pernyataan PlantUML) dan
    newline supaya tidak merusak sintaks."""
    return (label or "").replace(";", ",").replace("\n", " ").strip()


def condition(label: str) -> str:
    """Teks kondisi keputusan untuk `if (...)`. Hilangkan tanda kurung (merusak
    pembungkus kondisi) & newline; pastikan diakhiri `?` sesuai konvensi."""
    text = (label or "").replace("(", " ").replace(")", " ").replace("\n", " ").strip()
    if not text:
        return "?"
    return text if text.endswith("?") else text + "?"


def branch(guard: str | None) -> str:
    """Bagian `(guard)` sesudah `then`/`else`. Kembalikan ` (guard)` atau `` (string
    kosong) kalau tak ada guard — tidak mengarang label cabang yang tak diberikan."""
    g = (guard or "").replace("(", " ").replace(")", " ").replace("\n", " ").strip()
    return f" ({g})" if g else ""
