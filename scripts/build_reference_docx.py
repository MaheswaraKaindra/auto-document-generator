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

BAHASA VISUALNYA DIAMBIL DARI PDF ACUAN (dilihat halamannya sebagai GAMBAR,
2026-07-16 — bukan cuma teksnya): judul bab TENGAH + bold + huruf besar (bukan
kiri), body justified (rata kiri-kanan), header tabel hitam dengan teks putih di
tengah, caption kecil-miring biru-kelabu di tengah, kaki halaman = judul dokumen
miring di kiri + nomor halaman di kanan, dan Daftar Isi dengan titik-titik (dot
leader) sampai nomor halaman rata kanan.

ANGKA-ANGKANYA:
Satuan OOXML aneh dan mudah salah. `w:sz` itu SETENGAH-poin (32 = 16pt);
`w:spacing` dan `w:tblCellMar` pakai twip (1/20 poin, jadi 240 = 12pt).
Lebar area teks halaman = 8,5" - 2×1" margin = 6,5" = 9360 twip; tab stop kanan
di 9350 supaya tidak menabrak batas.

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
CAPTION_INK = "44546A"  # biru-kelabu caption, meniru caption dokumen acuan

# Tab stop kanan untuk nomor halaman (TOC & footer): tepat di tepi kanan area teks.
RIGHT_EDGE_TWIPS = 9350


def _sub(parent, tag: str, **attrs):
    """Bikin elemen OOXML dan tempelkan ke parent."""
    element = OxmlElement(tag)
    for key, value in attrs.items():
        element.set(qn(f"w:{key}"), str(value))
    parent.append(element)
    return element


def _field_runs(instruction: str, placeholder: str, *, italic=False, size=None):
    """Runs untuk satu field Word KOMPLEKS (fldChar begin/instrText/separate/end)
    — nilainya dihitung WORD saat dokumen dibuka. Prinsip yang sama dengan
    Daftar Gambar/Tabel: kita tidak tahu nomor halamannya, dan memang tidak
    perlu tahu.

    Kenapa field kompleks, bukan `fldSimple`: saat memperbarui field, Word
    MEMBUANG format run hasil lama dan mengambil format dari run KODE field-nya.
    fldSimple tidak punya run kode, jadi hasil update jatuh ke format default
    (terukur di probe: footer jadi 12pt tegak, bukan 9pt miring). Di field
    kompleks tiap run — termasuk run instrText — membawa rPr, jadi formatnya
    selamat melewati update. Ini persis cara Word sendiri menyimpan field.
    """

    def _rpr():
        rpr = OxmlElement("w:rPr")
        if italic:
            _sub(rpr, "w:i")
        if size:
            _sub(rpr, "w:sz", val=int(size * 2))
        return rpr

    runs = []
    for kind in ("begin", "separate", "end"):
        run = OxmlElement("w:r")
        run.append(_rpr())
        if kind == "begin":
            fld = OxmlElement("w:fldChar")
            fld.set(qn("w:fldCharType"), "begin")
            run.append(fld)
            runs.append(run)
            code = OxmlElement("w:r")
            code.append(_rpr())
            instr = OxmlElement("w:instrText")
            instr.set(qn("xml:space"), "preserve")
            instr.text = instruction
            code.append(instr)
            runs.append(code)
        elif kind == "separate":
            fld = OxmlElement("w:fldChar")
            fld.set(qn("w:fldCharType"), "separate")
            run.append(fld)
            runs.append(run)
            result = OxmlElement("w:r")
            result.append(_rpr())
            text = OxmlElement("w:t")
            text.text = placeholder
            result.append(text)
            runs.append(result)
        else:
            fld = OxmlElement("w:fldChar")
            fld.set(qn("w:fldCharType"), "end")
            run.append(fld)
            runs.append(run)
    return runs


def _restyle(style, *, size=None, bold=False, italic=False, caps=False, color=None,
             align=None, before=None, after=None, line=None, keep_next=False,
             char_spacing=None, page_break_before=False):
    """Timpa gaya satu style. `size` dalam POIN (dikonversi ke setengah-poin),
    `before`/`after`/`line` dalam POIN (dikonversi ke twip), `char_spacing`
    (perenggangan antar-huruf, untuk judul huruf besar) dalam twip."""
    rpr = style.element.get_or_add_rPr()
    ppr = style.element.get_or_add_pPr()
    for tag in ("w:b", "w:i", "w:caps", "w:sz", "w:szCs", "w:color", "w:spacing"):
        for old in rpr.findall(qn(tag)):
            rpr.remove(old)
    for tag in ("w:jc", "w:spacing", "w:keepNext", "w:pageBreakBefore"):
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
    if char_spacing:
        _sub(rpr, "w:spacing", val=char_spacing)
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
    if page_break_before:
        _sub(ppr, "w:pageBreakBefore")


def _toc_entry_style(document, style_id: str, internal_name: str, *,
                     size=10.5, caps=False, indent=0, after=4):
    """Style entri daftar (TOC 1-3, Table of Figures) dengan DOT LEADER.

    Kerangka bawaan Pandoc TIDAK punya style ini sama sekali (diperiksa). Saat
    Word mengisi field TOC, dia memakai style bernama "toc 1"/"table of figures"
    KALAU ADA di dokumen — kalau tidak, Word mengarang sendiri. Mendefinisikannya
    di sini berarti rupa daftar (titik-titik, nomor rata kanan, indent per level)
    deterministik, bukan tergantung versi Word pembaca.

    Yang penting NAMA INTERNALNYA ("toc 1", huruf kecil) — itu kunci yang dipakai
    Word untuk mencocokkan built-in style, bukan styleId.
    """
    style = OxmlElement("w:style")
    style.set(qn("w:type"), "paragraph")
    style.set(qn("w:styleId"), style_id)
    _sub(style, "w:name", val=internal_name)
    _sub(style, "w:basedOn", val="Normal")

    ppr = OxmlElement("w:pPr")
    tabs = OxmlElement("w:tabs")
    tab = OxmlElement("w:tab")
    tab.set(qn("w:val"), "right")
    tab.set(qn("w:leader"), "dot")
    tab.set(qn("w:pos"), str(RIGHT_EDGE_TWIPS))
    tabs.append(tab)
    ppr.append(tabs)
    spacing = OxmlElement("w:spacing")
    spacing.set(qn("w:after"), str(after * 20))
    ppr.append(spacing)
    if indent:
        _sub(ppr, "w:ind", left=indent)
    style.append(ppr)

    rpr = OxmlElement("w:rPr")
    if caps:
        _sub(rpr, "w:caps")
    _sub(rpr, "w:sz", val=int(size * 2))
    _sub(rpr, "w:szCs", val=int(size * 2))
    style.append(rpr)

    document.styles.element.append(style)


def _style_table(style):
    """Tabel: garis konsisten, sel bernapas, isi rata tengah vertikal, header
    HITAM dengan teks putih DI TENGAH — meniru tabel dokumen acuan.

    Header hitamnya dipasang lewat `tblStylePr type="firstRow"` — BUKAN dengan
    memformat selnya langsung. Alasannya: Pandoc menghasilkan sel dengan `<w:tcPr/>`
    KOSONG dan menyalakan `<w:tblLook w:firstRow="1">`, artinya Word sendiri yang
    menerapkan format kondisional baris pertama dari style ini. Jadi seluruh rupa
    tabel bisa diatur dari sini tanpa menyentuh satu baris pun XML yang dihasilkan
    — dan tanpa template Jinja2 perlu tahu apa-apa soal warna.
    """
    element = style.element
    for tag in ("w:tblPr", "w:trPr", "w:tcPr"):
        for old in element.findall(qn(tag)):
            element.remove(old)
    for old in element.findall(qn("w:tblStylePr")):
        element.remove(old)

    tbl_pr = OxmlElement("w:tblPr")
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        _sub(borders, f"w:{edge}", val="single", sz=4, space=0, color=GRID)
    tbl_pr.append(borders)

    # Pandoc bawaan memberi padding atas/bawah NOL — itu yang bikin baris tabel
    # terlihat mampet seperti keluaran Markdown mentah. 80 twip = 4pt napas.
    margins = OxmlElement("w:tblCellMar")
    for edge, width in (("top", 80), ("left", 115), ("bottom", 80), ("right", 115)):
        _sub(margins, f"w:{edge}", w=width, type="dxa")
    tbl_pr.append(margins)
    element.append(tbl_pr)

    # Tinggi baris minimum + isi sel rata TENGAH vertikal (bukan nempel atas) —
    # w:style tabel boleh membawa trPr/tcPr sendiri, berlaku ke semua baris/sel.
    # cantSplit: baris tidak boleh TERBELAH melintasi batas halaman (terlihat di
    # probe: baris System Requirement terpotong, sisa katanya sendirian di
    # halaman berikutnya); baris yang lebih tinggi dari satu halaman tetap
    # dibelah Word — aturan ini cuma memindahkan baris yang muat.
    tr_pr = OxmlElement("w:trPr")
    height = OxmlElement("w:trHeight")
    height.set(qn("w:val"), "300")  # 15pt minimum; baris isi panjang tetap tumbuh
    height.set(qn("w:hRule"), "atLeast")
    tr_pr.append(height)
    _sub(tr_pr, "w:cantSplit")
    element.append(tr_pr)

    tc_pr = OxmlElement("w:tcPr")
    _sub(tc_pr, "w:vAlign", val="center")
    element.append(tc_pr)

    # CATATAN pahit yang sudah diprobe (2026-07-16): w:pPr di dalam tblStylePr
    # (mis. jc=center untuk teks header) DIABAIKAN Word — dicoba dengan compat
    # flag overrideTableStyleFontSizeAndJustification true/false/absen, ketiganya
    # identik. rPr dan tcPr dihormati; pPr tidak. Karena itu perataan teks header
    # dipasang compiler_service lewat post-process python-docx, bukan di sini.
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
    # Judul dokumen (halaman cover). Judulnya juga muncul di kaki tiap halaman
    # lewat field TITLE — satu sumber, dua tempat, meniru acuan. Napas besar di
    # atas & bawahnya supaya cover tidak terasa mampet.
    _restyle(styles["Title"], size=22, bold=True, align="center", before=64, after=28)

    # Section = Heading 2, karena template memakai `##` (`#` dipakai judul, yang
    # kini datang dari metadata). Di dokumen acuan judul bab DI TENGAH, bold,
    # huruf besar — bukan rata kiri gaya Markdown. Perenggangan antar-huruf
    # halus (char_spacing) jadi aksen visualnya.
    _restyle(styles["Heading 1"], size=16, bold=True, caps=True, color=BLACK,
             align="center", before=28, after=12, keep_next=True, char_spacing=10)
    _restyle(styles["Heading 2"], size=14, bold=True, caps=True, color=BLACK,
             align="center", before=28, after=14, keep_next=True, char_spacing=10)
    _restyle(styles["Heading 3"], size=12, bold=True, color=BLACK,
             before=16, after=8, keep_next=True)

    # Judul "Daftar Isi/Gambar/Tabel": rupa sama dengan judul bab, plus SELALU
    # mulai halaman baru — di acuan tiap daftar punya halamannya sendiri.
    _restyle(styles["TOC Heading"], size=14, bold=True, caps=True, color=BLACK,
             align="center", before=0, after=18, char_spacing=10,
             page_break_before=True)

    # Caption: kecil, miring, biru-kelabu, di TENGAH — persis caption acuan.
    # `keep_next` supaya caption tabel tidak pernah terpisah dari tabelnya.
    _restyle(styles["Image Caption"], size=9, italic=True, align="center",
             color=CAPTION_INK, before=6, after=14)
    _restyle(styles["Table Caption"], size=9, italic=True, align="center",
             color=CAPTION_INK, before=4, after=14, keep_next=True)

    # Body JUSTIFIED (rata kiri-kanan) dengan spasi baris longgar — dua penanda
    # dokumen resmi yang paling terlihat saat disandingkan dengan acuan.
    _restyle(styles["Body Text"], size=11, align="both", after=8, line=16)
    _restyle(styles["First Paragraph"], size=11, align="both", after=8, line=16)
    # Compact dipakai sel tabel DAN list rapat: sedikit lebih kecil dari body.
    _restyle(styles["Compact"], size=10.5, after=2, line=14)

    # Paragraf gambar: diagram selalu DI TENGAH halaman + napas di sekelilingnya.
    _restyle(styles["Figure"], align="center", before=10, after=4)
    _restyle(styles["Captioned Figure"], align="center", before=10, after=4)

    _style_table(styles["Table"])

    # --- Style entri daftar (dot leader) ------------------------------------
    # Bab template = Heading 2, jadi entri utama Daftar Isi memakai "toc 2"
    # (indent 0, huruf besar seperti acuan) dan sub-bab memakai "toc 3".
    _toc_entry_style(document, "TOC1", "toc 1", size=11, caps=True)
    _toc_entry_style(document, "TOC2", "toc 2", size=10.5, caps=True)
    _toc_entry_style(document, "TOC3", "toc 3", size=10.5, indent=240)
    _toc_entry_style(document, "TableofFigures", "table of figures", size=10.5)

    # --- updateFields --------------------------------------------------------
    # Daftar Isi/Gambar/Tabel SDD kini field TOC yang ditanam template (bukan
    # --toc — lihat _pandoc_args di compiler_service). Tanpa updateFields, Word
    # tidak pernah mengisinya dan pembaca cuma melihat placeholder. Pandoc
    # menyalin settings.xml dari reference doc (diprobe 2026-07-16), jadi satu
    # baris di sini menghidupkan semua field di setiap dokumen yang dihasilkan.
    update_fields = OxmlElement("w:updateFields")
    update_fields.set(qn("w:val"), "true")
    document.settings.element.insert(0, update_fields)

    # --- Kaki halaman ------------------------------------------------------
    # "<judul dokumen, miring>  ....  <nomor>" — meniru acuan: judul miring di
    # kiri, nomor halaman rata kanan, satu baris, kecil supaya tidak berebut
    # perhatian dengan isi.
    footer = document.sections[0].footer
    paragraph = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
    for child in list(paragraph._p):
        paragraph._p.remove(child)
    ppr = OxmlElement("w:pPr")
    tabs = OxmlElement("w:tabs")
    tab = OxmlElement("w:tab")
    tab.set(qn("w:val"), "right")
    tab.set(qn("w:pos"), str(RIGHT_EDGE_TWIPS))
    tabs.append(tab)
    ppr.append(tabs)
    paragraph._p.append(ppr)
    for run in _field_runs(" TITLE ", "", italic=True, size=9):
        paragraph._p.append(run)
    tab_run = OxmlElement("w:r")
    tab_rpr = OxmlElement("w:rPr")
    _sub(tab_rpr, "w:sz", val=18)  # 9pt, sama dengan runs field — jaga tinggi baris footer
    tab_run.append(tab_rpr)
    tab_run.append(OxmlElement("w:tab"))
    paragraph._p.append(tab_run)
    for run in _field_runs(" PAGE ", "1", size=9):
        paragraph._p.append(run)

    document.save(str(destination))
    scratch.unlink()
    return destination


if __name__ == "__main__":
    path = build()
    print(f"reference.docx dibangun: {path} ({path.stat().st_size / 1024:.0f} KB)")
    print("Jalankan pytest — ada test yang menjaga style Pandoc tidak ikut rusak.")
    sys.exit(0)
