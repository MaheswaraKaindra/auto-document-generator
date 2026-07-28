"""Tes endpoint /templates (V2 upload template). Docx sintetis (python-docx),
store di-redirect ke tmp — tanpa LLM, tanpa docx vendor. build_reference memakai
pandoc asli (seperti test compiler lain)."""
import io

import pytest
from docx import Document
from fastapi.testclient import TestClient

from app.main import app
from app.services import compiler_service

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    """Jangan tulis template ke data/ asli — redirect store ke tmp pytest."""
    monkeypatch.setattr(compiler_service, "TEMPLATES_STORE", tmp_path / "templates")


@pytest.fixture
def client():
    return TestClient(app)


def _docx_bytes(headings):
    doc = Document()
    doc.add_paragraph("Judul Dokumen", style="Title")
    for h in headings:
        doc.add_paragraph(h, style="Heading 1")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_upload_compiles_registers_and_is_usable_in_generate(client):
    data = _docx_bytes(["Deskripsi Aplikasi", "Use Case", "Lampiran"])
    resp = client.post(
        "/templates",
        files={"file": ("vendor_sdd.docx", data, DOCX_MIME)},
        data={"name": "Vendor SDD", "doc_types": "SDD"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    tid = body["manifest"]["template_id"]
    assert tid == "vendor-sdd"
    assert body["manifest"]["doc_types"] == {"SDD": "SDD.md"}

    # rencana peta ikut di respons (untuk ditinjau)
    bindings = {m["text"]: m["binding"] for m in body["mappings"]["SDD"]}
    assert bindings["Deskripsi Aplikasi"] == "app_description"
    assert bindings["Use Case"] == "use_cases"
    assert bindings["Lampiran"] == "manual"          # tak dikenali → placeholder jujur

    # terdaftar, muncul di daftar (dengan doc_types), DAN lolos validasi generate
    listed = client.get("/templates").json()["templates"]
    entry = next(t for t in listed if t["id"] == tid)
    assert entry["doc_types"] == ["SDD"]
    assert entry["source"] == "compiled"
    compiler_service.validate_template(tid, "SDD")   # tak melempar = bisa dipakai generate

    detail = client.get(f"/templates/{tid}")
    assert detail.status_code == 200
    assert detail.json()["manifest"]["template_id"] == tid


def test_upload_with_llm_mapping_opt_in(client, monkeypatch):
    """use_llm_mapping=true meng-opt-in pemeta LLM (di-mock di boundary, $0). Bab
    asing yang heuristik tandai 'manual' kini terpetakan lewat jawaban LLM."""
    import app.services.llm_mapping_service as lm
    monkeypatch.setattr(
        lm, "_request_bindings",
        lambda outline, doc_type: {0: "skip", 1: "app_description", 2: "feature_requirements"},
    )
    data = _docx_bytes(["Vision Statement", "Business Capabilities"])
    resp = client.post(
        "/templates",
        files={"file": ("dynamics.docx", data, DOCX_MIME)},
        data={"doc_types": "SDD", "use_llm_mapping": "true"},
    )
    assert resp.status_code == 201, resp.text
    bindings = {m["text"]: m["binding"] for m in resp.json()["mappings"]["SDD"]}
    assert bindings["Vision Statement"] == "app_description"
    assert bindings["Business Capabilities"] == "feature_requirements"


def test_upload_rejects_doc_and_non_docx(client):
    doc = client.post("/templates", files={"file": ("lama.doc", b"\xd0\xcf", "application/msword")})
    assert doc.status_code == 422
    assert ".docx" in doc.json()["detail"]

    txt = client.post("/templates", files={"file": ("catatan.txt", b"halo", "text/plain")})
    assert txt.status_code == 422


def test_upload_rejects_garbage_and_empty(client):
    garbage = client.post(
        "/templates", files={"file": ("palsu.docx", b"ini bukan docx sama sekali", DOCX_MIME)})
    assert garbage.status_code == 422          # PackageNotFoundError → 422, bukan 500

    empty = client.post("/templates", files={"file": ("kosong.docx", b"", DOCX_MIME)})
    assert empty.status_code == 422


def test_list_templates_includes_builtins_with_doc_types(client):
    templates = client.get("/templates").json()["templates"]
    by_id = {t["id"]: t for t in templates}
    assert by_id["default"]["doc_types"] == ["SDD", "UAT"]
    assert by_id["default"]["source"] == "builtin"
    # premco kini menyediakan SDD DAN UAT — frontend membaca ini, bukan hardcode
    assert by_id["premco"]["doc_types"] == ["SDD", "UAT"]


def test_get_unknown_template_is_404(client):
    assert client.get("/templates/tidak-ada").status_code == 404


def _upload(client, headings, name="Vendor"):
    resp = client.post(
        "/templates",
        files={"file": (f"{name}.docx", _docx_bytes(headings), DOCX_MIME)},
        data={"name": name, "doc_types": "SDD"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_tinjauan_manusia_menyimpan_peta_dan_regenerate_template(client):
    """Langkah terakhir yang tak bisa diotomatiskan.

    Ekstraksi menemukan babnya dan pemeta menebak isinya, tapi cuma pemberi
    template yang tahu bab bernama asing itu sebetulnya deskripsi aplikasi."""
    body = _upload(client, ["Bab Asing Yang Tak Dikenali", "Lampiran"])
    template_id = body["manifest"]["template_id"]
    plan = body["mappings"]["SDD"]
    # Heuristik menyerah pada nama asing -> placeholder jujur, bukan tebakan.
    assert all(p["binding"] != "app_description" for p in plan)

    bindings = [p["binding"] for p in plan]
    bindings[[p["text"] for p in plan].index("Bab Asing Yang Tak Dikenali")] = "app_description"
    resp = client.put(f"/templates/{template_id}/mappings/SDD",
                      json={"bindings": bindings})

    assert resp.status_code == 200, resp.text
    updated = resp.json()["mappings"]["SDD"]
    assert updated[[p["text"] for p in plan].index("Bab Asing Yang Tak Dikenali")][
        "binding"] == "app_description"
    # Struktur bab tak boleh ikut bergeser: itu hasil PENGUKURAN dokumen sumber.
    assert [p["text"] for p in updated] == [p["text"] for p in plan]
    assert [p["level"] for p in updated] == [p["level"] for p in plan]
    # Template Jinja ikut di-generate ulang — kalau tidak, suntingan cuma tersimpan
    # di JSON dan dokumennya keluar sama saja seperti sebelum ditinjau.
    rendered = (compiler_service.TEMPLATES_STORE / template_id / "SDD.md").read_text(
        encoding="utf-8")
    assert "app_description" in rendered


def test_tinjauan_menolak_peta_yang_merusak(client):
    body = _upload(client, ["Deskripsi Aplikasi", "Use Case"])
    template_id = body["manifest"]["template_id"]
    plan = body["mappings"]["SDD"]
    bindings = [p["binding"] for p in plan]

    # Jumlah tak cocok: peta harus utuh, satu binding per bab.
    assert client.put(f"/templates/{template_id}/mappings/SDD",
                      json={"bindings": bindings[:-1]}).status_code == 422
    # Binding karangan.
    assert client.put(f"/templates/{template_id}/mappings/SDD",
                      json={"bindings": ["ngawur"] * len(bindings)}).status_code == 422
    # Satu isi dipakai dua bab: bab kedua cuma akan menyalin bab pertama, jadi
    # ditolak TERANG-TERANGAN daripada di-dedup diam-diam seperti pemeta otomatis.
    duplicated = ["app_description"] * len(bindings)
    resp = client.put(f"/templates/{template_id}/mappings/SDD",
                      json={"bindings": duplicated})
    assert resp.status_code == 422
    assert "app_description" in resp.json()["detail"]

    assert client.put("/templates/entah-apa/mappings/SDD",
                      json={"bindings": ["manual"]}).status_code == 404
    assert client.put(f"/templates/{template_id}/mappings/UAT",
                      json={"bindings": bindings}).status_code == 404


def test_daftar_binding_tersedia_untuk_dropdown(client):
    """Path statis harus menang atas `/{template_id}` — kalau urutan deklarasinya
    terbalik, parameter menelan "bindings" dan endpoint ini balas 404 diam-diam."""
    resp = client.get("/templates/bindings")
    assert resp.status_code == 200
    bindings = resp.json()["bindings"]
    assert {"skip", "manual", "heading_only", "app_description"} <= set(bindings)
