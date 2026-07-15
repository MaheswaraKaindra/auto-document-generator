"""Deteksi bagian repo yang benar-benar DIKIRIM sebagai produk, dari manifest-nya.

Kenapa modul ini ada: menyaring "yang bukan produk" lewat blocklist nama folder
adalah permainan yang tidak bisa dimenangkan. `test/` tertangkap, lalu
`examples/` lolos, lalu `docs_src/` lolos, lalu `website/`, `playground/`,
`cookbook/`... tiap repo mengarang konvensinya sendiri, jadi daftar nama tidak
akan pernah lengkap.

Diukur pada fastapi: 456 dari 530 file (86%) berasal dari `docs_src/`, dan
SELURUH 432 endpoint yang terdeteksi berasal dari sana — package `fastapi/` yang
asli menyumbang nol. Dokumen yang lahir dari input itu menggambarkan potongan
tutorial sebagai fitur produk, dan terbaca meyakinkan.

Modul ini membalik pertanyaannya: berhenti menebak mana yang BUKAN produk, dan
tanya repo-nya sendiri mana yang produk. `pyproject.toml` dan `package.json`
MENDEKLARASIKAN itu — jadi ini fakta dari repo, bukan tebakan kita.

PRINSIP UTAMA — GAGAL-MEMBUKA, BUKAN GAGAL-MENUTUP.
Kalau manifest tidak ada, tidak terbaca, atau hasil deteksinya tidak cocok dengan
satu file pun, kembalikan KOSONG supaya pemanggil menyimpan semua file. Filter
yang terlalu rakus membuang kode produksi diam-diam — kegagalan yang jauh lebih
sulit dilihat daripada kebanyakan noise. Ini bukan kekhawatiran teoretis: aturan
any-depth untuk kata "samples" pernah membuang SELURUH 48 file Java
spring-petclinic, cuma karena nama package-nya `org.springframework.samples`.
"""

import json
import tomllib

_PYPROJECT = "pyproject.toml"
_PACKAGE_JSON = "package.json"


def _normalize_package_name(name: str) -> str:
    """"Flask" -> "flask", "my-pkg" -> "my_pkg".

    Nama distribusi di manifest tidak selalu sama dengan nama folder modulnya.
    Contoh nyata: flask mendeklarasikan `name = "Flask"` tapi modulnya `flask`.
    """
    return name.strip().lower().replace("-", "_")


def _existing_dirs(candidates: set[str], all_paths: set[str]) -> set[str]:
    """Sisakan hanya folder yang BENAR-BENAR ada di repo.

    Ini jaring pengaman utamanya: nama dari manifest cuma dipercaya kalau ada
    file nyata di bawahnya, jadi tebakan yang meleset otomatis gugur di sini.
    """
    found = set()
    for name in candidates:
        # Dua layout yang lazim: <name>/ di root (fastapi), atau src/<name>/
        # (flask, requests — "src layout").
        for prefix in ("", "src/"):
            directory = f"{prefix}{name}/"
            if any(p.startswith(directory) for p in all_paths):
                found.add(directory)
    return found


def _python_product_paths(content: str, all_paths: set[str]) -> set[str]:
    """Baca pyproject.toml. Mendukung PEP 621, poetry, dan flit."""
    try:
        data = tomllib.loads(content)
    except (tomllib.TOMLDecodeError, ValueError):
        return set()  # manifest rusak -> jangan menyaring apa pun

    tool = data.get("tool", {})
    names = {
        data.get("project", {}).get("name"),
        tool.get("poetry", {}).get("name"),
        # flit menyebut nama MODUL-nya terpisah dari nama distribusi — ini justru
        # yang paling akurat kalau ada.
        tool.get("flit", {}).get("module", {}).get("name"),
    }
    candidates = {_normalize_package_name(n) for n in names if isinstance(n, str) and n.strip()}
    return _existing_dirs(candidates, all_paths)


def _js_product_paths(content: str, all_paths: set[str]) -> set[str]:
    """Baca package.json.

    Field `files` adalah sinyal terbaik yang ada di seluruh modul ini: npm
    memakainya untuk menentukan apa yang benar-benar masuk paket, jadi isinya
    literal jawaban atas pertanyaan kita. express mendeklarasikan
    `["LICENSE", "Readme.md", "index.js", "lib/"]`.
    """
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return set()

    if not isinstance(data, dict) or data.get("workspaces"):
        # Monorepo: satu package.json mengatur banyak paket. Terlalu berisiko
        # ditebak di sini — biarkan semua file lewat.
        return set()

    entries = data.get("files")
    if not isinstance(entries, list) or not entries:
        # Tanpa `files`, pakai `main` sebagai petunjuk kasar. `main` menunjuk satu
        # FILE titik masuk, jadi yang menandakan produk adalah FOLDER-nya:
        # main = "lib/index.js" -> produknya "lib/", bukan cuma file itu (kalau
        # cuma file itu yang disimpan, lib/router.js dan tetangganya ikut hilang).
        main = data.get("main")
        if isinstance(main, str) and "/" in main.strip().lstrip("./"):
            entries = [main.strip().lstrip("./").rsplit("/", 1)[0]]
        else:
            # main di root ("index.js") -> folder-nya seluruh repo -> tidak ada
            # sinyal yang berguna, jangan menyaring.
            entries = []

    roots: set[str] = set()
    for entry in entries:
        if not isinstance(entry, str):
            continue
        cleaned = entry.strip().lstrip("./").rstrip("/")
        if not cleaned or cleaned.startswith("!"):  # "!x" = pola pengecualian npm
            continue
        directory = f"{cleaned}/"
        if any(p.startswith(directory) for p in all_paths):
            roots.add(directory)          # ternyata folder
        elif cleaned in all_paths:
            roots.add(cleaned)            # ternyata file tunggal (mis. index.js)
    return roots


def find_product_paths(path_to_content: dict[str, str]) -> set[str]:
    """Kembalikan prefix path yang dideklarasikan repo sebagai produknya.

    Entry berakhiran "/" adalah folder; sisanya file tunggal.
    KOSONG berarti "tidak tahu" — pemanggil WAJIB menyimpan semua file.

    Hanya manifest di ROOT yang dibaca. Manifest yang terkubur di dalam
    (mis. `docs_src/tutorial/package.json`) menjelaskan contoh, bukan repo-nya.
    """
    all_paths = set(path_to_content)
    roots: set[str] = set()

    if _PYPROJECT in path_to_content:
        roots |= _python_product_paths(path_to_content[_PYPROJECT], all_paths)
    if _PACKAGE_JSON in path_to_content:
        roots |= _js_product_paths(path_to_content[_PACKAGE_JSON], all_paths)

    return roots


def is_product_path(path: str, roots: set[str]) -> bool:
    """Apakah `path` berada di dalam salah satu root produk?"""
    for root in roots:
        if root.endswith("/"):
            if path.startswith(root):
                return True
        elif path == root:
            return True
    return False
