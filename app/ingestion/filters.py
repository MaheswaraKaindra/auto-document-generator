import os

IGNORED_DIRS = {
    ".git", "node_modules", "venv", ".venv", "__pycache__", "build", "dist",
    "target", "out", ".idea", ".vscode", ".next", "coverage", "vendor",
}

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
    if any(part in IGNORED_DIRS for part in parts[:-1]):
        return False
    file_name = parts[-1]
    if file_name in ESSENTIAL_FILENAMES:
        return True
    _, ext = os.path.splitext(file_name)
    return ext in SOURCE_EXTENSIONS
