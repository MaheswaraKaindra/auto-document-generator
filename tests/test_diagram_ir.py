"""Tes layer diagram: Diagram IR + PlantUML Renderer (Option C, 2026-07-20).

Menguji renderer BERDIRI SENDIRI: konstruksi IR di tangan -> render -> assert
source PlantUML. TIDAK memanggil pipeline live (yang tetap memakai PlantUML LLM),
jadi output DOCX tak tersentuh. Tanpa Java: assertion di STRING PlantUML
(deterministik), plus satu cek kompatibilitas dengan compiler_service.
_normalize_plantuml (murni string) untuk membuktikan output renderer masuk ke
jalur render yang sama.
"""
import pytest

from app.diagram.ir import (
    Actor,
    ActivityDiagramIR,
    ActivityEdge,
    ActivityNode,
    ActivityNodeKind,
    ArchEdge,
    ArchitectureDiagramIR,
    ArchNode,
    ArchNodeKind,
    Association,
    ComponentDiagramIR,
    ComponentEdge,
    ComponentNode,
    DiagramType,
    Lane,
    Package,
    UseCaseDiagramIR,
    UseCaseNode,
)
from app.diagram.renderer import PlantUMLRenderer
from app.diagram.renderer.plantuml import _DISPATCH
from app.services import compiler_service

R = PlantUMLRenderer()


# --- IR: tipe default terisi benar --------------------------------------------
def test_ir_diagram_type_defaults():
    assert ActivityDiagramIR().diagram_type == DiagramType.ACTIVITY
    assert UseCaseDiagramIR().diagram_type == DiagramType.USE_CASE
    assert ArchitectureDiagramIR().diagram_type == DiagramType.ARCHITECTURE
    assert ComponentDiagramIR().diagram_type == DiagramType.COMPONENT


# --- Activity: contoh PERSIS dari brief ---------------------------------------
def _login_activity() -> ActivityDiagramIR:
    return ActivityDiagramIR(
        title="Login",
        lanes=[Lane(id="user", label="User"), Lane(id="system", label="System")],
        nodes=[
            ActivityNode(id="start", kind=ActivityNodeKind.START, lane="user"),
            ActivityNode(id="open", kind=ActivityNodeKind.ACTION, label="Open Website", lane="user"),
            ActivityNode(id="login", kind=ActivityNodeKind.ACTION, label="Display Login", lane="system"),
            ActivityNode(id="decision", kind=ActivityNodeKind.DECISION, label="Credentials Valid", lane="system"),
            ActivityNode(id="end", kind=ActivityNodeKind.END, lane="system"),
        ],
        edges=[
            ActivityEdge(source="start", target="open"),
            ActivityEdge(source="open", target="login"),
            ActivityEdge(source="login", target="decision"),
            ActivityEdge(source="decision", target="end", guard="Valid"),
        ],
    )


def test_activity_render_matches_brief_example():
    out = R.render(_login_activity())
    lines = out.splitlines()
    assert lines[0] == "@startuml"
    assert lines[-1] == "@enduml"
    assert "start" in lines
    assert ":Open Website;" in lines
    assert ":Display Login;" in lines
    assert "if (Credentials Valid?) then (Valid)" in lines
    assert "stop" in lines
    assert "endif" in lines
    # swimlane terpakai
    assert "|User|" in lines
    assert "|System|" in lines


def test_activity_two_branch_decision_if_else():
    ir = ActivityDiagramIR(
        nodes=[
            ActivityNode(id="s", kind=ActivityNodeKind.START),
            ActivityNode(id="d", kind=ActivityNodeKind.DECISION, label="Sukses?"),
            ActivityNode(id="ok", kind=ActivityNodeKind.ACTION, label="Tampilkan dashboard"),
            ActivityNode(id="no", kind=ActivityNodeKind.ACTION, label="Tampilkan error"),
            ActivityNode(id="e1", kind=ActivityNodeKind.END),
            ActivityNode(id="e2", kind=ActivityNodeKind.END),
        ],
        edges=[
            ActivityEdge(source="s", target="d"),
            ActivityEdge(source="d", target="ok", guard="Ya"),
            ActivityEdge(source="d", target="no", guard="Tidak"),
            ActivityEdge(source="ok", target="e1"),
            ActivityEdge(source="no", target="e2"),
        ],
    )
    out = R.render(ir)
    assert "if (Sukses?) then (Ya)" in out
    assert "else (Tidak)" in out
    assert ":Tampilkan dashboard;" in out
    assert ":Tampilkan error;" in out
    assert out.count("endif") == 1


def test_activity_action_label_semicolon_stripped():
    # `;` di label akan menutup pernyataan PlantUML -> harus dibersihkan
    ir = ActivityDiagramIR(nodes=[
        ActivityNode(id="s", kind=ActivityNodeKind.START),
        ActivityNode(id="a", kind=ActivityNodeKind.ACTION, label="Isi form; klik simpan"),
        ActivityNode(id="e", kind=ActivityNodeKind.END),
    ], edges=[ActivityEdge(source="s", target="a"), ActivityEdge(source="a", target="e")])
    out = R.render(ir)
    assert ":Isi form, klik simpan;" in out          # `;` internal -> `,`
    assert out.count(";") == 1                        # hanya penutup aksi


# --- Use case -----------------------------------------------------------------
def test_usecase_render():
    ir = UseCaseDiagramIR(
        system_name="Sistem Inventaris",
        actors=[Actor(id="admin", label="Admin")],
        use_cases=[UseCaseNode(id="uc1", label="Kelola Stok")],
        associations=[Association(actor="admin", use_case="uc1")],
    )
    out = R.render(ir)
    assert "left to right direction" in out
    assert 'actor "Admin" as admin' in out
    assert 'rectangle "Sistem Inventaris" {' in out
    assert 'usecase "Kelola Stok" as uc1' in out
    assert "admin --> uc1" in out


# --- Architecture -------------------------------------------------------------
def test_architecture_render_node_kinds():
    ir = ArchitectureDiagramIR(
        nodes=[
            ArchNode(id="user", label="User", kind=ArchNodeKind.ACTOR),
            ArchNode(id="be", label="Backend API", kind=ArchNodeKind.COMPONENT),
            ArchNode(id="db", label="PostgreSQL", kind=ArchNodeKind.DATABASE),
        ],
        edges=[ArchEdge(source="user", target="be"), ArchEdge(source="be", target="db", label="query")],
    )
    out = R.render(ir)
    assert 'actor "User" as user' in out
    assert 'component "Backend API" as be' in out
    assert 'database "PostgreSQL" as db' in out
    assert "user --> be" in out
    assert "be --> db : query" in out


# --- Component ----------------------------------------------------------------
def test_component_render_packages_and_no_brackets():
    ir = ComponentDiagramIR(
        packages=[Package(id="fe", label="FE-Web")],
        nodes=[
            ComponentNode(id="login", label="Login.vue", package="fe"),
            ComponentNode(id="ep", label="POST /users/login"),   # di luar paket
        ],
        edges=[ComponentEdge(source="login", target="ep")],
    )
    out = R.render(ir)
    assert 'package "FE-Web" {' in out
    assert 'component "Login.vue" as login' in out
    assert 'component "POST /users/login" as ep' in out
    assert "login --> ep" in out
    # Referensi lewat alias id, BUKAN `[Label]` -> kebal bug kurung route-param
    assert "[" not in out


# --- Renderer TIDAK menulis gaya (itu urusan pipeline) ------------------------
@pytest.mark.parametrize("ir", [
    _login_activity(),
    UseCaseDiagramIR(system_name="S", actors=[Actor(id="a", label="A")],
                     use_cases=[UseCaseNode(id="u", label="U")],
                     associations=[Association(actor="a", use_case="u")]),
    ArchitectureDiagramIR(nodes=[ArchNode(id="u", label="U", kind=ArchNodeKind.ACTOR)]),
    ComponentDiagramIR(nodes=[ComponentNode(id="c", label="C")]),
])
def test_renderer_emits_structure_only_no_style(ir):
    out = R.render(ir)
    assert out.startswith("@startuml")
    assert out.rstrip().endswith("@enduml")
    assert "!theme" not in out       # gaya disuntik compiler, bukan renderer
    assert "skinparam" not in out


# --- Kompatibilitas dengan jalur render live ----------------------------------
def test_render_output_flows_through_normalize_plantuml():
    """Output renderer harus masuk ke compiler_service._normalize_plantuml (jalur
    yang sama dgn PlantUML LLM) tanpa error, dan gaya disuntik DI SANA — bukti
    'switch-ready' tanpa mengubah pipeline."""
    rendered = R.render(_login_activity())
    normalized = compiler_service._normalize_plantuml(rendered)
    assert "@startuml" in normalized
    # renderer tak menulis gaya; normalisasi yang menambahkannya
    assert "!theme" not in rendered
    assert len(normalized) > len(rendered)   # preamble gaya tersuntik


# --- Dispatch -----------------------------------------------------------------
def test_dispatch_covers_all_diagram_types():
    assert set(_DISPATCH) == set(DiagramType)


def test_render_unsupported_type_raises(monkeypatch):
    # kosongkan dispatch untuk memicu jalur error (render membaca _DISPATCH modul)
    monkeypatch.setattr("app.diagram.renderer.plantuml._DISPATCH", {})
    with pytest.raises(ValueError, match="belum mendukung"):
        R.render(_login_activity())
