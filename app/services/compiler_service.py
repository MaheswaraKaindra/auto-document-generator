"""
Compiler service (Peran 3 — Backend & Templating).

Alur: DocumentContent (Contract B, dari LLMService milik Peran 2)
      -> render diagram PlantUML jadi gambar (LOKAL, lewat plantuml.jar)
      -> render template Jinja2 (Markdown)
      -> export ke .docx lewat pypandoc.

Tidak menyentuh/menduplikasi logika Peran 1 (parser_service.py) atau
Peran 2 (llm_service.py) — modul ini murni konsumen dari Contract B.
"""

import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any

import pypandoc
from jinja2 import Environment, FileSystemLoader
from PIL import Image

from app.core import config
from app.domain.exceptions import DiagramRenderError

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
OUTPUT_DIR = Path(tempfile.gettempdir()) / "auto_document_generator"
IMAGES_DIR = OUTPUT_DIR / "images"

# autoescape=False karena output-nya Markdown, bukan HTML — auto-escaping
# justru akan merusak karakter Markdown biasa (*, _, |, dst).
_jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
)

_TEMPLATE_BY_DOC_TYPE = {
    "SDD": "sdd_template.md",
    "UAT": "uat_template.md",
}

# Judul dokumen — masuk ke halaman pertama DAN ke kaki tiap halaman. Sengaja di
# sini, bukan sebagai `# Judul` di template: Pandoc merendernya dengan style
# `Title` (yang memang untuk itu) dan sekaligus menyimpannya ke docProps, tempat
# field TITLE di kaki halaman membacanya.
_TITLE_BY_DOC_TYPE = {
    "SDD": "Solution Design Document",
    "UAT": "Dokumen User Acceptance Testing (UAT)",
}

# Kerangka tampilan: font, gaya heading, dan kaki halaman bernomor. Dibangun oleh
# scripts/build_reference_docx.py — bukan file biner misterius.
REFERENCE_DOCX = TEMPLATES_DIR / "reference.docx"

# Ketajaman render PlantUML. Default PlantUML 96 dpi — cukup untuk layar, buram
# untuk cetak (pelajaran yang sama dengan mermaid.ink dulu: layak cetak butuh
# ≥150 dpi, dan produk lama memakai ~246 dpi lewat width=1600). 200 dpi ~2x
# ukuran piksel default: tajam di kertas tanpa membengkakkan docx.
_PLANTUML_DPI = 200

# Gaya visual diagram disuntik DI SINI, bukan ditulis LLM — filosofi yang sama
# dengan reference.docx: rupa dokumen diatur dari satu tempat yang deterministik,
# bukan dari output model yang bisa berubah-ubah antar panggilan. `!theme plain`
# = UML klasik hitam-putih, gaya yang dipakai dokumen acuan enterprise.
_PLANTUML_STYLE_PREAMBLE = ("!theme plain", f"skinparam dpi {_PLANTUML_DPI}")

# Ruang yang benar-benar tersedia di halaman, dipakai _image_attr untuk membatasi
# ukuran tampil diagram. Lebar: 8,5 inci dikurangi margin 1 inci di dua sisi.
# Tinggi: 11 dikurangi margin, dikurangi lagi ruang untuk judul sub-bab dan
# caption di bawah gambar — 8 inci konservatif, dan lebih baik diagram sedikit
# lebih kecil daripada tumpah ke halaman berikutnya.
_PAGE_WIDTH_IN = 6.5
_PAGE_HEIGHT_IN = 8.0

_MANUAL_PLACEHOLDER = "*(diisi manual)*"


class _MetadataDict(dict):
    """dict yang mengembalikan penanda *(diisi manual)* untuk field yang tidak
    diisi pengguna.

    Alasan pakai __missing__ ketimbang daftar field eksplisit: daftar itu harus
    disinkronkan manual dengan DocumentMetadata di layer API, dan compiler tidak
    boleh mengimpor ke atas ke layer API. Dengan cara ini menambah field metadata
    cuma menyentuh schema + template — tidak ada daftar ketiga yang bisa basi.
    """

    def __missing__(self, key: str) -> str:
        return _MANUAL_PLACEHOLDER


def _build_metadata_context(document_metadata: dict[str, Any] | None) -> _MetadataDict:
    """Ambil field yang benar-benar diisi; sisanya biar __missing__ yang jawab.

    String kosong/spasi diperlakukan sama dengan tidak diisi — input form yang
    dikosongkan pengguna tidak boleh menghasilkan sel tabel kosong melompong.
    """
    filled = {
        key: value.strip()
        for key, value in (document_metadata or {}).items()
        if isinstance(value, str) and value.strip()
    }
    return _MetadataDict(filled)


def _strip_code_fence(diagram_script: str) -> str:
    """Buang code fence Markdown (```plantuml ... ```) kalau LLM terlanjur
    menyertakannya — fence bukan bagian bahasa diagram mana pun."""
    script = diagram_script.strip()
    if not script.startswith("```"):
        return script
    lines = [ln for ln in script.splitlines() if not ln.strip().startswith("```")]
    return "\n".join(lines).strip()


def _normalize_plantuml(diagram_script: str) -> str:
    """Siapkan script LLM untuk plantuml.jar: buang fence, pastikan terbungkus
    @startuml/@enduml, lalu suntik preamble gaya (theme + dpi) TEPAT sesudah
    @startuml.

    Preamble disuntik di sini dan LLM DILARANG menulis theme/skinparam sendiri
    (lihat SYSTEM_PROMPT llm_service): rupa diagram harus datang dari satu tempat
    deterministik, bukan dari selera model yang berubah antar panggilan — filosofi
    yang sama dengan reference.docx untuk rupa dokumen.
    """
    script = _strip_code_fence(diagram_script)
    if "@startuml" not in script:
        script = f"@startuml\n{script}\n@enduml"

    lines = []
    injected = False
    for line in script.splitlines():
        lines.append(line)
        if not injected and line.strip().startswith("@startuml"):
            lines.extend(_PLANTUML_STYLE_PREAMBLE)
            injected = True
    return "\n".join(lines)


def _run_plantuml(plantuml_source: str) -> bytes:
    """Jalankan plantuml.jar (mode -pipe: source di stdin, PNG di stdout).

    Dipisah dari _render_diagram_to_image supaya test bisa me-mock PROSES
    EKSTERNALNYA saja — normalisasi script dan penulisan file tetap teruji asli.

    Render LOKAL, bukan layanan hosted — dua alasan, satu keputusan (2026-07-16):
    (1) privasi: isi diagram (nama endpoint, struktur komponen) tidak lagi
    meninggalkan mesin — keterbatasan mermaid.ink yang tercatat sejak awal;
    (2) rupa: PlantUML menggambar UML sungguhan (aktor stick-figure, oval use
    case, start/stop activity) — bahasa visual dokumen acuan enterprise, dipilih
    pemilik project lewat perbandingan berdampingan (scripts/diagram_comparison.py).

    -Playout=smetana: layout engine Java murni bawaan jar. Tanpa ini diagram
    use case & component menuntut Graphviz/dot terpasang terpisah di sistem —
    dependency kedua yang diam-diam, gagal hanya di mesin yang tidak punya.
    """
    jar = Path(config.PLANTUML_JAR)
    if not jar.is_file():
        raise DiagramRenderError(
            f"plantuml.jar tidak ditemukan di '{jar}'. Unduh dari "
            f"https://github.com/plantuml/plantuml/releases (asset "
            f"plantuml-<versi>.jar), simpan sebagai tools/plantuml.jar, atau "
            f"tunjuk lokasinya lewat PLANTUML_JAR di .env."
        )

    try:
        result = subprocess.run(
            ["java", "-jar", str(jar), "-pipe", "-tpng",
             "-charset", "UTF-8", "-Playout=smetana"],
            input=plantuml_source.encode("utf-8"),
            capture_output=True,
            timeout=120,
        )
    except FileNotFoundError as e:
        raise DiagramRenderError(
            "Java tidak ditemukan di PATH — render diagram PlantUML butuh "
            "Java 17+ terpasang."
        ) from e
    except subprocess.TimeoutExpired as e:
        raise DiagramRenderError(
            "PlantUML tidak selesai merender dalam 120 detik — script diagram "
            "kemungkinan terlalu besar."
        ) from e

    # PlantUML MENGGAMBAR pesan syntax error sebagai gambar (exit code tetap
    # non-nol) — kalau cuma percaya stdout, error itu ter-embed diam-diam ke
    # dokumen sebagai "diagram". Periksa exit code DAN magic number PNG.
    if result.returncode != 0 or not result.stdout.startswith(b"\x89PNG"):
        stderr = result.stderr.decode("utf-8", "replace").strip()
        raise DiagramRenderError(
            f"PlantUML menolak script diagram: {stderr[:400] or 'tanpa detail'} "
            f"(cek syntax PlantUML-nya)."
        )
    return result.stdout


def _render_diagram_to_image(diagram_script: str, images_dir: Path) -> str:
    """Render satu script PlantUML jadi file PNG lokal; kembalikan path-nya."""
    images_dir.mkdir(parents=True, exist_ok=True)
    png = _run_plantuml(_normalize_plantuml(diagram_script))
    image_path = images_dir / f"{uuid.uuid4().hex}.png"
    image_path.write_bytes(png)
    return str(image_path)


def _image_attr(image_path: str) -> str:
    """Atribut ukuran Pandoc (`{width=...}` / `{height=...}`) untuk satu diagram.

    Tanpa ini semua gambar direntangkan selebar halaman, dan activity diagram itu
    TINGGI DAN SEMPIT — terukur pada esteler: 5 dari 11 diagram ditanam setinggi
    9,7 sampai 17,2 inci di halaman yang ruang pakainya cuma ~9 inci. Tumpah
    keluar halaman.

    Aturannya satu kalimat: batasi sisi yang lebih dulu mentok. Diagram lebar
    dibatasi LEBARNYA, diagram tinggi dibatasi TINGGINYA — sisi satunya ikut
    proporsional, jadi tidak ada yang gepeng.

    Pillow, bukan parsing header PNG manual: JPEG yang dibaca sebagai PNG
    menghasilkan angka ngawur TANPA error (65536 x 4293001688 — betulan terjadi
    di sesi ini). Pillow memvalidasi formatnya dan gagal berisik.
    """
    with Image.open(image_path) as image:
        width, height = image.size
    if height / width > _PAGE_HEIGHT_IN / _PAGE_WIDTH_IN:
        return f"{{height={_PAGE_HEIGHT_IN}in}}"
    return f"{{width={_PAGE_WIDTH_IN}in}}"


def _build_sdd_context(data: dict[str, Any]) -> dict[str, Any]:
    diagrams = data["diagrams"]

    # Ganti newline jadi spasi supaya tidak merusak baris tabel Markdown
    # (satu baris tabel Markdown wajib satu baris teks) — sama seperti
    # penanganan uat_test_cases di _build_uat_context.
    cleaned_features = [
        {**feature, "description": feature["description"].replace("\n", " ")}
        for feature in data.get("feature_requirements", [])
    ]
    cleaned_use_cases = [
        {
            **uc,
            "description": uc["description"].replace("\n", " "),
            "pre_condition": uc["pre_condition"].replace("\n", " "),
            "acceptance_criteria": [ac.replace("\n", " ") for ac in uc.get("acceptance_criteria", [])],
        }
        for uc in data.get("use_cases", [])
    ]
    cleaned_roles = [
        {**role, "description": role["description"].replace("\n", " ")}
        for role in data.get("user_roles", [])
    ]
    cleaned_requirements = [
        {**req, "detail": req["detail"].replace("\n", " ")}
        for req in data.get("system_requirements", [])
    ]
    cleaned_flow_steps = [step.replace("\n", " ") for step in data.get("business_flow_steps", [])]

    # Empat diagram tetap diakses dengan diagrams[...] — sengaja KeyError kalau
    # hilang: dokumen tanpa salah satunya cacat, dan lebih baik gagal berisik.
    architecture = _render_diagram_to_image(diagrams["system_architecture"], IMAGES_DIR)
    integration = _render_diagram_to_image(diagrams["component_integration"], IMAGES_DIR)
    business_flow = _render_diagram_to_image(diagrams["business_process_flow"], IMAGES_DIR)
    use_case = _render_diagram_to_image(diagrams["use_case_diagram"], IMAGES_DIR)

    return {
        **data,
        "feature_requirements": cleaned_features,
        "use_cases": cleaned_use_cases,
        "user_roles": cleaned_roles,
        "system_requirements": cleaned_requirements,
        "business_flow_steps": cleaned_flow_steps,
        "diagrams": {
            "system_architecture_image": architecture,
            "system_architecture_attr": _image_attr(architecture),
            "component_integration_image": integration,
            "component_integration_attr": _image_attr(integration),
            "business_process_flow_image": business_flow,
            "business_process_flow_attr": _image_attr(business_flow),
            "use_case_diagram_image": use_case,
            "use_case_diagram_attr": _image_attr(use_case),
            "activity_diagrams": [
                {
                    "activity_name": activity["activity_name"],
                    "description": activity["description"],
                    "actor": activity["actor"].replace("\n", " "),
                    "pre_condition": activity["pre_condition"].replace("\n", " "),
                    "steps": [s.replace("\n", " ") for s in activity["steps"]],
                    "image_path": path,
                    "image_attr": _image_attr(path),
                }
                for activity, path in (
                    (a, _render_diagram_to_image(a["diagram_script"], IMAGES_DIR))
                    for a in diagrams.get("activity_diagrams", [])
                )
            ],
        },
    }


def _document_title(normalized_type: str, project_name: str) -> str:
    """Judul dokumen: dipakai DUA kali oleh Word — sebagai judul besar di halaman
    pertama (style `Title`), dan sebagai teks di kaki SETIAP halaman (field
    `TITLE` di reference.docx membacanya dari docProps). Satu sumber, dua tempat.

    Meniru acuan, yang menaruh judul yang sama di kedua tempat itu."""
    label = _TITLE_BY_DOC_TYPE[normalized_type]
    return f"{label} — {project_name}" if project_name.strip() else label


def _pandoc_args(normalized_type: str, title: str) -> list[str]:
    """Argumen Pandoc per jenis dokumen.

    `--reference-doc` membawa TAMPILAN: font, gaya heading, dan yang paling
    penting **kaki halaman berisi nomor halaman**. Kerangka bawaan Pandoc tidak
    punya footer sama sekali (diperiksa langsung), dan itu bukan cuma soal rupa:
    Daftar Gambar menulis "Gambar 4 ... 14" sementara tidak ada halaman yang
    bertuliskan "14", jadi pembaca harus menghitung dari depan. Indeksnya tidak
    bisa dipakai. Lihat `scripts/build_reference_docx.py`.

    Judul daftar dibuat Indonesia lewat DUA mekanisme Pandoc yang BERBEDA — bukan
    gaya-gayaan, memang begitu writer docx-nya:
      `lang=id`   -> "Daftar Gambar" / "Daftar Tabel" (terjemahan bawaan;
                     `lof-title`/`lot-title` DIABAIKAN oleh writer docx — diuji)
      `toc-title` -> "Daftar Isi" (yang ini justru TIDAK ikut `lang`)

    `--lof`/`--lot` (Daftar Gambar & Daftar Tabel) khusus SDD, dan itu bukan
    kemalasan: UAT punya NOL gambar dan cuma satu tabel isi (Case Pengujian) —
    sisanya front-matter yang memang tidak di-caption. Memasangnya di UAT
    menghasilkan dua halaman indeks KOSONG di tiap dokumen. Halaman hampa lebih
    buruk daripada tidak ada halamannya sama sekali.

    Pandoc menulis kedua daftar itu sebagai FIELD CODE Word
    (`TOC \\h \\z \\t "Image Caption" \\c`), bukan teks jadi — jadi WORD yang
    menghitung nomor halamannya saat dokumen dibuka, dan kita tidak perlu tahu
    pagination sama sekali dari sisi Markdown. Diverifikasi dengan MEMBUKA docx di
    Word sungguhan (11 baris + nomor halaman, tanpa refresh manual); membaca
    XML-nya saja tidak akan pernah membuktikan itu.
    """
    args = [
        "--standalone",
        "--toc",
        "-M",
        "lang=id",
        "-M",
        "toc-title=Daftar Isi",
        "-M",
        f"title={title}",
        f"--reference-doc={REFERENCE_DOCX}",
    ]
    if normalized_type == "SDD":
        args += ["--lof", "--lot"]
    return args


def _build_uat_context(data: dict[str, Any]) -> dict[str, Any]:
    # Ganti newline jadi "; " supaya tidak merusak baris tabel Markdown
    # (satu baris tabel Markdown wajib satu baris teks).
    cleaned_cases = [
        {**tc, "steps": tc["steps"].replace("\n", "; ")}
        for tc in data.get("uat_test_cases", [])
    ]
    return {**data, "uat_test_cases": cleaned_cases}


def generate_docx(
    document_type: str,
    document_content: dict[str, Any],
    project_name: str = "",
    document_metadata: dict[str, Any] | None = None,
) -> str:
    """
    Entry point utama Peran 3.

    document_type: "SDD" atau "UAT" (menentukan template mana yang dipakai).
    document_content: dict hasil DocumentContent.model_dump() dari LLMService
                       milik Peran 2 (Contract B), atau dummy JSON dengan
                       skema yang sama.
    document_metadata: isian manusia dari form (nomor RFC, demografi, dst).
                       None/kosong = template pakai penanda *(diisi manual)*
                       seperti sebelum form ini ada.
    Mengembalikan path file .docx yang sudah jadi.
    """
    normalized_type = document_type.upper()
    template_name = _TEMPLATE_BY_DOC_TYPE.get(normalized_type)
    if template_name is None:
        raise ValueError(f"document_type tidak dikenal: {document_type!r} (harus 'SDD' atau 'UAT')")

    context = {
        "project_name": project_name,
        "meta": _build_metadata_context(document_metadata),
        **document_content,
    }

    if normalized_type == "SDD":
        context = {**context, **_build_sdd_context(document_content)}
    else:
        context = {**context, **_build_uat_context(document_content)}

    template = _jinja_env.get_template(template_name)
    rendered_markdown = template.render(**context)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"{normalized_type}_{uuid.uuid4().hex}.docx"

    try:
        pypandoc.convert_text(
            rendered_markdown,
            to="docx",
            format="md",
            outputfile=str(output_path),
            extra_args=_pandoc_args(
                normalized_type, _document_title(normalized_type, project_name)
            ),
        )
    except OSError as e:
        raise RuntimeError(
            "Pandoc tidak ditemukan di sistem. Install pandoc terlebih dahulu "
            "(https://pandoc.org/installing.html) atau jalankan "
            "`python -c \"import pypandoc; pypandoc.download_pandoc()\"` sekali."
        ) from e

    return str(output_path)
