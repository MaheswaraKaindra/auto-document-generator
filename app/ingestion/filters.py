import os
import re

# Dicocokkan di KEDALAMAN BERAPA PUN. Nama-nama ini praktis tidak pernah muncul
# sebagai bagian sah dari path kode produksi, dan justru harus tertangkap jauh di
# dalam: Maven/Gradle menaruh test di `src/test/java`, bukan di root.
#
# Kode test BUKAN sistem yang sedang didokumentasikan. Tanpa ini, dokumen
# menggambarkan fixture test sebagai fitur produk — dan terbaca meyakinkan, jadi
# tidak ada yang tahu harus mengeceknya. Diukur pada repo express: 1169 dari 1265
# "endpoint" ternyata berasal dari test/.
IGNORED_DIRS = {
    ".git", "node_modules", "venv", ".venv", "__pycache__", "build", "dist",
    "target", "out", ".idea", ".vscode", ".next", "coverage", "vendor",
    "test", "tests", "spec", "specs", "__tests__", "__mocks__", "e2e",
    "cypress", "testdata", "fixtures",
}

# Cuma dicocokkan di TINGKAT PALING ATAS. Kata-kata ini lazim muncul sebagai
# bagian sah dari nama package, jadi mencocokkannya di kedalaman berapa pun akan
# membuang kode produksi diam-diam.
#
# Kasus nyata: spring-petclinic menaruh kodenya di
# `src/main/java/org/springframework/samples/petclinic/` — "samples" di situ nama
# package Java. Aturan any-depth sempat membuang SEMUA 48 file Java-nya.
# Sementara `examples/auth/index.js` milik express memang kode demo dan harus
# dibuang. Bedanya cuma di kedalaman.
IGNORED_TOP_LEVEL_DIRS = {
    "example", "examples", "demo", "demos", "sample", "samples",
    "benchmark", "benchmarks", "docs",
}

# Blocklist folder saja tidak cukup: banyak bahasa menaruh test PERSIS di sebelah
# kodenya, tanpa folder terpisah. Go mewajibkannya (foo_test.go di sebelah
# foo.go), dan React/Vue lazim begitu (Button.test.tsx di sebelah Button.tsx).
_TEST_FILE_PATTERN = re.compile(
    r"""
      \.(test|spec)\.[jt]sx?$   # Button.test.tsx, api.spec.js
    | ^test_.+\.py$             # test_parser.py (konvensi pytest)
    | _test\.(py|go|rb)$        # parser_test.go (konvensi Go)
    | ^conftest\.py$            # fixture pytest
    """,
    re.VERBOSE,
)

SOURCE_EXTENSIONS = {
    ".py", ".java", ".kt", ".ts", ".tsx", ".js", ".jsx", ".go", ".rb",
    ".php", ".cs", ".rs", ".c", ".cpp", ".h", ".hpp", ".vue", ".svelte",
}

ESSENTIAL_FILENAMES = {
    "requirements.txt", "pyproject.toml", "pom.xml", "build.gradle",
    "build.gradle.kts", "package.json", "go.mod", "Dockerfile",
}

MAX_FILE_SIZE_BYTES = 500_000

# Guard anti archive-bomb. Ditaruh di sini (bukan di salah satu provider) supaya
# ZIP upload dan tarball GitHub tunduk pada batas yang sama persis — Workspace
# yang mereka hasilkan harus tidak bisa dibedakan oleh Parser.
MAX_TOTAL_FILES = 5_000
MAX_TOTAL_UNCOMPRESSED_BYTES = 200_000_000


def is_relevant_path(path: str) -> bool:
    parts = path.split("/")
    dirs = parts[:-1]
    if any(part in IGNORED_DIRS for part in dirs):
        return False
    if dirs and dirs[0] in IGNORED_TOP_LEVEL_DIRS:
        return False
    file_name = parts[-1]
    if _TEST_FILE_PATTERN.search(file_name):
        return False
    if file_name in ESSENTIAL_FILENAMES:
        return True
    _, ext = os.path.splitext(file_name)
    return ext in SOURCE_EXTENSIONS
