"""Test manifest.py + narrow_to_product (Peran 1).

Manifest di sini disalin dari repo NYATA (fastapi, flask, requests, express) yang
dipakai kerangka validasi — bukan versi ideal karangan sendiri. Bentuk aslinya
memang beragam, dan justru keberagaman itulah yang harus ditangani.
"""

import pytest

from app.domain.models import Workspace, WorkspaceFile
from app.ingestion.manifest import find_product_paths, is_product_path
from app.services.ingestion_service import narrow_to_product


def _ws(files: dict[str, str]) -> Workspace:
    return Workspace(
        repo_tag="Backend",
        source_ref="test",
        files=[WorkspaceFile(file_name=p.split("/")[-1], file_path=p, content=c) for p, c in files.items()],
    )


def test_fastapi_layout_package_at_root():
    """fastapi: cuma `name = "fastapi"`, package-nya di fastapi/ (root)."""
    paths = {
        "pyproject.toml": '[project]\nname = "fastapi"\n',
        "fastapi/applications.py": "x = 1",
        "docs_src/tutorial001.py": "x = 1",
        "scripts/build.py": "x = 1",
    }
    assert find_product_paths(paths) == {"fastapi/"}


def test_flask_layout_src_and_name_case_differs():
    """flask: mendeklarasikan `name = "Flask"` (huruf besar) tapi modulnya `flask`,
    dan letaknya di src/flask/. Nama distribusi != nama folder."""
    paths = {
        "pyproject.toml": '[project]\nname = "Flask"\n\n[tool.flit.module]\nname = "flask"\n',
        "src/flask/app.py": "x = 1",
        "examples/tutorial/app.py": "x = 1",
    }
    assert find_product_paths(paths) == {"src/flask/"}


def test_requests_src_layout():
    paths = {
        "pyproject.toml": '[project]\nname = "requests"\n\n[tool.setuptools.packages.find]\nwhere = ["src"]\n',
        "src/requests/api.py": "x = 1",
        "tests/test_api.py": "x = 1",
    }
    assert find_product_paths(paths) == {"src/requests/"}


def test_poetry_name_is_read():
    paths = {
        "pyproject.toml": '[tool.poetry]\nname = "my-cool-pkg"\n',
        "my_cool_pkg/core.py": "x = 1",
    }
    # "my-cool-pkg" -> folder "my_cool_pkg" (tanda hubung jadi garis bawah)
    assert find_product_paths(paths) == {"my_cool_pkg/"}


def test_express_package_json_files_field():
    """express: `files` menyebut langsung apa yang dikirim — folder DAN file tunggal."""
    paths = {
        "package.json": '{"name":"express","files":["LICENSE","Readme.md","index.js","lib/"]}',
        "index.js": "x",
        "lib/express.js": "x",
        "test/app.js": "x",
        "examples/auth/index.js": "x",
    }
    assert find_product_paths(paths) == {"index.js", "lib/"}


def test_package_json_falls_back_to_main_directory():
    """`main` menunjuk satu file titik masuk, tapi yang menandakan produk adalah
    FOLDER-nya — kalau cuma file itu yang disimpan, lib/router.js ikut hilang."""
    paths = {
        "package.json": '{"name":"x","main":"lib/index.js"}',
        "lib/index.js": "x",
        "lib/router.js": "x",
        "test/a.js": "x",
    }
    assert find_product_paths(paths) == {"lib/"}


def test_package_json_main_at_root_gives_no_signal():
    """main = "index.js" -> foldernya seluruh repo -> tidak berguna, jangan menyaring."""
    paths = {"package.json": '{"name":"x","main":"index.js"}', "index.js": "x", "test/a.js": "x"}
    assert find_product_paths(paths) == set()


# --- Gagal-membuka: tiap kasus di bawah HARUS mengembalikan set kosong ---


@pytest.mark.parametrize(
    "paths, why",
    [
        ({"app/main.py": "x"}, "tidak ada manifest sama sekali"),
        ({"pyproject.toml": "{{{ rusak", "app/main.py": "x"}, "TOML rusak"),
        ({"package.json": "{ rusak", "app/main.py": "x"}, "JSON rusak"),
        ({"pyproject.toml": "[build-system]\nrequires = []\n", "app/main.py": "x"}, "manifest tanpa nama"),
        (
            {"pyproject.toml": '[project]\nname = "ghost"\n', "app/main.py": "x"},
            "nama dideklarasikan tapi foldernya tidak ada",
        ),
        (
            {"package.json": '{"name":"m","workspaces":["packages/*"]}', "packages/a/i.js": "x"},
            "monorepo — terlalu berisiko ditebak",
        ),
    ],
)
def test_returns_empty_when_uncertain(paths, why):
    """KOSONG = "tidak tahu" = pemanggil menyimpan semua file.

    Menyaring terlalu rakus membuang kode produksi diam-diam — kegagalan yang jauh
    lebih sulit dilihat daripada kebanyakan noise."""
    assert find_product_paths(paths) == set(), why


def test_narrow_keeps_everything_when_manifest_is_silent():
    ws = _ws({"app/main.py": "x", "test/test_main.py": "x"})
    assert len(narrow_to_product(ws).files) == 2


def test_narrow_drops_non_product_but_keeps_root_manifest():
    """Manifest root tetap disimpan walau di luar folder produk: dari situ LLM
    membaca dependency dan nama proyek."""
    ws = _ws(
        {
            "pyproject.toml": '[project]\nname = "fastapi"\n',
            "fastapi/applications.py": "x",
            "docs_src/tutorial001.py": "x",
            "scripts/build.py": "x",
        }
    )
    kept = {f.file_path for f in narrow_to_product(ws).files}
    assert kept == {"pyproject.toml", "fastapi/applications.py"}


def test_narrow_never_empties_the_workspace():
    """Kalau deteksi meleset sampai tidak menyisakan apa pun, itu tanda deteksinya
    yang salah — bukan repo-nya yang kosong. Kembalikan apa adanya."""
    ws = _ws({"pyproject.toml": '[project]\nname = "fastapi"\n'})
    # "fastapi/" tidak akan cocok dengan file mana pun di sini
    assert len(narrow_to_product(ws).files) == 1


def test_is_product_path_does_not_prefix_match_filenames():
    """"index.js" tidak boleh ikut mencocokkan "index.jsx"."""
    roots = {"index.js", "lib/"}
    assert is_product_path("index.js", roots) is True
    assert is_product_path("lib/router.js", roots) is True
    assert is_product_path("index.jsx", roots) is False
