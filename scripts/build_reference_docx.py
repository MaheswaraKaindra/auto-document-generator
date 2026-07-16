"""Bangun `app/templates/reference.docx` — kerangka TAMPILAN dokumen untuk Pandoc.

    python scripts/build_reference_docx.py

File inilah yang menentukan rupa dokumen: tipografi, gaya tabel, kaki halaman.
Isi dokumen datang dari Contract B lewat template Jinja2; file ini tidak tahu
apa-apa soal isi, dan tidak boleh tahu.

KENAPA SCRIPT, BUKAN .DOCX YANG DI-COMMIT BEGITU SAJA:
sebuah .docx biner di repo adalah kotak hitam — tidak bisa di-review, tidak bisa
di-diff, dan begitu pembuatnya pergi tidak ada yang berani menyentuhnya. Dengan
script, tampilan dokumen jadi KODE. Binernya tetap ikut repo supaya `pip install`
saja sudah cukup menjalankan aplikasi.

DIBANGUN DARI KERANGKA BAWAAN PANDOC, BUKAN DARI NOL. Pandoc mencari nama style
tertentu ("Image Caption", "Table Caption", "First Paragraph", "Compact",
"Title", ...). Kerangka buatan sendiri yang kehilangan satu saja akan merusak
Daftar Gambar/Tabel TANPA error apa pun — jadi kita cuma MENIMPA yang perlu.

ANGKA-ANGKANYA:
Satuan OOXML aneh dan mudah salah. `w:sz` itu SETENGAH-poin (32 = 16pt);
`w:spacing` dan `w:tblCellMar` pakai twip (1/20 poin, jadi 240 = 12pt).

Ukuran font mengikuti dokumen acuan, yang diukur langsung dari PDF-nya:
badan ~13, heading ~19 (rasio ~1,45x), fontnya Calibri — dan Calibri kebetulan
sudah jadi font tema bawaan Pandoc, jadi tidak perlu diubah.
"""

import subprocess
import sys
from pathlib import Path

import docx
import pypandoc
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

OUTPUT = Path(__file__).resolve().parent.parent / "app" / "templates" / "reference.docx"

BLACK = "000000"
WHITE = "FFFFFF"
GRID = "BFBFBF"  # abu-abu garis tabel: kelihatan, tapi tidak berteriak


def _sub(parent, tag: str, **attrs):
    """Bikin elemen OOXML dan tempelkan ke parent."""
    element = OxmlElement(tag)
    for key, value in attrs.items():
        element.set(qn(f"w:{key}"), str(value))
    parent.append(element)
    return element


def _field(instruction: str, placeholder: str):
    """Satu field Word (`fldSimple`) — nilainya dihitung WORD saat dokumen dibuka.

    Prinsip yang sama dengan Daftar Gambar/Tabel: kita tidak tahu nomor
    halamannya, dan memang tidak perlu tahu.
    """
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), instruction)
    run = OxmlElement("w:r")
    text = OxmlElement("w:t")
    text.text = placeholder
    run.append(text)
    field.append(run)
    return field


def _restyle(style, *, size=None, bold=False, italic=False, caps=False, color=None,
             align=None, before=None, after=None, line=None, keep_next=False):
    """Timpa gaya satu style. `size` dalam POIN (dikonversi ke setengah-poin),
    `before`/`after`/`line` dalam POIN (dikonversi ke twip)."""
    rpr = style.element.get_or_add_rPr()
    ppr = style.element.get_or_add_pPr()
    for tag in ("w:b", "w:i", "w:caps", "w:sz", "w:szCs", "w:color"):
        for old in rpr.findall(qn(tag)):
            rpr.remove(old)
    for tag in ("w:jc", "w:spacing", "w:keepNext"):
        for old in ppr.findall(qn(tag)):
            ppr.remove(old)

    if bold:
        _sub(rpr, "w:b")
    if italic:
        _sub(rpr, "w:i")
    if caps:
        _sub(rpr, "w:caps")
    if size:
        _sub(rpr, "w:sz", val=int(size * 2))
        _sub(rpr, "w:szCs", val=int(size * 2))
    if color:
        _sub(rpr, "w:color", val=color)
    if align:
        _sub(ppr, "w:jc", val=align)
    if before is not None or after is not None or line is not None:
        spacing = OxmlElement("w:spacing")
        if before is not None:
            spacing.set(qn("w:before"), str(int(before * 20)))
        if after is not None:
            spacing.set(qn("w:after"), str(int(after * 20)))
        if line is not None:
            spacing.set(qn("w:line"), str(int(line * 20)))
            spacing.set(qn("w:lineRule"), "auto")
        ppr.append(spacing)
    if keep_next:
        _sub(ppr, "w:keepNext")


def _style_table(style):
    """Tabel: garis konsisten, sel bernapas, header HITAM dengan teks putih.

    Header hitamnya dipasang lewat `tblStylePr type="firstRow"` — BUKAN dengan
    memformat selnya langsung. Alasannya: Pandoc menghasilkan sel dengan `<w:tcPr/>`
    KOSONG dan menyalakan `<w:tblLook w:firstRow="1">`, artinya Word sendiri yang
    menerapkan format kondisional baris pertama dari style ini. Jadi seluruh rupa
    tabel bisa diatur dari sini tanpa menyentuh satu baris pun XML yang dihasilkan
    — dan tanpa template Jinja2 perlu tahu apa-apa soal warna.
    """
    element = style.element
    for old in element.findall(qn("w:tblPr")):
        element.remove(old)
    for old in element.findall(qn("w:tblStylePr")):
        element.remove(old)

    tbl_pr = OxmlElement("w:tblPr")
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        _sub(borders, f"w:{edge}", val="single", sz=4, space=0, color=GRID)
    tbl_pr.append(borders)

    # Pandoc bawaan memberi padding atas/bawah NOL — itu yang bikin baris tabel
    # terlihat mampet seperti keluaran Markdown mentah.
    margins = OxmlElement("w:tblCellMar")
    for edge, width in (("top", 60), ("left", 108), ("bottom", 60), ("right", 108)):
        _sub(margins, f"w:{edge}", w=width, type="dxa")
    tbl_pr.append(margins)
    element.append(tbl_pr)

    first_row = OxmlElement("w:tblStylePr")
    first_row.set(qn("w:type"), "firstRow")
    rpr = OxmlElement("w:rPr")
    _sub(rpr, "w:b")
    _sub(rpr, "w:color", val=WHITE)
    first_row.append(rpr)
    tc_pr = OxmlElement("w:tcPr")
    shading = OxmlElement("w:shd")
    shading.set(qn("w:val"), "clear")
    shading.set(qn("w:color"), "auto")
    shading.set(qn("w:fill"), BLACK)
    tc_pr.append(shading)
    _sub(tc_pr, "w:vAlign", val="center")
    first_row.append(tc_pr)
    element.append(first_row)


def build(destination: Path = OUTPUT) -> Path:
    default = subprocess.run(
        [pypandoc.get_pandoc_path(), "--print-default-data-file", "reference.docx"],
        capture_output=True,
        check=True,
    ).stdout
    scratch = destination.with_suffix(".tmp")
    scratch.write_bytes(default)
    document = docx.Document(str(scratch))
    styles = document.styles

    # --- Tipografi ---------------------------------------------------------
    # Judul dokumen (halaman pertama). Judulnya juga muncul di kaki tiap halaman
    # lewat field TITLE — satu sumber, dua tempat, meniru acuan.
    _restyle(styles["Title"], size=26, bold=True, align="center", after=8)

    # Section = Heading 2, karena template memakai `##` (`#` dipakai judul, yang
    # kini datang dari metadata). Bold + HURUF BESAR + hitam + napas di atasnya:
    # bawaan Pandoc biru muda 16pt tanpa bold, yang terbaca seperti render
    # Markdown, bukan bab dokumen resmi.
    _restyle(styles["Heading 1"], size=18, bold=True, caps=True, color=BLACK,
             before=20, after=8, keep_next=True)
    _restyle(styles["Heading 2"], size=15, bold=True, caps=True, color=BLACK,
             before=18, after=8, keep_next=True)
    _restyle(styles["Heading 3"], size=12, bold=True, color=BLACK,
             before=12, after=6, keep_next=True)

    # Caption: kecil, miring, di TENGAH — dan `keep_next` supaya caption tabel
    # tidak pernah terpisah dari tabelnya di ujung halaman.
    _restyle(styles["Image Caption"], size=9, italic=True, align="center",
             before=4, after=12)
    _restyle(styles["Table Caption"], size=9, italic=True, align="center",
             before=4, after=12, keep_next=True)

    _restyle(styles["Body Text"], size=11, after=6, line=15)
    _restyle(styles["First Paragraph"], size=11, after=6, line=15)
    _restyle(styles["Compact"], size=10, after=2, line=13)

    _style_table(styles["Table"])

    # --- Kaki halaman ------------------------------------------------------
    # "<nomor>   <judul dokumen>", meniru acuan (dicek di hal 2, 6, 13).
    footer = document.sections[0].footer
    paragraph = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
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
    print("Jalankan pytest — ada test yang menjaga style Pandoc tidak ikut rusak.")
    sys.exit(0)
