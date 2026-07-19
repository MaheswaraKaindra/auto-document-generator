"""Tes sintesis reference.docx (V2 increment 2). Dua janji yang dijaga:

1. `build(spec=None)` CONTENT-IDENTIK dengan `app/templates/reference.docx`
   ter-commit — isi tiap member zip sama (timestamp zip diabaikan, itu wajar
   beda antar-build), jadi meregenerasi tanpa spec tak pernah menggeser
   garis-dasar 239 test yang membaca file ter-commit.
2. `build(spec=...)` BENAR-BENAR mengukur-dari-sumber: tema major/minor (heading
   vs body terpisah), warna header tabel + teks kontras, caps/rata heading —
   semuanya dari spec, bukan PREMCO.

Logika sintesis ada di `app.services.reference_synthesis_service` (dipindah dari
`scripts/` saat runtime V2 mulai membutuhkannya); CLI `scripts/build_reference_docx.py`
kini cuma pembungkus tipis.
"""
import re
import zipfile
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn

from app.services import reference_synthesis_service as rs

_ROOT = Path(__file__).resolve().parent.parent
COMMITTED = _ROOT / "app" / "templates" / "reference.docx"


def _members(path) -> dict:
    with zipfile.ZipFile(path) as package:
        return {info.filename: package.read(info.filename)
                for info in package.infolist()}


def _style_element(doc, name):
    for style in doc.styles:
        if style.name == name:
            return style.element
    raise AssertionError(f"style {name!r} tak ada di dokumen")


def _first_row_seg(doc):
    """Segmen `tblStylePr type=firstRow` dari style Table — tempat warna header."""
    table = _style_element(doc, "Table")
    for sp in table.findall(qn("w:tblStylePr")):
        if sp.get(qn("w:type")) == "firstRow":
            return sp
    raise AssertionError("tblStylePr firstRow tak ada di style Table")


def test_spec_none_is_content_identical_to_committed_reference(tmp_path):
    """Guard paling penting increment 2: menambah dukungan `spec` TIDAK mengubah
    perilaku default. `build(spec=None)` menghasilkan reference PREMCO yang isi
    tiap member zip-nya identik dengan yang ter-commit — hanya timestamp zip yang
    beda antar-build. Kalau ini gagal, meregenerasi reference.docx akan diam-diam
    menggeser 239 test yang membaca file ter-commit.

    (Ini juga menautkan reference.docx ter-commit ke pandoc environment ini: bila
    versi pandoc berubah sehingga kerangka bawaannya berbeda, test ini gagal dan
    memberi tahu bahwa reference.docx memang perlu diregenerasi.)"""
    rebuilt = rs.build_reference(tmp_path / "ref_none.docx", spec=None)
    committed = _members(COMMITTED)
    got = _members(rebuilt)
    assert list(committed) == list(got), "daftar/urutan member zip berubah"
    differing = [name for name in committed if committed[name] != got[name]]
    assert not differing, f"member berbeda ISI (bukan sekadar timestamp): {differing}"


def test_spec_drives_theme_fonts_heading_and_table_header(tmp_path):
    """Spec terisi → tipografi & warna DIUKUR dari sumber, bukan PREMCO: tema
    major≠minor (heading vs body terpisah), heading tak-caps rata kiri tanpa
    perenggangan, header tabel abu dengan teks HITAM (kontras luminance)."""
    spec = {"visual": {
        "effective_heading_font": "Tahoma",
        "effective_body_font": "Verdana",
        "title": {"size_pt": 20, "bold": True, "caps": False, "align": "left"},
        "headings": {
            "Heading 1": {"size_pt": 13, "bold": True, "caps": False, "align": "left"},
            "Heading 2": {"size_pt": 12, "bold": True, "caps": False, "align": "center"},
        },
        "table_header_fill": "A4A4A4",
    }}
    out = rs.build_reference(tmp_path / "ref_spec.docx", spec=spec)

    with zipfile.ZipFile(out) as package:
        theme = package.read("word/theme/theme1.xml").decode("utf-8")
    assert re.findall(r'<a:latin typeface="([^"]*)"', theme) == ["Tahoma", "Verdana"]

    doc = Document(str(out))
    first_row = _first_row_seg(doc)
    shd = first_row.find(qn("w:tcPr") + "/" + qn("w:shd"))
    assert shd.get(qn("w:fill")) == "A4A4A4"
    color = first_row.find(qn("w:rPr") + "/" + qn("w:color"))
    assert color.get(qn("w:val")) == "000000"   # abu terang -> teks hitam terbaca

    h1_rpr = _style_element(doc, "Heading 1").find(qn("w:rPr"))
    assert h1_rpr.find(qn("w:caps")) is None       # caps=False -> tak ada w:caps
    assert h1_rpr.find(qn("w:spacing")) is None    # non-caps -> tak ada perenggangan
    assert h1_rpr.find(qn("w:sz")).get(qn("w:val")) == "26"  # 13pt = 26 setengah-poin
    h1_jc = _style_element(doc, "Heading 1").find(qn("w:pPr")).find(qn("w:jc"))
    assert h1_jc.get(qn("w:val")) == "left"


def test_premco_default_keeps_caps_and_black_header(tmp_path):
    """Sisi sebaliknya: tanpa spec, heading DIPAKSA huruf besar + perenggangan
    dan header tabel HITAM teks putih — identitas PREMCO tetap utuh."""
    out = rs.build_reference(tmp_path / "ref_premco.docx", spec=None)
    doc = Document(str(out))

    h2_rpr = _style_element(doc, "Heading 2").find(qn("w:rPr"))
    assert h2_rpr.find(qn("w:caps")) is not None
    assert h2_rpr.find(qn("w:spacing")) is not None   # perenggangan menyertai caps

    first_row = _first_row_seg(doc)
    shd = first_row.find(qn("w:tcPr") + "/" + qn("w:shd"))
    assert shd.get(qn("w:fill")) == "000000"
    color = first_row.find(qn("w:rPr") + "/" + qn("w:color"))
    assert color.get(qn("w:val")) == "FFFFFF"


def test_empty_spec_falls_back_to_premco(tmp_path):
    """Spec kosong / tanpa field visual tidak boleh melempar dan harus jatuh ke
    PREMCO — jalur 'template miskin' (V0: sebagian docx cuma 4/14 style)."""
    for empty in ({}, {"visual": {}}):
        cfg = rs._resolve_style(empty)
        assert cfg["heading_font"] == rs.BODY_FONT
        assert cfg["header_fill"] == rs.BLACK
        assert cfg["header_text"] == rs.WHITE
        assert cfg["heading1"]["caps"] is True


def test_contrast_text_picks_readable_ink():
    """Teks header dihitung dari luminansi: fill gelap → putih, terang → hitam,
    dan prefiks '#' ditoleransi."""
    assert rs._contrast_text("000000") == "FFFFFF"
    assert rs._contrast_text("1F3864") == "FFFFFF"    # biru tua
    assert rs._contrast_text("A4A4A4") == "000000"    # abu 04
    assert rs._contrast_text("D9D9D9") == "000000"    # abu IEEE
    assert rs._contrast_text("#9CC3E5") == "000000"   # biru muda + prefiks '#'
