"""Cek kesiapan dependency untuk probe `/ready` (#14).

`/health` menjawab "proses ini hidup?"; `/ready` menjawab pertanyaan yang
berbeda dan lebih berguna untuk orchestrator: "proses ini bisa MENGERJAKAN
pekerjaannya?" — yaitu apakah keempat dependency yang dipakai pipeline benar-benar
ada. Bedanya nyata: container bisa hidup (health OK) sambil kehilangan Java, dan
tiap generate akan gagal di tahap diagram — persis yang `/ready` cegah dengan
menyuruh orchestrator TIDAK mengarahkan trafik ke instance itu.

Dependency yang dicek dipilih dari yang PIPELINE-nya benar-benar butuh, bukan
daftar umum: DB (status job), pandoc (export docx), Java + plantuml.jar (render
diagram). Sama persis dengan yang, kalau hilang, menggagalkan `_generate_document`.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any

from app.core import config
from app.services import db, job_store

logger = logging.getLogger(__name__)


def _check_db() -> dict[str, Any]:
    try:
        with db.connect(job_store.DB_PATH) as conn:
            conn.execute("SELECT 1").fetchone()
        engine = "postgres" if db.postgres_enabled() else "sqlite"
        return {"name": "database", "ok": True, "detail": engine}
    except Exception as e:
        return {"name": "database", "ok": False, "detail": str(e)}


def _check_pandoc() -> dict[str, Any]:
    try:
        import pypandoc                                # noqa: PLC0415

        version = pypandoc.get_pandoc_version()
        return {"name": "pandoc", "ok": True, "detail": f"v{version}"}
    except Exception as e:
        return {"name": "pandoc", "ok": False, "detail": str(e)}


def _check_java() -> dict[str, Any]:
    try:
        result = subprocess.run(
            ["java", "-version"], capture_output=True, timeout=15
        )
        if result.returncode == 0:
            # `java -version` menulis ke stderr; baris pertama memuat versinya.
            first = (result.stderr or b"").decode("utf-8", "replace").splitlines()
            return {"name": "java", "ok": True, "detail": first[0] if first else "ok"}
        return {"name": "java", "ok": False, "detail": f"exit {result.returncode}"}
    except FileNotFoundError:
        return {"name": "java", "ok": False, "detail": "java tak ada di PATH"}
    except Exception as e:
        return {"name": "java", "ok": False, "detail": str(e)}


def _check_plantuml_jar() -> dict[str, Any]:
    jar = Path(config.PLANTUML_JAR)
    if jar.is_file():
        return {"name": "plantuml_jar", "ok": True, "detail": str(jar)}
    return {"name": "plantuml_jar", "ok": False, "detail": f"tak ditemukan di {jar}"}


_CHECKS = (_check_db, _check_pandoc, _check_java, _check_plantuml_jar)


def readiness() -> dict[str, Any]:
    """Jalankan semua cek. Kembalikan {ready: bool, checks: [...]}.

    `ready` True hanya kalau SEMUA dependency ada — satu saja hilang membuat
    pipeline gagal, jadi tak ada gunanya melaporkan "setengah siap".
    """
    checks = [check() for check in _CHECKS]
    ready = all(c["ok"] for c in checks)
    if not ready:
        missing = [c["name"] for c in checks if not c["ok"]]
        logger.warning("Readiness gagal — dependency tak lengkap: %s", ", ".join(missing))
    return {"ready": ready, "checks": checks}
