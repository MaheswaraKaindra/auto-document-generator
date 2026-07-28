"""Sintesis kerangka TAMPILAN dokumen (`reference.docx`) untuk Pandoc.

`build_reference(dest, spec)` membangun reference.docx yang menentukan rupa
dokumen: tipografi, gaya tabel, kaki halaman. Isi dokumen datang dari Contract B
lewat template Jinja2; file ini tidak tahu apa-apa soal isi, dan tidak boleh tahu.

DUA PEMANGGIL:
  - CLI `scripts/build_reference_docx.py` → `build_reference()` tanpa spec →
    meregenerasi `app/templates/reference.docx` ter-commit (PREMCO default).
  - Runtime V2 (`template_compiler_service`) → `build_reference(dest, spec)` →
    reference tersintesis per template yang di-upload user.
Dulu seluruh logika ini ada di script; dipindah ke service saat runtime V2 mulai
membutuhkannya (2026-07-19). Script kini pembungkus CLI tipis.

DUA MODE (V2 — sintesis reference dari template user). Tanpa argumen, `build()`
menghasilkan reference PREMCO, dan hasilnya CONTENT-IDENTIK dengan
`app/templates/reference.docx` yang ter-commit — isi tiap member zip sama; cuma
timestamp zip yang berbeda antar-build (itu wajar & tak berbahaya) — jadi
meregenerasinya tak pernah menggeser garis-dasar 239 test. Dengan `spec` (sebuah
`TemplateSpec` dari `app.services.template_spec_service`), tipografi & warna
header DIUKUR dari docx template user lalu di-override DI ATAS fondasi PREMCO yang
sama. Yang di-override cuma identitas sumber (tema major/minor, ukuran/bold/caps/
rata Title & Heading, warna fill+teks header tabel); seluruh struktur teruji —
dot-leader, footer fldChar, padding tabel, updateFields, caption — diwarisi utuh.
Inilah langkah "sintesis reference.docx" pipeline upload-template. Lihat
`_resolve_style`.

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
badan ~13, heading ~19 (rasio ~1,45x).

FONTNYA CALIBRI, DAN HARUS DISET SENDIRI. Baris di sini dulu berbunyi "fontnya
Calibri — dan Calibri kebetulan sudah jadi font tema bawaan Pandoc, jadi tidak
perlu diubah". Itu SALAH: tema bawaan Pandoc adalah Aptos. Karena kalimat itu
MENALAR alih-alih MENGUKUR, kesimpulannya ("tidak perlu diubah") membuat font
tidak pernah diset, dan seluruh dokumen keluar ber-Aptos — setiap huruf di setiap
halaman memakai font yang bukan font acuan. Lihat `_set_theme_fonts`.
"""

import re
import subprocess
import zipfile
from pathlib import Path

import docx
import pypandoc
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

# reference.docx ter-commit (dipakai CLI scripts/build_reference_docx.py saat
# meregenerasi tanpa spec). Service ini di app/services/, jadi parent.parent = app/.
DEFAULT_REFERENCE = Path(__file__).resolve().parent.parent / "templates" / "reference.docx"

# Font seluruh dokumen. Diukur dari docx acuan, bukan ditebak: `docDefaults`
# mereka menyetel rFonts ascii="Calibri" EKSPLISIT (sz=22 = 11pt), dan tema
# mereka pun major="Calibri" — jadi tidak ada satu pun jalur yang merender
# selain Calibri. Kerangka bawaan Pandoc memakai Aptos; lihat `_set_theme_fonts`.
BODY_FONT = "Calibri"

BLACK = "000000"
WHITE = "FFFFFF"
# 2026-07-21: header tabel dikembalikan ke HITAM atas aturan tipografi pemilik
# ("Table Header: background hitam, teks putih"). Konstanta DARK tetap ada untuk
# jalur sintesis template upload (fallback), tapi default PREMCO kembali BLACK.
DARK = "3B3838"
# "Semi bold" heading 3: Calibri tak punya varian Semibold di OOXML (w:b itu
# biner), jadi diaproksimasi bold + abu gelap — terbaca lebih ringan dari H2
# (hitam bold), memberi tingkat ketiga hierarki tanpa font tambahan.
SEMIBOLD_INK = "595959"
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
             char_spacing=None, page_break_before=False, keep_lines=False,
             widow_control=False):
    """Timpa gaya satu style. `size` dalam POIN (dikonversi ke setengah-poin),
    `before`/`after`/`line` dalam POIN (dikonversi ke twip), `char_spacing`
    (perenggangan antar-huruf, untuk judul huruf besar) dalam twip.

    `keep_lines` = paragraf tidak boleh TERBELAH melintasi halaman (dipakai
    heading & caption: heading dua baris yang patah di batas halaman, atau
    caption yang setengahnya pindah, adalah cacat paling khas dokumen
    hasil-generate). `widow_control` = jangan tinggalkan satu baris sendirian di
    ujung/awal halaman. Keduanya default Word, TAPI tidak dinyatakan di kerangka
    Pandoc — dan "default" yang tidak tertulis adalah yang berubah diam-diam
    antar versi Word. Dinyatakan eksplisit supaya deterministik.
    """
    rpr = style.element.get_or_add_rPr()
    ppr = style.element.get_or_add_pPr()
    for tag in ("w:b", "w:i", "w:caps", "w:sz", "w:szCs", "w:color", "w:spacing"):
        for old in rpr.findall(qn(tag)):
            rpr.remove(old)
    for tag in ("w:jc", "w:spacing", "w:keepNext", "w:pageBreakBefore",
                "w:keepLines", "w:widowControl"):
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
    if keep_lines:
        _sub(ppr, "w:keepLines")
    if widow_control:
        _sub(ppr, "w:widowControl")
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


def _style_table(style, header_fill: str = BLACK, header_text: str = WHITE):
    """Tabel: garis konsisten, sel bernapas, isi rata tengah vertikal, header
    berlatar `header_fill` dengan teks `header_text` DI TENGAH — meniru tabel
    dokumen acuan. Default PREMCO = latar hitam, teks putih; sintesis dari spec
    mengganti keduanya (warna terukur dari template user + teks kontras).

    Header-nya dipasang lewat `tblStylePr type="firstRow"` — BUKAN dengan
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
    _sub(rpr, "w:color", val=header_text)
    first_row.append(rpr)
    tc_pr = OxmlElement("w:tcPr")
    shading = OxmlElement("w:shd")
    shading.set(qn("w:val"), "clear")
    shading.set(qn("w:color"), "auto")
    shading.set(qn("w:fill"), header_fill)
    tc_pr.append(shading)
    _sub(tc_pr, "w:vAlign", val="center")
    first_row.append(tc_pr)
    element.append(first_row)


def _set_theme_fonts(path: Path, heading_font: str = BODY_FONT,
                     body_font: str = BODY_FONT) -> None:
    """Paksa font tema paket .docx: `heading_font` untuk majorFont (heading),
    `body_font` untuk minorFont (body). Default PREMCO keduanya Calibri.

    KENAPA TEMA, BUKAN STYLE: font dokumen tidak datang dari style mana pun.
    `docDefaults` dan style heading kerangka Pandoc menunjuk ke tema lewat
    `asciiTheme="minorHAnsi"` / `"majorHAnsi"`, dan temanya (word/theme/theme1.xml)
    yang memutuskan huruf apa yang dicetak. Selama tema tidak disentuh, seluruh
    dokumen keluar ber-Aptos berapa pun style-nya diatur — dan itu persis yang
    terjadi seminggu tanpa ketahuan, karena style-nya memang semua benar.

    Dua elemen `<a:latin>`: majorFont (heading) LEBIH DULU dari minorFont (body)
    — urutan itu dijamin skema OOXML, jadi penggantian berurutan (major, lalu
    minor) aman. Saat `heading_font == body_font` (PREMCO), keduanya jadi string
    yang sama, sehingga output identik dengan versi lama yang menyetel satu font.
    `panose` ikut dibuang — itu sidik jari metrik font LAMA; membiarkannya
    menunjuk Aptos bisa menyesatkan substitusi Word di mesin tanpa font itu.

    python-docx tidak mengekspos part tema, jadi paketnya ditulis ulang.
    """
    theme_part = "word/theme/theme1.xml"
    with zipfile.ZipFile(path) as package:
        items = [(info, package.read(info.filename)) for info in package.infolist()]
    if not any(info.filename == theme_part for info, _ in items):
        raise RuntimeError(f"{theme_part} tidak ada di kerangka Pandoc — font tidak bisa diset.")
    order = [heading_font, body_font]
    seen = [0]

    def _pick_latin(_match) -> str:
        font = order[min(seen[0], len(order) - 1)]  # jaga-jaga bila match >2
        seen[0] += 1
        return f'<a:latin typeface="{font}"/>'

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as package:
        for info, data in items:
            if info.filename == theme_part:
                patched, count = re.subn(
                    r'<a:latin typeface="[^"]*"(?:\s+panose="[^"]*")?\s*/>',
                    _pick_latin,
                    data.decode("utf-8"),
                )
                if count != 2:
                    raise RuntimeError(
                        f"Diharapkan 2 <a:latin> di tema (major+minor), ketemu {count} — "
                        "kerangka Pandoc berubah, periksa sebelum percaya fontnya benar."
                    )
                data = patched.encode("utf-8")
            package.writestr(info, data)


def _contrast_text(fill_hex: str) -> str:
    """Putih atau hitam untuk teks DI ATAS `fill_hex`, dihitung dari luminansi
    (YIQ). Fill gelap → teks putih; fill terang → teks hitam. Dihitung, bukan
    diukur per-dokumen: begitu warna header datang dari template user sembarang
    (hitam PREMCO, abu `A4A4A4`, biru tua…), teks header harus tetap terbaca
    tanpa kita menebak. Ambang 128 = konvensi YIQ; setiap warna header nyata yang
    diukur sejauh ini jatuh jelas di satu sisi (PREMCO 000000→putih; 04
    A4A4A4/D9D9D9→hitam)."""
    fill = fill_hex.lstrip("#")
    r, g, b = (int(fill[i:i + 2], 16) for i in (0, 2, 4))
    yiq = (r * 299 + g * 587 + b * 114) / 1000
    return BLACK if yiq >= 128 else WHITE


def _cover_style(document, style_id: str, name: str, *, bottom_rule: str = "", **restyle):
    """Daftarkan satu style paragraf BARU (belum ada di kerangka Pandoc) lalu
    beri rupanya lewat `_restyle`.

    Dipakai halaman cover. Template memanggilnya lewat div Pandoc
    `::: {custom-style="Cover Title"}` — Pandoc mencocokkan berdasarkan NAMA
    style, jadi nama di sini adalah kontraknya dengan template (diprobe: Pandoc
    tetap memakai nama itu walau style-nya tak ada, cuma tanpa rupa apa pun —
    makanya style-nya harus benar-benar didefinisikan di sini).

    `bottom_rule` = warna garis hairline di BAWAH paragraf (kosong = tanpa
    garis). Itu cara membuat pemisah tipis di cover tanpa menggambar tabel:
    satu paragraf kosong yang seluruh gunanya adalah garisnya.
    """
    element = OxmlElement("w:style")
    element.set(qn("w:type"), "paragraph")
    element.set(qn("w:styleId"), style_id)
    _sub(element, "w:name", val=name)
    _sub(element, "w:basedOn", val="Normal")
    _sub(element, "w:qFormat")
    document.styles.element.append(element)

    style = document.styles[name]
    _restyle(style, **restyle)
    if bottom_rule:
        borders = OxmlElement("w:pBdr")
        _sub(borders, "w:bottom", val="single", sz=6, space=1, color=bottom_rule)
        style.element.get_or_add_pPr().append(borders)
    return style


def _letterspacing(caps: bool):
    """Perenggangan antar-huruf halus MENYERTAI perlakuan huruf-besar (aksen
    titling khas dokumen resmi). Non-caps → tak ada. Aturan turunan ini menjaga
    PREMCO (H1/H2 caps → renggang 10) identik byte, sekaligus memberi keputusan
    waras untuk spec asing tanpa menambah knob terpisah."""
    return 10 if caps else None


# Default PREMCO — nilai yang selama ini di-hardcode. `spec=None` mereproduksi
# ini PERSIS (isi tiap member zip identik dengan reference.docx ter-commit), jadi
# meregenerasi tanpa spec tak pernah menggeser garis-dasar test.
_PREMCO_STYLE = {
    "heading_font": BODY_FONT,   # tema major
    "body_font": BODY_FONT,      # tema minor
    "title":    {"size": 30, "bold": True, "caps": False, "align": "center"},
    # Ukuran heading DIUKUR dari PDF acuan (span per baris, 2026-07-21), bukan
    # ditebak: bab "DESKRIPSI APLIKASI"/"SYSTEM REQUIREMENT" = Calibri-Bold 14pt
    # huruf besar di TENGAH; sub-bab "2.10. Activity Diagram ..." = Calibri-Bold
    # 12pt rata KIRI. Aturan tipografi pemilik (bab besar+bold+UPPERCASE+tengah,
    # sub-bab bold) tetap dipenuhi — yang berubah cuma angkanya, dari 16/13 yang
    # ditebak jadi 14/12 yang terukur.
    "heading1": {"size": 14, "bold": True, "caps": True,  "align": "center"},  # bab: besar+bold+UPPERCASE
    "heading2": {"size": 12, "bold": True, "caps": False, "align": "left"},    # sub-bab: bold
    "heading3": {"size": 11, "bold": True, "caps": False, "align": "left"},    # sub-sub: semibold (approx via SEMIBOLD_INK)
    "header_fill": BLACK,
    "header_text": WHITE,
}


def _resolve_style(spec: dict | None) -> dict:
    """Gabungkan properti visual sumber-spesifik dari `TemplateSpec` di atas
    fondasi PREMCO. `spec` kosong/None → PERSIS PREMCO (lihat `_PREMCO_STYLE`).

    Yang di-override HANYA identitas sumber: tema major/minor (font heading vs
    body TERPISAH), Title/Heading{1,2,3} {size,bold,caps,align}, dan warna
    fill+teks header tabel. Field spec yang kosong (None/"") jatuh ke nilai
    PREMCO — perilaku fallback yang sama dengan riset scratchpad yang menyalin
    reference PREMCO lalu menimpanya.
    """
    if not spec:
        return {k: (dict(v) if isinstance(v, dict) else v)
                for k, v in _PREMCO_STYLE.items()}
    visual = spec.get("visual", {}) or {}

    def pick(measured, default):
        # Bool `False` harus lolos (bukan dianggap "kosong"); cuma None/"" fallback.
        return measured if measured not in (None, "") else default

    def heading(key: str) -> dict:
        m = (visual.get("headings", {}) or {}).get(key, {}) or {}
        d = _PREMCO_STYLE[key.lower().replace(" ", "")]
        return {
            "size": pick(m.get("size_pt"), d["size"]),
            "bold": pick(m.get("bold"), d["bold"]),
            "caps": pick(m.get("caps"), d["caps"]),
            "align": pick(m.get("align"), d["align"]),
        }

    title_m = visual.get("title", {}) or {}
    fill = pick(visual.get("table_header_fill"), BLACK)
    return {
        "heading_font": pick(visual.get("effective_heading_font"), BODY_FONT),
        "body_font": pick(visual.get("effective_body_font"), BODY_FONT),
        "title": {
            "size": pick(title_m.get("size_pt"), 22),
            "bold": pick(title_m.get("bold"), True),
            "caps": pick(title_m.get("caps"), False),
            "align": pick(title_m.get("align"), "center"),
        },
        "heading1": heading("Heading 1"),
        "heading2": heading("Heading 2"),
        "heading3": heading("Heading 3"),
        "header_fill": fill,
        "header_text": _contrast_text(fill),
    }


def build_reference(destination: Path = DEFAULT_REFERENCE, spec: dict | None = None) -> Path:
    default = subprocess.run(
        [pypandoc.get_pandoc_path(), "--print-default-data-file", "reference.docx"],
        capture_output=True,
        check=True,
    ).stdout
    scratch = destination.with_suffix(".tmp")
    scratch.write_bytes(default)
    document = docx.Document(str(scratch))
    styles = document.styles
    cfg = _resolve_style(spec)  # PREMCO bila spec None; terukur-dari-sumber bila terisi

    # --- Tipografi ---------------------------------------------------------
    # Judul dokumen (halaman cover). Judulnya juga muncul di kaki tiap halaman
    # lewat field TITLE — satu sumber, dua tempat, meniru acuan. Napas besar di
    # atas & bawahnya supaya cover tidak terasa mampet.
    # `after` sengaja RAPAT (14, dulu 28): tepat di bawah judul cover kini ada
    # baris identitas ("No. Solution Design ...") — dua baris yang saling
    # menjelaskan harus terbaca sebagai satu blok, bukan dua. Napas besar cover
    # pindah ke atas judul, dibawa "Cover Eyebrow" (lihat blok Cover di bawah).
    _restyle(styles["Title"], size=cfg["title"]["size"], bold=cfg["title"]["bold"],
             caps=cfg["title"]["caps"], align=cfg["title"]["align"],
             char_spacing=_letterspacing(cfg["title"]["caps"]), before=64, after=14)

    # Aturan tipografi pemilik (2026-07-21): H1 = bab (besar+bold+UPPERCASE,
    # tengah), H2 = sub-bab (bold), H3 = sub-sub (semibold, diaproksimasi bold +
    # SEMIBOLD_INK). Template DIGESER agar bab pakai `#` = Word Heading 1 (dulu
    # bab `##` = Heading 2; `#` bebas karena judul datang dari metadata) — supaya
    # style Word H1/H2/H3 cocok langsung dengan aturan & penamaan Word benar saat
    # diedit. Perenggangan antar-huruf (char_spacing) mengiringi huruf besar H1.
    # keep_next = heading tidak boleh jadi baris terakhir halaman (harus ikut
    # paragraf/tabel di bawahnya); keep_lines = heading yang jatuh ke dua baris
    # tidak boleh dipatahkan di antara keduanya.
    _restyle(styles["Heading 1"], size=cfg["heading1"]["size"], bold=cfg["heading1"]["bold"],
             caps=cfg["heading1"]["caps"], color=BLACK, align=cfg["heading1"]["align"],
             before=28, after=12, keep_next=True, keep_lines=True, widow_control=True,
             char_spacing=_letterspacing(cfg["heading1"]["caps"]))
    _restyle(styles["Heading 2"], size=cfg["heading2"]["size"], bold=cfg["heading2"]["bold"],
             caps=cfg["heading2"]["caps"], color=BLACK, align=cfg["heading2"]["align"],
             before=28, after=14, keep_next=True, keep_lines=True, widow_control=True,
             char_spacing=_letterspacing(cfg["heading2"]["caps"]))
    _restyle(styles["Heading 3"], size=cfg["heading3"]["size"], bold=cfg["heading3"]["bold"],
             caps=cfg["heading3"]["caps"], color=SEMIBOLD_INK, align=cfg["heading3"]["align"],
             before=16, after=8, keep_next=True, keep_lines=True, widow_control=True,
             char_spacing=_letterspacing(cfg["heading3"]["caps"]))

    # --- Halaman cover -------------------------------------------------------
    # Hierarki cover diukur dari halaman 1 dokumen acuan (span PDF-nya dibaca,
    # bukan ditebak): label jenis dokumen di ATAS (18pt bold) lalu NAMA PROJECT
    # yang lebih besar (20pt bold) sebagai puncaknya, baru identitas (versi, RFC,
    # klasifikasi) yang mengecil di bawahnya. Kita memakai urutan yang sama
    # dengan kontras ukuran yang lebih tegas (13 → 30), plus pemisah hairline dan
    # label section kecil — supaya cover terbaca sebagai hierarki, bukan tumpukan
    # tabel. Ukuran judulnya sendiri tetap dari cfg["title"] (style Title).
    _cover_style(document, "CoverEyebrow", "Cover Eyebrow",
                 size=13, bold=True, caps=True, color=SEMIBOLD_INK, align="center",
                 char_spacing=80, before=58, after=4)
    # Baris identitas di bawah judul (No. Solution Design) — menempel judul.
    _cover_style(document, "CoverSubtitle", "Cover Subtitle",
                 size=11.5, color=SEMIBOLD_INK, align="center", before=0, after=2)
    # Pemisah: paragraf yang isinya cuma garis. Ukuran font sengaja kecil supaya
    # yang memakan tinggi adalah spasi before/after-nya, bukan barisnya.
    _cover_style(document, "CoverRule", "Cover Rule",
                 size=6, align="center", before=12, after=12, bottom_rule=GRID)
    # Judul blok cover ("Kodifikasi & Katalog Proses Bisnis", "Tim Project"):
    # kecil, huruf besar, renggang — penanda kelompok, bukan heading bab (jadi
    # sengaja BUKAN Heading, supaya tidak masuk Daftar Isi).
    _cover_style(document, "CoverSectionLabel", "Cover Section Label",
                 size=9.5, bold=True, caps=True, color=SEMIBOLD_INK, align="left",
                 char_spacing=60, before=16, after=5, keep_next=True)

    # Judul "Daftar Isi/Gambar/Tabel": rupa mengikuti judul bab (Heading 2, level
    # bab template), plus SELALU mulai halaman baru — di acuan tiap daftar punya
    # halamannya sendiri.
    _restyle(styles["TOC Heading"], size=cfg["heading1"]["size"], bold=cfg["heading1"]["bold"],
             caps=cfg["heading1"]["caps"], color=BLACK, align=cfg["heading1"]["align"],
             before=0, after=18, char_spacing=_letterspacing(cfg["heading1"]["caps"]),
             page_break_before=True)

    # Caption: kecil, miring, biru-kelabu, di TENGAH — persis caption acuan.
    # Table Caption sengaja TANPA keep_next: caption tabel kini DI BAWAH
    # tabelnya (dipindah _move_table_captions_below di compiler, meniru acuan),
    # jadi keep_next malah mengikatnya ke paragraf sesudahnya — arah yang salah.
    # Yang menjaga caption menempel tabelnya: keepNext di baris terakhir tabel,
    # dipasang compiler saat memindahkan.
    # keep_lines: caption dua baris tidak boleh terbelah antar halaman.
    _restyle(styles["Image Caption"], size=9, italic=True, align="center",
             color=CAPTION_INK, before=6, after=14, keep_lines=True, widow_control=True)
    _restyle(styles["Table Caption"], size=9, italic=True, align="center",
             color=CAPTION_INK, before=4, after=14, keep_lines=True, widow_control=True)

    # Body JUSTIFIED (rata kiri-kanan) dengan spasi baris longgar — dua penanda
    # dokumen resmi yang paling terlihat saat disandingkan dengan acuan.
    _restyle(styles["Body Text"], size=11, align="both", after=10, line=17,
             widow_control=True)
    _restyle(styles["First Paragraph"], size=11, align="both", after=10, line=17,
             widow_control=True)
    # Compact dipakai sel tabel DAN list rapat: sedikit lebih kecil dari body.
    #
    # align="left" WAJIB dinyatakan, bukan dibiarkan mewarisi: Compact
    # `basedOn` Body Text yang JUSTIFIED, jadi tanpa baris ini setiap sel tabel
    # ikut rata kiri-kanan. Di kolom selebar 2-3 inci itu menghasilkan "sungai"
    # spasi yang melebar (terukur di probe: "Admin dapat mengelola seluruh data
    # inventaris:  menambah item baru,  melihat"), dan justru itu penanda paling
    # khas keluaran Markdown mentah. Tabel dokumen acuan rata KIRI.
    _restyle(styles["Compact"], size=10.5, align="left", after=2, line=14,
             widow_control=True)

    # Paragraf gambar: diagram selalu DI TENGAH halaman + napas di sekelilingnya.
    # keep_next mengikat gambar ke CAPTION-nya (caption gambar ada di BAWAH
    # gambar) — tanpa ini gambar bisa tertinggal di halaman sebelumnya sementara
    # captionnya menyeberang sendirian.
    _restyle(styles["Figure"], align="center", before=10, after=4,
             keep_next=True, keep_lines=True)
    _restyle(styles["Captioned Figure"], align="center", before=10, after=4,
             keep_next=True, keep_lines=True)

    _style_table(styles["Table"], header_fill=cfg["header_fill"],
                 header_text=cfg["header_text"])

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
    _set_theme_fonts(destination, heading_font=cfg["heading_font"],
                     body_font=cfg["body_font"])
    scratch.unlink()
    return destination
