"""Test deteksi endpoint di parser_service.py (Peran 1).

Cakupannya SENGAJA sempit: cuma deteksi endpoint Python, bukan seluruh parser
(parser_service.py memang belum punya test menyeluruh — lihat Keterbatasan).
Bagian ini yang dikunci karena di sinilah bug-nya: Flask menghasilkan nol
endpoint selama ini, dan untuk aplikasi bisnis endpoint ITU produknya.
"""

from app.domain.models import Workspace, WorkspaceFile
from app.services.parser_service import build_parsed_repo_context


def _endpoints(source: str, file_path: str = "routes/x.py") -> list[dict]:
    workspace = Workspace(repo_tag="Backend", source_ref="test")
    workspace.files.append(
        WorkspaceFile(
            file_name=file_path.split("/")[-1], file_path=file_path, content=source
        )
    )
    context = build_parsed_repo_context(project_name="t", workspaces=[workspace])
    return [
        endpoint
        for repo in context["repositories"]
        for f in repo["files"]
        for endpoint in f["api_endpoints"]
    ]


def test_flask_route_without_methods_defaults_to_get():
    """@bp.route("/x") tanpa methods= berarti GET saja — itu default Flask,
    dan bentuk paling umum. Ini yang dulu menghasilkan NOL endpoint karena
    "route" bukan anggota HTTP_METHODS."""
    endpoints = _endpoints(
        'from flask import Blueprint\n'
        'bp = Blueprint("auth", __name__)\n'
        '@bp.route("/logout")\n'
        'def logout():\n'
        '    return "ok"\n'
    )

    assert endpoints == [{"method": "GET", "path": "/logout", "payload": None}]


def test_one_route_decorator_can_produce_several_endpoints():
    """methods=["GET", "POST"] itu DUA endpoint. Versi lama mengembalikan satu
    endpoint per fungsi, yang cukup selama cuma FastAPI yang dikenali."""
    endpoints = _endpoints(
        '@auth_bp.route("/login", methods=["GET", "POST"])\n'
        'def login():\n'
        '    return "ok"\n'
    )

    assert {(e["method"], e["path"]) for e in endpoints} == {
        ("GET", "/login"),
        ("POST", "/login"),
    }


def test_flask_path_parameters_are_kept_verbatim():
    """Converter Flask (<int:item_id>) harus utuh — itu bagian dari kontrak
    endpoint, dan pembaca dokumen perlu melihatnya."""
    endpoints = _endpoints(
        '@customer_bp.route("/cart/update/<int:item_id>", methods=["POST"])\n'
        'def update(item_id):\n'
        '    return "ok"\n'
    )

    assert endpoints[0]["path"] == "/cart/update/<int:item_id>"
    assert endpoints[0]["method"] == "POST"


def test_head_and_options_are_dropped():
    """Flask menambahkan HEAD/OPTIONS sendiri secara otomatis; keduanya protokol,
    bukan fitur yang perlu didokumentasikan."""
    endpoints = _endpoints(
        '@bp.route("/x", methods=["GET", "HEAD", "OPTIONS"])\n'
        'def x():\n'
        '    return "ok"\n'
    )

    assert [e["method"] for e in endpoints] == ["GET"]


def test_stacked_route_decorators_all_counted():
    """Menumpuk route pada satu view itu lazim di Flask. Versi lama berhenti di
    decorator pertama yang cocok."""
    endpoints = _endpoints(
        '@bp.route("/")\n'
        '@bp.route("/home")\n'
        'def index():\n'
        '    return "ok"\n'
    )

    assert {e["path"] for e in endpoints} == {"/", "/home"}


def test_fastapi_decorator_still_detected():
    """Penjaga regresi: menambah Flask tidak boleh merusak FastAPI, satu-satunya
    bentuk yang selama ini jalan."""
    endpoints = _endpoints(
        '@app.get("/items")\n'
        'def read_items():\n'
        '    return []\n'
    )

    assert endpoints == [{"method": "GET", "path": "/items", "payload": None}]


def test_unrelated_decorator_is_not_an_endpoint():
    """`route` cuma dikenali dalam bentuk <apa_saja>.route("path"). Decorator lain
    tidak boleh diseret jadi endpoint."""
    endpoints = _endpoints(
        '@lru_cache(maxsize=8)\n'
        'def helper():\n'
        '    return 1\n'
        '@app.errorhandler(404)\n'
        'def not_found(e):\n'
        '    return "nope"\n'
    )

    assert endpoints == []
