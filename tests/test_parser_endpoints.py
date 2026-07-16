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


# --- url_prefix Blueprint -----------------------------------------------------
#
# Sebelum ini path yang dicatat adalah path yang DITULIS di decorator, jadi
# routes/admin.py dan routes/customer.py esteler sama-sama melaporkan `GET /`
# dan `GET /menu` — dua fitur berbeda tampak berbagi endpoint yang sama.
#
# Bentuk di bawah diambil dari esteler-app yang SUNGGUHAN. CLAUDE.md sempat
# mendiagnosis ini sebagai masalah lintas-file (`register_blueprint(bp,
# url_prefix=...)` di file lain); kode esteler ternyata menaruh url_prefix di
# konstruktor Blueprint, di file yang sama dengan route-nya.

def test_blueprint_url_prefix_is_prepended():
    """`Blueprint("admin", __name__, url_prefix="/admin")` -> route ikut berprefix.
    Diambil apa adanya dari routes/admin.py esteler."""
    endpoints = _endpoints(
        'from flask import Blueprint\n'
        'admin_bp = Blueprint("admin", __name__, url_prefix="/admin")\n'
        '@admin_bp.route("/dashboard")\n'
        'def dashboard():\n'
        '    return "ok"\n'
    )

    assert endpoints == [{"method": "GET", "path": "/admin/dashboard", "payload": None}]


def test_blueprint_prefix_keeps_root_slash():
    """`url_prefix="/admin"` + `route("/")` = `/admin/` — Flask mempertahankan
    slash itu, dan inilah kasus yang dulu bentrok dengan `GET /` milik customer."""
    endpoints = _endpoints(
        'admin_bp = Blueprint("admin", __name__, url_prefix="/admin")\n'
        '@admin_bp.route("/")\n'
        'def index():\n'
        '    return "ok"\n'
    )

    assert endpoints[0]["path"] == "/admin/"


def test_blueprint_without_prefix_is_unchanged():
    """`Blueprint("auth", __name__)` tanpa url_prefix -> path apa adanya.
    routes/auth.py dan routes/customer.py esteler memang begini — memaksa prefix
    di sini akan MERUSAK path yang selama ini benar."""
    endpoints = _endpoints(
        'auth_bp = Blueprint("auth", __name__)\n'
        '@auth_bp.route("/login", methods=["GET", "POST"])\n'
        'def login():\n'
        '    return "ok"\n'
    )

    assert {(e["method"], e["path"]) for e in endpoints} == {
        ("GET", "/login"),
        ("POST", "/login"),
    }


def test_two_blueprints_in_one_file_dont_bleed():
    """Prefix dilacak per variabel, bukan per file."""
    endpoints = _endpoints(
        'api_bp = Blueprint("api", __name__, url_prefix="/api")\n'
        'web_bp = Blueprint("web", __name__)\n'
        '@api_bp.route("/users")\n'
        'def users():\n'
        '    return "ok"\n'
        '@web_bp.route("/users")\n'
        'def page():\n'
        '    return "ok"\n'
    )

    assert {e["path"] for e in endpoints} == {"/api/users", "/users"}


def test_blueprint_defined_after_its_routes():
    """Pengumpulan prefix adalah PRA-PASS, jadi urutan penulisan tidak menentukan.
    Kalau disandarkan pada urutan file, kasus ini diam-diam kehilangan prefix."""
    endpoints = _endpoints(
        '@late_bp.route("/x")\n'
        'def x():\n'
        '    return "ok"\n'
        'late_bp = Blueprint("late", __name__, url_prefix="/late")\n'
    )

    assert endpoints[0]["path"] == "/late/x"


def test_blueprint_created_inside_factory_function():
    """Pola factory (`create_app`) menaruh Blueprint di dalam fungsi — pra-pass
    menyisir seluruh pohon, bukan cuma level modul."""
    endpoints = _endpoints(
        'def create_app():\n'
        '    inner_bp = Blueprint("inner", __name__, url_prefix="/inner")\n'
        '    return inner_bp\n'
        '@inner_bp.route("/ping")\n'
        'def ping():\n'
        '    return "ok"\n'
    )

    assert endpoints[0]["path"] == "/inner/ping"


def test_qualified_blueprint_call_recognised():
    """`flask.Blueprint(...)` — yang diperiksa nama atribut terakhirnya."""
    endpoints = _endpoints(
        'import flask\n'
        'bp = flask.Blueprint("x", __name__, url_prefix="/y")\n'
        '@bp.route("/z")\n'
        'def z():\n'
        '    return "ok"\n'
    )

    assert endpoints[0]["path"] == "/y/z"


def test_unknown_route_object_gets_no_prefix():
    """Penjaga gagal-membuka: `app` bukan Blueprint yang kita kenal -> path apa
    adanya. Menebak prefix menaruh endpoint di URL yang tidak ada — lebih buruk
    daripada path yang kurang lengkap."""
    endpoints = _endpoints(
        'app = Flask(__name__)\n'
        '@app.route("/health")\n'
        'def health():\n'
        '    return "ok"\n'
    )

    assert endpoints[0]["path"] == "/health"


def test_fastapi_router_unaffected_by_blueprint_logic():
    """Penjaga regresi: `router` bukan Blueprint, jadi tidak boleh dapat prefix."""
    endpoints = _endpoints(
        'router = APIRouter()\n'
        '@router.get("/items")\n'
        'def read_items():\n'
        '    return []\n'
    )

    assert endpoints == [{"method": "GET", "path": "/items", "payload": None}]


def test_blueprint_prefix_with_trailing_slash_no_double_slash():
    endpoints = _endpoints(
        'bp = Blueprint("b", __name__, url_prefix="/admin/")\n'
        '@bp.route("/menu")\n'
        'def menu():\n'
        '    return "ok"\n'
    )

    assert endpoints[0]["path"] == "/admin/menu"


def test_blueprint_prefix_applies_to_fastapi_style_method_decorator():
    """`@bp.get("/x")` juga dipakai (Flask 2.0+ punya shortcut method), jadi
    prefix harus ikut di jalur HTTP_METHODS, bukan cuma di jalur `route`."""
    endpoints = _endpoints(
        'bp = Blueprint("b", __name__, url_prefix="/api")\n'
        '@bp.get("/ping")\n'
        'def ping():\n'
        '    return "ok"\n'
    )

    assert endpoints == [{"method": "GET", "path": "/api/ping", "payload": None}]
