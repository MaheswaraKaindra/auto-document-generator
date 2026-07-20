"""Tes split diagram use case per-aktor (fix panah menyilang — temuan Flowy).
Parse PlantUML use case LLM → IR → render per-aktor, dengan fallback ke diagram
tunggal. plantuml.jar di-mock (proses eksternal), sisanya asli.
"""
import io
import json
from pathlib import Path

from PIL import Image

from app.domain.exceptions import DiagramRenderError
from app.services import compiler_service as C

_DUMMY = Path(__file__).resolve().parent.parent / "dummy_data" / "document_content_sdd.json"

_MULTI = """@startuml
left to right direction
actor Admin
actor "Petugas Approval" as Approver
rectangle "Sistem X" {
  usecase "Kelola Pengguna" as UC1
  usecase "Setujui Permintaan" as UC2
  usecase "Login" as UC3
}
Admin --> UC1
Admin --> UC3
Approver --> UC2
Approver --> UC3
@enduml"""

_SINGLE = """@startuml
actor Admin
rectangle "Sys" {
  usecase "Kelola" as UC1
}
Admin --> UC1
@enduml"""


def _png():
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), (240, 240, 240)).save(buf, "PNG")
    return buf.getvalue()


# --- Parser -------------------------------------------------------------------
def test_parse_multi_actor():
    ir = C._usecase_plantuml_to_ir(_MULTI)
    assert {a.label for a in ir.actors} == {"Admin", "Petugas Approval"}
    assert {a.id for a in ir.actors} == {"Admin", "Approver"}   # bare id=label, alias=Approver
    assert len(ir.use_cases) == 3
    assert len(ir.associations) == 4
    assert ir.system_name == "Sistem X"


def test_parse_garbage_or_incomplete_returns_none():
    assert C._usecase_plantuml_to_ir("bukan plantuml sama sekali") is None
    assert C._usecase_plantuml_to_ir("@startuml\nactor Admin\n@enduml") is None   # tanpa usecase
    assert C._usecase_plantuml_to_ir(
        '@startuml\nusecase "X" as UC1\n@enduml') is None                          # tanpa actor


# --- Split --------------------------------------------------------------------
def test_split_multi_actor_produces_one_per_actor(monkeypatch, tmp_path):
    monkeypatch.setattr(C, "_run_plantuml", lambda *a, **k: _png())
    imgs = C._split_usecase_images(_MULTI, tmp_path)
    assert len(imgs) == 2
    assert {d["actor"] for d in imgs} == {"Admin", "Petugas Approval"}
    for d in imgs:
        assert d["image"].endswith(".png")
        assert Path(d["image"]).exists()
        assert d["attr"].startswith("{") and "in}" in d["attr"]


def test_split_single_actor_returns_none(monkeypatch, tmp_path):
    # < 2 aktor: split tak berguna -> None -> pemanggil pakai diagram tunggal
    monkeypatch.setattr(C, "_run_plantuml", lambda *a, **k: _png())
    assert C._split_usecase_images(_SINGLE, tmp_path) is None


def test_split_render_failure_falls_back_to_none(monkeypatch, tmp_path):
    def boom(*a, **k):
        raise DiagramRenderError("render gagal")
    monkeypatch.setattr(C, "_run_plantuml", boom)
    assert C._split_usecase_images(_MULTI, tmp_path) is None   # nol regresi: fallback


# --- Integrasi ke _build_sdd_context -----------------------------------------
def test_build_sdd_context_split_vs_single(monkeypatch, tmp_path):
    monkeypatch.setattr(C, "_run_plantuml", lambda *a, **k: _png())
    monkeypatch.setattr(C, "IMAGES_DIR", tmp_path)
    data = json.loads(_DUMMY.read_text(encoding="utf-8"))
    data["diagrams"]["use_case_diagram"] = _MULTI

    split = C._build_sdd_context(data, render_integration=True, split_usecase=True)["diagrams"]
    assert split["use_case_diagrams_by_actor"] is not None
    assert len(split["use_case_diagrams_by_actor"]) == 2
    assert split["use_case_figure_count"] == 2
    assert split["use_case_diagram_image"] is None            # gabungan tak dirender

    single = C._build_sdd_context(data, render_integration=True, split_usecase=False)["diagrams"]
    assert single["use_case_diagrams_by_actor"] is None
    assert single["use_case_figure_count"] == 1               # offset activity tetap +4
    assert single["use_case_diagram_image"] is not None


def test_default_template_splits_usecase_premco_does_not():
    assert C._resolve_template("default", "SDD").splits_usecase is True
    assert C._resolve_template("premco", "SDD").splits_usecase is False
