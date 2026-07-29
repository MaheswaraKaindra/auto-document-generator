"""Halaman Kebijakan Privasi & Syarat-Ketentuan (#16).

Disajikan dari backend, bukan dari SPA, karena dua alasan praktis: halaman ini
harus bisa dibuka TANPA login (calon pelanggan membacanya sebelum mendaftar), dan
harus punya URL sendiri yang bisa ditautkan dari mana saja — sementara frontend
produk ini satu halaman tanpa router.

Isinya HTML statis di `app/legal/`. Satu-satunya logika di sini adalah spanduk
"draf" yang muncul sendiri selama masih ada penanda `[ISI: ...]` yang belum
diganti — lihat `_render`.
"""
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["legal"])

_LEGAL_DIR = Path(__file__).resolve().parent.parent / "legal"

# Penanda yang ditinggalkan penulis draf untuk fakta yang tak bisa diketahui dari
# kode: nama badan usaha, yurisdiksi, kontak. Kehadirannya = dokumen ini belum
# selesai.
_PLACEHOLDER = "[ISI:"

# Titik sisip di berkas HTML. Ada supaya spanduk bisa disisipkan tanpa menebak
# struktur dokumen (mis. mencari `<body>` dengan regex).
_SLOT = "<!--DRAF-->"

_BANNER = (
    '<div class="draf"><strong>Dokumen ini masih draf.</strong> Sebagian isian '
    'yang ditandai kuning belum diganti dengan data sebenarnya, dan teksnya belum '
    'ditinjau secara hukum. Jangan jadikan halaman ini dasar keputusan apa pun.'
    "</div>"
)


def _render(nama: str) -> HTMLResponse:
    """Muat halaman, sisipkan spanduk kalau masih ada penanda yang belum diisi.

    Spanduknya OTOMATIS, bukan ditulis manual di berkas HTML, dan itu inti
    rancangan kecil ini: spanduk manual punya dua cara gagal yang dua-duanya
    memalukan — lupa memasangnya saat menerbitkan draf, atau lupa menghapusnya
    sesudah teksnya final. Diturunkan dari isi dokumen, keduanya mustahil: ia
    hilang sendiri tepat ketika penanda terakhir diisi.
    """
    path = _LEGAL_DIR / nama
    if not path.exists():
        # 404 dengan pesan yang menyebut berkasnya: kalau ini terjadi di
        # produksi, penyebabnya hampir pasti berkas yang tak ikut ter-COPY ke
        # image — dan pesan generik akan menyembunyikan itu.
        logger.error("Halaman legal tak ditemukan: %s", path)
        raise HTTPException(status_code=404, detail=f"Halaman {nama} tidak tersedia.")

    html = path.read_text(encoding="utf-8")
    banner = _BANNER if _PLACEHOLDER in html else ""
    return HTMLResponse(html.replace(_SLOT, banner))


@router.get("/privacy", response_class=HTMLResponse)
def privacy_policy():
    """Kebijakan Privasi. Publik — sengaja tanpa `get_current_user`: orang harus
    bisa membaca apa yang terjadi pada datanya SEBELUM menyerahkan data apa pun."""
    return _render("privacy.html")


@router.get("/terms", response_class=HTMLResponse)
def terms_of_service():
    """Syarat & Ketentuan. Publik, alasan yang sama dengan /privacy."""
    return _render("terms.html")
