"""Bangun `app/templates/reference.docx` — kerangka tampilan untuk Pandoc.

    python scripts/build_reference_docx.py

KENAPA SCRIPT, BUKAN FILE .DOCX YANG DI-COMMIT BEGITU SAJA:
sebuah .docx biner di repo adalah kotak hitam — tidak bisa di-review, tidak bisa
di-diff, dan begitu orang yang membuatnya pergi, tidak ada yang berani
menyentuhnya. Dengan script, tampilan dokumen jadi KODE: bisa dibaca, diubah,
dan dijalankan ulang. Hasilnya tetap di-commit supaya `pip install` saja sudah
cukup untuk menjalankan aplikasi (tidak perlu langkah build tambahan).

APA YANG DIPERBAIKI FILE INI:
Tanpa `--reference-doc`, Pandoc memakai kerangka bawaannya — dan kerangka itu
TIDAK punya header, footer, maupun nomor halaman (diperiksa langsung:
`pandoc --print-default-data-file reference.docx` tidak berisi footer sama
sekali). Akibatnya bukan cuma soal rupa:

    Daftar Gambar kita menulis "Gambar 4 ... 14",
    tapi tidak ada halaman yang bertuliskan "14".

Pembaca harus menghitung halaman satu per satu dari depan. Indeksnya jadi tidak
bisa dipakai. Dokumen acuan (87 halaman) menaruh "<nomor> <judul dokumen>" di
kaki SETIAP halaman — file ini menirunya.

CARA KERJANYA: mulai dari kerangka bawaan Pandoc, lalu TAMBAHKAN footer.
Sengaja tidak membangun dari nol — Pandoc mencari nama style tertentu
("Image Caption", "Table Caption", "First Paragraph", "Title", ...), dan
kerangka buatan sendiri yang kehilangan salah satunya akan merusak Daftar
Gambar/Tabel tanpa error apa pun.
"""

import subprocess
import sys
from pathlib import Path

import docx
import pypandoc
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

OUTPUT = Path(__file__).resolve().parent.parent / "app" / "templates" / "reference.docx"


def _field(instruction: str, placeholder: str) -> OxmlElement:
    """Satu field Word (`fldSimple`) — nilainya dihitung Word saat dokumen dibuka.

    Dipakai untuk PAGE (nomor halaman) dan TITLE (judul dokumen dari docProps).
    Sama seperti Daftar Gambar/Tabel: kita tidak tahu nomor halamannya, dan
    memang tidak perlu tahu — Word yang menghitung. `placeholder` cuma teks
    cadangan untuk pembaca yang tidak menghitung field.
    """
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), instruction)
    run = OxmlElement("w:r")
    text = OxmlElement("w:t")
    text.text = placeholder
    run.append(text)
    field.append(run)
    return field


def build(destination: Path = OUTPUT) -> Path:
    default = subprocess.run(
        [pypandoc.get_pandoc_path(), "--print-default-data-file", "reference.docx"],
        capture_output=True,
        check=True,
    ).stdout
    scratch = destination.with_suffix(".tmp")
    scratch.write_bytes(default)

    document = docx.Document(str(scratch))
    footer = document.sections[0].footer
    paragraph = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()

    # Format kaki halaman meniru acuan: "<nomor>  <judul dokumen>".
    # TITLE membaca docProps, yang diisi compiler_service lewat `-M title=...`,
    # jadi tiap dokumen membawa judulnya sendiri tanpa file ini perlu diubah.
    paragraph._p.append(_field(" PAGE ", "1"))
    spacer = OxmlElement("w:r")
    spacer_text = OxmlElement("w:t")
    spacer_text.set(qn("xml:space"), "preserve")
    spacer_text.text = "   "
    spacer.append(spacer_text)
    paragraph._p.append(spacer)
    paragraph._p.append(_field(" TITLE ", ""))

    document.save(str(destination))
    scratch.unlink()
    return destination


if __name__ == "__main__":
    path = build()
    print(f"reference.docx dibangun: {path} ({path.stat().st_size / 1024:.0f} KB)")
    print("Jalankan pytest untuk memastikan Daftar Gambar/Tabel tidak ikut rusak.")
    sys.exit(0)
