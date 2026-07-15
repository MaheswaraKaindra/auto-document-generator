"""
Compiler service (Peran 3 — Backend & Templating).

Alur: DocumentContent (Contract B, dari LLMService milik Peran 2)
      -> render diagram Mermaid jadi gambar
      -> render template Jinja2 (Markdown)
      -> export ke .docx lewat pypandoc.

Tidak menyentuh/menduplikasi logika Peran 1 (parser_service.py) atau
Peran 2 (llm_service.py) — modul ini murni konsumen dari Contract B.
"""

import base64
import tempfile
import uuid
from pathlib import Path
from typing import Any

import pypandoc
import requests
from jinja2 import Environment, FileSystemLoader

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


def _render_mermaid_to_image(mermaid_script: str, images_dir: Path) -> str:
    """
    Render satu script Mermaid jadi file gambar PNG.

    Implementasi saat ini pakai layanan hosted mermaid.ink (GET request,
    base64 dari teks mermaid) — sudah diverifikasi jalan lewat tes
    end-to-end (termasuk pipeline penuh ke repo GitHub asli).

    PERHATIAN: cara ini mengirim ISI DIAGRAM (bisa memuat nama endpoint,
    struktur komponen internal) ke layanan pihak ketiga lewat internet.
    Untuk data yang confidential (repo perusahaan), ganti fungsi ini
    dengan rendering lokal (mis. mermaid-cli) sebelum dipakai di
    lingkungan produksi.
    """
    images_dir.mkdir(parents=True, exist_ok=True)

    encoded = base64.urlsafe_b64encode(mermaid_script.encode("utf-8")).decode("ascii")
    url = f"https://mermaid.ink/img/{encoded}"

    response = requests.get(url, timeout=30)
    response.raise_for_status()

    image_path = images_dir / f"{uuid.uuid4().hex}.png"
    image_path.write_bytes(response.content)
    return str(image_path)


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

    return {
        **data,
        "feature_requirements": cleaned_features,
        "use_cases": cleaned_use_cases,
        "diagrams": {
            "system_architecture_image": _render_mermaid_to_image(
                diagrams["system_architecture"], IMAGES_DIR
            ),
            "component_integration_image": _render_mermaid_to_image(
                diagrams["component_integration"], IMAGES_DIR
            ),
            "use_case_diagram_image": _render_mermaid_to_image(
                diagrams["use_case_diagram"], IMAGES_DIR
            ),
            "activity_diagrams": [
                {
                    "activity_name": activity["activity_name"],
                    "description": activity["description"],
                    "image_path": _render_mermaid_to_image(
                        activity["mermaid_script"], IMAGES_DIR
                    ),
                }
                for activity in diagrams.get("activity_diagrams", [])
            ],
        },
    }


def _build_uat_context(data: dict[str, Any]) -> dict[str, Any]:
    # Ganti newline jadi "; " supaya tidak merusak baris tabel Markdown
    # (satu baris tabel Markdown wajib satu baris teks).
    cleaned_cases = [
        {**tc, "steps": tc["steps"].replace("\n", "; ")}
        for tc in data.get("uat_test_cases", [])
    ]
    return {**data, "uat_test_cases": cleaned_cases}


def generate_docx(document_type: str, document_content: dict[str, Any], project_name: str = "") -> str:
    """
    Entry point utama Peran 3.

    document_type: "SDD" atau "UAT" (menentukan template mana yang dipakai).
    document_content: dict hasil DocumentContent.model_dump() dari LLMService
                       milik Peran 2 (Contract B), atau dummy JSON dengan
                       skema yang sama.
    Mengembalikan path file .docx yang sudah jadi.
    """
    normalized_type = document_type.upper()
    template_name = _TEMPLATE_BY_DOC_TYPE.get(normalized_type)
    if template_name is None:
        raise ValueError(f"document_type tidak dikenal: {document_type!r} (harus 'SDD' atau 'UAT')")

    context = {"project_name": project_name, **document_content}

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
            extra_args=["--standalone", "--toc"],
        )
    except OSError as e:
        raise RuntimeError(
            "Pandoc tidak ditemukan di sistem. Install pandoc terlebih dahulu "
            "(https://pandoc.org/installing.html) atau jalankan "
            "`python -c \"import pypandoc; pypandoc.download_pandoc()\"` sekali."
        ) from e

    return str(output_path)
