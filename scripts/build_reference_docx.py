"""CLI: regenerasi `app/templates/reference.docx` (kerangka TAMPILAN PREMCO).

    python scripts/build_reference_docx.py

Logika sintesisnya ADA DI `app/services/reference_synthesis_service.py` — dipindah
ke service (2026-07-19) karena runtime V2 (kompilasi template yang di-upload user)
memanggilnya juga untuk mensintesis reference per-template. Script ini cuma
pembungkus CLI supaya reference.docx ter-commit bisa diregenerasi dari terminal.

Kenapa reference.docx tetap KODE (bukan .docx biner misterius di repo): lihat
docstring service. Binernya tetap ikut repo supaya `pip install` saja cukup.
"""
import sys
from pathlib import Path

# Script ini di scripts/, jadi repo root = parent.parent — masukkan ke path supaya
# `app` bisa diimpor tanpa install editable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.reference_synthesis_service import build_reference  # noqa: E402

if __name__ == "__main__":
    path = build_reference()
    print(f"reference.docx dibangun: {path} ({path.stat().st_size / 1024:.0f} KB)")
    print("Jalankan pytest — ada test yang menjaga style Pandoc tidak ikut rusak.")
    sys.exit(0)
