"""Deteksi endpoint Next.js App Router (Peran 1).

Ditambahkan 2026-07-18 sesudah tes end-to-end taxonomy menunjukkan 0 endpoint
dari 130 file: App Router tak memakai pemanggilan router (`app.get(...)`),
melainkan NAMED EXPORT `GET/POST/...` di file `route.ts`, dengan URL dari
STRUKTUR FOLDER. Cakupan sempit — sengaja, sama seperti test parser lain.
"""

from app.services.parser_service import _app_router_path, parse_file


def _endpoints(source: str, file_path: str):
    meta = parse_file(file_path.split("/")[-1], file_path, source)
    return meta, [(e.method, e.path) for e in meta.api_endpoints]


# --- Path derivation dari struktur folder -------------------------------------

def test_path_static():
    assert _app_router_path("app/api/posts/route.ts") == "/api/posts"


def test_path_dynamic_segment():
    assert _app_router_path("app/api/posts/[postId]/route.ts") == "/api/posts/:postId"


def test_path_catch_all():
    assert _app_router_path("app/api/blog/[...slug]/route.ts") == "/api/blog/:slug"


def test_path_optional_catch_all():
    assert _app_router_path("app/api/[[...all]]/route.ts") == "/api/:all"


def test_path_route_group_is_stripped():
    """Route group `(marketing)` itu pengelompokan folder — TIDAK muncul di URL."""
    assert _app_router_path("app/(marketing)/api/x/route.ts") == "/api/x"


def test_path_parallel_slot_is_stripped():
    assert _app_router_path("app/api/@modal/x/route.ts") == "/api/x"


def test_path_src_app_prefix():
    assert _app_router_path("src/app/api/blog/[...slug]/route.ts") == "/api/blog/:slug"


def test_path_none_when_not_under_app():
    assert _app_router_path("components/Button.tsx") is None
    assert _app_router_path("pages/api/foo.ts") is None


# --- Deteksi method dari named export -----------------------------------------

def test_named_exports_become_endpoints():
    meta, endpoints = _endpoints(
        'import { db } from "@/lib/db"\n'
        "export async function GET(req) { return new Response() }\n"
        "export async function POST(req) { return new Response() }\n",
        "app/api/posts/route.ts",
    )
    assert ("GET", "/api/posts") in endpoints
    assert ("POST", "/api/posts") in endpoints
    assert meta.type == "controller"  # punya endpoint -> controller


def test_dynamic_route_methods_carry_param_path():
    _, endpoints = _endpoints(
        "export async function DELETE(req, ctx) { return new Response() }\n"
        "export async function PATCH(req, ctx) { return new Response() }\n",
        "app/api/posts/[postId]/route.ts",
    )
    assert set(endpoints) == {("DELETE", "/api/posts/:postId"), ("PATCH", "/api/posts/:postId")}


def test_const_arrow_export_form():
    """`export const GET = async () => {}` — bentuk arrow, juga handler sah."""
    _, endpoints = _endpoints(
        "export const GET = async (req) => new Response()\n",
        "app/api/health/route.ts",
    )
    assert endpoints == [("GET", "/api/health")]


def test_unexported_function_is_not_an_endpoint():
    """Fungsi helper tak-terekspor bernama sama TIDAK boleh jadi endpoint."""
    _, endpoints = _endpoints(
        "async function GET() {}\n"  # tanpa export
        "export async function POST(req) { return new Response() }\n",
        "app/api/x/route.ts",
    )
    assert endpoints == [("POST", "/api/x")]


def test_route_segment_config_is_not_a_method():
    """`export const dynamic = 'force-dynamic'` itu konfigurasi route, bukan method."""
    _, endpoints = _endpoints(
        "export const dynamic = 'force-dynamic'\n"
        "export const runtime = 'edge'\n"
        "export async function GET(req) { return new Response() }\n",
        "app/api/x/route.ts",
    )
    assert endpoints == [("GET", "/api/x")]


def test_only_route_file_triggers_detection():
    """Named export GET di file BUKAN `route.ts` tidak dianggap endpoint —
    App Router hanya menjadikan `route.ts` sebagai route (page.tsx, dsb. tidak)."""
    _, endpoints = _endpoints(
        "export async function GET(req) { return new Response() }\n",
        "app/api/x/page.tsx",
    )
    assert endpoints == []


def test_underscore_route_is_ignored():
    """`_route.ts` ber-underscore = route yang dinonaktifkan; Next.js mengabaikannya."""
    _, endpoints = _endpoints(
        "export async function GET(req) { return new Response() }\n",
        "app/api/x/_route.ts",
    )
    assert endpoints == []


def test_express_style_still_works_alongside():
    """Regresi: deteksi Express (`router.get('/x', ...)`) tetap jalan di file biasa."""
    _, endpoints = _endpoints(
        "const router = express.Router()\n"
        "router.get('/health', (req, res) => res.send('ok'))\n",
        "src/routes/health.ts",
    )
    assert ("GET", "/health") in endpoints
