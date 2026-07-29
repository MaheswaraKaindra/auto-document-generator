"""Lapisan DB bersama: SQLite (default) atau Postgres (#13).

DUA MODE, dipilih dari env — pola yang sama dengan `auth_service` & `job_queue`:

- **`DATABASE_URL` kosong → SQLite** di `DATABASE_PATH`. Nol layanan tambahan;
  ini yang membuat repo tetap bisa dikerjakan, dites, dan didemokan $0.
- **`DATABASE_URL` terisi → Postgres.** State dibagi lintas MESIN, bukan cuma
  lintas proses — syarat yang tak bisa dipenuhi file SQLite begitu web dan worker
  hidup di container/host berbeda.

Kenapa perlu, dan batas persisnya: multi-worker di SATU mesin sudah lama jalan
dengan SQLite, dan CLAUDE.md mencatat alasannya — state-nya file di disk yang
dibaca semua proses, bukan dict di memori. Yang patah adalah multi-MESIN: dua
container tak berbagi file itu. Jadi Postgres di sini menutup gap yang sempit dan
nyata, bukan menggantikan sesuatu yang rusak.

**Bukan ORM.** `job_store` sengaja ditulis rata sejak awal supaya pemindahan ini
cukup mengganti isi lapisan, bukan menulis ulang pemanggilnya — dan itu memang
yang terjadi: tak satu pun pemanggil `job_store`/`billing_service` berubah.

Yang diterjemahkan modul ini, semuanya karena dialek (bukan karena logika beda):
- placeholder `?` → `%s`;
- `kolom IS ?` (idiom SQLite untuk mencocokkan NULL) → `IS NOT DISTINCT FROM %s`;
- `PRAGMA table_info` → `information_schema.columns`, lewat `columns()`.
Sisa SQL-nya sengaja ditulis dalam irisan yang dipahami KEDUA mesin (`CREATE TABLE
IF NOT EXISTS`, `ON CONFLICT ... DO UPDATE`, `COALESCE`), supaya tak ada dua versi
query yang bisa menyimpang diam-diam.
"""

from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

from app.core import config

# ` IS ?` hanya sah sebagai pembanding NULL di SQLite. Diterjemahkan, bukan
# dilarang, supaya query-nya tetap satu versi untuk dua mesin.
_IS_NULL_COMPARE = re.compile(r"\bIS\s+\?", re.IGNORECASE)


def postgres_enabled() -> bool:
    """True kalau state disimpan di Postgres. Dibaca saat dipanggil (tak di-cache)
    supaya test bisa menyetel `config.DATABASE_URL` per-kasus."""
    return bool(config.DATABASE_URL)


def _translate(sql: str) -> str:
    """SQL gaya SQLite → dialek Postgres."""
    sql = _IS_NULL_COMPARE.sub("IS NOT DISTINCT FROM %s", sql)
    return sql.replace("?", "%s")


class _PgConnection:
    """Pembungkus tipis supaya psycopg terlihat seperti sqlite3 di titik pakai.

    Dibuat sekecil mungkin dengan sengaja: makin banyak yang ditiru di sini, makin
    besar peluang dua mesin berperilaku beda pada hal yang tak pernah diuji.
    """

    def __init__(self, raw):
        self._raw = raw

    def execute(self, sql: str, params: Sequence[Any] = ()):
        cur = self._raw.cursor()
        cur.execute(_translate(sql), tuple(params))
        return cur

    def executescript(self, script: str) -> None:
        with self._raw.cursor() as cur:
            cur.execute(script)

    def columns(self, table: str) -> set:
        with self._raw.cursor() as cur:
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = %s", (table,))
            return {row["column_name"] for row in cur.fetchall()}


class _SqliteConnection:
    """Antarmuka yang sama untuk SQLite — supaya pemanggil tak pernah bercabang."""

    def __init__(self, raw: sqlite3.Connection):
        self._raw = raw

    def execute(self, sql: str, params: Sequence[Any] = ()):
        return self._raw.execute(sql, tuple(params))

    def executescript(self, script: str) -> None:
        self._raw.executescript(script)

    def columns(self, table: str) -> set:
        return {row["name"] for row in self._raw.execute(f"PRAGMA table_info({table})")}


@contextmanager
def connect(sqlite_path: Optional[Path] = None):
    """Koneksi ke store yang sedang aktif. `sqlite_path` diabaikan di mode Postgres.

    Parameternya tetap ada supaya pemanggil (`job_store`, `billing_service`) bisa
    terus menunjuk DB_PATH masing-masing — itu yang membuat test yang mengalihkan
    DB ke `tmp_path` tetap bekerja tanpa satu baris pun berubah.
    """
    if postgres_enabled():
        import psycopg                               # noqa: PLC0415
        from psycopg.rows import dict_row             # noqa: PLC0415

        raw = psycopg.connect(config.DATABASE_URL, row_factory=dict_row)
        try:
            yield _PgConnection(raw)
            raw.commit()
        finally:
            raw.close()
        return

    path = Path(sqlite_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = sqlite3.connect(path)
    raw.row_factory = sqlite3.Row
    try:
        yield _SqliteConnection(raw)
        raw.commit()
    finally:
        raw.close()


def rows_as_dicts(rows: Iterable) -> list[dict]:
    """Baris → dict, seragam untuk dua mesin (sqlite3.Row perlu dikonversi,
    psycopg dict_row sudah dict)."""
    return [dict(row) for row in rows]
