"""V2 — `TemplateSpec`: ukur docx template user jadi kontrak JSON terstruktur.

Bagian pertama dari pipeline "upload template jadi template terdaftar" (roadmap
tahap c). DETERMINISTIK, tanpa LLM — sama filosofinya dengan `parser_service`
(Contract A): ukur input, hasilkan struktur, jangan menebak.

Spec ini dikonsumsi dua langkah berikutnya:
  1. sintesis `reference.docx` (properti visual: font, heading, warna header),
  2. pemetaan bab → Contract B (outline heading berurut).

Kelayakannya sudah dibuktikan end-to-end pada template multi-sumber
(`scripts/validation/V2_TEMPLATE_MULTISOURCE.md`); modul ini mengangkat
pengukuran itu dari riset scratchpad jadi kode ber-tes.

PELAJARAN yang dikodekan di sini:
- **Font "efektif" wajib di-resolve, bukan dibaca satu sumber.** `docDefaults`
  bisa menunjuk tema sementara style `Normal` meng-override ke font lain — yang
  DIRENDER adalah hasil resolusi `Normal`→ascii/tema. Membaca `docDefaults` saja
  bisa keliru (mis. template yang docDefault-nya tema-minor tapi Normal-nya
  Verdana). Ini kelas bug yang sama dengan "font tema Aptos".
- **`caps` heading itu diukur, bukan diasumsikan** — sebagian template memaksa
  huruf besar lewat `w:caps`, sebagian tidak.
"""
from __future__ import annotations

import re
import zipfile
from collections import Counter
from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.oxml.ns import qn

# Style yang dicari pipeline Pandoc kita — dipakai menakar seberapa "kaya" style
# template user (V0: template nyata sering cuma punya 4 dari 14; itu sebabnya
# swap reference-doc gagal & sintesis jadi satu-satunya jalan).
PANDOC_STYLES = (
    "Title", "Heading 1", "Heading 2", "Heading 3", "Heading 4",
    "Body Text", "Compact", "First Paragraph", "Image Caption",
    "Table Caption", "Table", "TOC Heading", "toc 1", "table of figures",
)

_GENERIC_TABLE_STYLES = {"Normal Table", "Table Normal", "None"}


def _theme_fonts(path: Path) -> tuple[str | None, str | None]:
    """(font tema major, minor) dari `word/theme/theme1.xml`. python-docx tidak
    mengekspos part tema, jadi dibaca langsung dari paket zip."""
    try:
        with zipfile.ZipFile(path) as package:
            xml = package.read("word/theme/theme1.xml").decode("utf-8", "replace")
    except (KeyError, zipfile.BadZipFile, OSError):
        return (None, None)
    major = re.search(r"<a:majorFont>.*?<a:latin typeface=\"([^\"]*)\"", xml, re.S)
    minor = re.search(r"<a:minorFont>.*?<a:latin typeface=\"([^\"]*)\"", xml, re.S)
    return (major.group(1) if major else None, minor.group(1) if minor else None)


def _rfonts_value(rfonts, theme_major: str | None, theme_minor: str | None) -> str | None:
    """Font EFEKTIF dari satu elemen rFonts: `ascii` eksplisit menang; kalau
    menunjuk tema (`asciiTheme`), resolve ke tema major/minor."""
    if rfonts is None:
        return None
    ascii_ = rfonts.get(qn("w:ascii"))
    if ascii_:
        return ascii_
    theme = rfonts.get(qn("w:asciiTheme"))
    if theme:
        if "major" in theme:
            return theme_major
        if "minor" in theme:
            return theme_minor
    return None


def _docdefault_size(doc) -> float | None:
    rpr = doc.styles.element.find(
        qn("w:docDefaults") + "/" + qn("w:rPrDefault") + "/" + qn("w:rPr"))
    if rpr is None:
        return None
    sz = rpr.find(qn("w:sz"))
    return int(sz.get(qn("w:val"))) / 2 if sz is not None else None


def _style_element(doc, name: str):
    for style in doc.styles:
        if style.name == name:
            return style.element
    return None


def _style_rfonts(doc, name: str):
    el = _style_element(doc, name)
    if el is None:
        return None
    rpr = el.find(qn("w:rPr"))
    return rpr.find(qn("w:rFonts")) if rpr is not None else None


def _effective_fonts(doc, theme_major, theme_minor) -> tuple[str | None, str | None]:
    """(font body, font heading) yang benar-benar dirender. Body dari style
    `Normal` (fallback `docDefaults`); heading dari style `Heading 1` (fallback
    tema major). Beda body vs heading itu nyata dan harus ditangkap."""
    body = _rfonts_value(_style_rfonts(doc, "Normal"), theme_major, theme_minor)
    if not body:
        dd = doc.styles.element.find(
            qn("w:docDefaults") + "/" + qn("w:rPrDefault") + "/" + qn("w:rPr"))
        dd_rfonts = dd.find(qn("w:rFonts")) if dd is not None else None
        body = _rfonts_value(dd_rfonts, theme_major, theme_minor) or theme_minor
    head = _rfonts_value(_style_rfonts(doc, "Heading 1"), theme_major, theme_minor)
    return (body, head or theme_major)


def _style_format(doc, name: str) -> dict | None:
    """Format satu style paragraf: font, ukuran (poin), bold, caps, perataan."""
    el = _style_element(doc, name)
    if el is None:
        return None
    rpr = el.find(qn("w:rPr"))
    ppr = el.find(qn("w:pPr"))
    sz = rpr.find(qn("w:sz")) if rpr is not None else None
    bold = rpr.find(qn("w:b")) if rpr is not None else None
    caps = rpr.find(qn("w:caps")) if rpr is not None else None
    rfonts = rpr.find(qn("w:rFonts")) if rpr is not None else None
    jc = ppr.find(qn("w:jc")) if ppr is not None else None
    font = None
    if rfonts is not None:
        font = rfonts.get(qn("w:ascii")) or rfonts.get(qn("w:asciiTheme"))
    return {
        "font": font,
        "size_pt": int(sz.get(qn("w:val"))) / 2 if sz is not None else None,
        "bold": bold is not None and bold.get(qn("w:val")) not in ("0", "false"),
        "caps": caps is not None and caps.get(qn("w:val")) not in ("0", "false"),
        "align": jc.get(qn("w:val")) if jc is not None else None,
    }


def _guess_kind(heading_text: str) -> str:
    if re.search(r"acceptance|testing|uat|pengujian|test script|defect", heading_text):
        return "UAT"
    if re.search(r"design|architecture|deskripsi|requirement", heading_text):
        return "SDD"
    return "unknown"


def _guess_language(heading_text: str) -> str:
    if re.search(r"\b(dokumen|pengujian|pendahuluan|deskripsi|prosedur|"
                 r"pengendalian|persetujuan)\b", heading_text):
        return "id"
    return "en"


def build_template_spec(docx_path: str | Path) -> dict:
    """Ukur sebuah `.docx` template → `TemplateSpec` (dict). Deterministik, $0.

    `.doc` biner (format Word lama) TIDAK didukung python-docx — konversi ke
    `.docx` dulu (mis. Word COM / LibreOffice) sebelum memanggil ini.
    """
    path = Path(docx_path)
    doc = Document(str(path))
    body = doc.element.body

    theme_major, theme_minor = _theme_fonts(path)
    eff_body, eff_head = _effective_fonts(doc, theme_major, theme_minor)

    headings_fmt = {}
    for level in range(1, 5):
        fmt = _style_format(doc, f"Heading {level}")
        if fmt:
            headings_fmt[f"Heading {level}"] = fmt

    # Tabel: warna fill header baris-1 yang dominan + apakah pakai named style.
    header_fills = Counter()
    table_styles = Counter()
    for table in doc.tables:
        table_styles[table.style.name if table.style else "None"] += 1
        if not table.rows:
            continue
        for cell in table.rows[0].cells:
            shd = cell._tc.find(qn("w:tcPr") + "/" + qn("w:shd"))
            if shd is None:
                continue
            fill = shd.get(qn("w:fill"))
            if fill and fill not in ("auto", "FFFFFF"):
                header_fills[fill] += 1
    dominant_fill = header_fills.most_common(1)[0][0] if header_fills else None
    named = sum(v for k, v in table_styles.items() if k not in _GENERIC_TABLE_STYLES)
    generic = sum(v for k, v in table_styles.items() if k in _GENERIC_TABLE_STYLES)

    # Orientasi per-section.
    orientations = []
    for section in doc.sections:
        orient = ("landscape" if section.orientation == WD_ORIENT.LANDSCAPE
                  else "portrait")
        width = round(section.page_width.inches, 1) if section.page_width else None
        orientations.append({"orient": orient, "width_in": width})

    # Outline heading berurut + sinyal dekay (CORETAD).
    outline = []
    heading_usage = Counter()
    empty_headings = 0
    tab_in_headings = False
    for para in doc.paragraphs:
        name = para.style.name if para.style else ""
        match = re.fullmatch(r"Heading (\d)", name)
        if name != "Title" and match is None:
            continue
        heading_usage[name] += 1
        text = para.text.strip()
        if not text:
            empty_headings += 1
        if "\t" in para.text:
            tab_in_headings = True
        level = 0 if name == "Title" else int(match.group(1))
        outline.append({"level": level, "text": re.sub(r"\s+", " ", text)[:90],
                        "empty": not text})

    n_toc = (sum(1 for it in body.findall(".//" + qn("w:instrText"))
                 if it.text and "TOC" in it.text)
             + sum(1 for fs in body.findall(".//" + qn("w:fldSimple"))
                   if "TOC" in (fs.get(qn("w:instr")) or "")))
    n_images = (len(body.findall(".//" + qn("w:drawing")))
                + len(body.findall(".//" + qn("w:pict"))))

    all_heading_text = " ".join(o["text"].lower() for o in outline)
    present_styles = {s.name for s in doc.styles}

    return {
        "source_name": path.stem,
        "doc_kind_guess": _guess_kind(all_heading_text),
        "language_guess": _guess_language(all_heading_text),
        "visual": {
            "effective_body_font": eff_body,
            "effective_heading_font": eff_head,
            "base_size_pt": _docdefault_size(doc) or 11,
            "theme_major_font": theme_major,
            "theme_minor_font": theme_minor,
            "title": _style_format(doc, "Title"),
            "headings": headings_fmt,
            "table_header_fill": dominant_fill,
            "table_header_fill_all": dict(header_fills),
            "table_uses_named_style": named > generic,
            "table_styles": dict(table_styles),
            "orientations": orientations,
            "has_landscape": any(o["orient"] == "landscape" for o in orientations),
        },
        "structure": {
            "n_paragraphs": len(doc.paragraphs),
            "n_tables": len(doc.tables),
            "n_images": n_images,
            "n_sections": len(doc.sections),
            "n_toc_fields": n_toc,
            "heading_usage": dict(heading_usage),
            "outline": outline,
        },
        "styles_present": [s for s in PANDOC_STYLES if s in present_styles],
        "decay": {"empty_headings": empty_headings,
                  "tab_in_headings": tab_in_headings},
    }
