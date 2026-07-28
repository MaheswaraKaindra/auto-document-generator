"""Rate limit per-akun untuk endpoint yang MEMAKAN BIAYA.

Kenapa ada: satu `POST /documents/generate` = satu panggilan Claude berbayar.
Tanpa batas, satu akun — atau satu token yang bocor, atau satu skrip yang lepas
kendali — bisa membengkakkan tagihan tanpa ada yang menyadarinya sampai akhir
bulan. Identitas untuk menguncinya sudah ada sejak seam auth: `Principal.id`.

**Penghitungnya bukan struktur data baru.** Kuota dihitung dari jejak yang MEMANG
sudah tersimpan: baris di tabel `jobs` (untuk generate) dan manifest di
`data/templates/` (untuk upload template). Ini keputusan yang disengaja, bukan
kemalasan — dan dua sifatnya yang penting datang gratis:

- **Benar lintas-worker.** `uvicorn --workers 3` = tiga proses. Penghitung
  in-memory memberi tiap proses kuotanya sendiri, jadi batas "10/jam" diam-diam
  jadi 30/jam — dan makin longgar tiap kali worker ditambah. CLAUDE.md sudah
  mencatat pelajaran ini dari arah sebaliknya: multi-worker JALAN di produk ini
  justru karena state-nya di SQLite, bukan di dict Python.
- **Tahan restart.** Kuota yang hilang tiap deploy/crash bukan kuota. Dan restart
  adalah hal yang paling mungkin terjadi persis ketika sistem sedang dihajar.

Konsekuensinya jujur: ini menghitung PERMINTAAN GENERATE, termasuk job yang
akhirnya gagal. Itu memang yang dimaksud "N generate per jam" — job bisa gagal
SESUDAH LLM dibayar (mis. render diagram 502), jadi menghitung yang sukses saja
akan membiarkan kegagalan berulang dibayar tanpa batas.

**Jendela SLIDING**, bukan "reset tiap jam bulat": batas per-jam yang di-reset di
menit ke-0 memperbolehkan 2N generate dalam dua menit di sekitar pergantian jam —
persis lonjakan yang batas ini ada untuk mencegah.

**Mode dev (auth mati) TIDAK dibatasi.** Saat `SUPABASE_URL` kosong semua pemanggil
adalah satu `Principal` anonim yang sama, jadi "per-akun" tak punya arti: yang
tersisa cuma batas global yang akan menghentikan sesi dev/demo di tengah jalan —
melanggar prinsip repo ini bahwa mode dev harus jalan penuh & $0. Batas ini baru
punya makna ketika akun benar-benar ada. Deploy publik TANPA auth karena itu tak
terlindungi batas ini; itu disebut sendiri di DEPLOY.md, bukan disembunyikan.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.core import config
from app.services import auth_service, compiler_service, job_store
from app.services.auth_service import Principal


@dataclass(frozen=True)
class RateLimitDecision:
    """Hasil pemeriksaan kuota. `retry_after_seconds` cuma bermakna kalau ditolak."""
    allowed: bool
    limit: int
    remaining: int
    retry_after_seconds: int


_ALLOWED_UNLIMITED = RateLimitDecision(
    allowed=True, limit=0, remaining=0, retry_after_seconds=0)


def _decide(times: list[datetime], limit: int, window_seconds: int,
            now: datetime) -> RateLimitDecision:
    """Sliding window atas `times` (waktu permintaan terakhir, terbaru dulu).

    Prakondisi: `times` berisi PALING BANYAK `limit` entri terbaru — itu yang
    membuat keputusan ini bisa diambil tanpa menyapu seluruh riwayat. Kalau `limit`
    entri terbaru semuanya masih di dalam jendela, kuotanya habis; yang lebih tua
    tak bisa mengubah kesimpulan itu.
    """
    cutoff = now - timedelta(seconds=window_seconds)
    # Timestamp naive (tak seharusnya terjadi — semua ditulis UTC ber-offset) tak
    # bisa dibandingkan dengan yang aware. Anggap UTC daripada meledak: batas
    # kuota tak boleh menjatuhkan endpoint yang seharusnya dilindunginya.
    in_window = sorted(
        (t if t.tzinfo else t.replace(tzinfo=timezone.utc) for t in times),
        reverse=True,
    )
    in_window = [t for t in in_window if t > cutoff]

    if len(in_window) < limit:
        return RateLimitDecision(allowed=True, limit=limit,
                                 remaining=limit - len(in_window),
                                 retry_after_seconds=0)

    # Kuota longgar lagi begitu permintaan TERTUA di dalam jendela keluar darinya.
    # Dibulatkan ke ATAS: Retry-After yang kependekan mengundang klien mencoba
    # lagi satu detik terlalu awal, kena 429 kedua, lalu menyalahkan servernya.
    oldest_blocking = in_window[limit - 1]
    retry_after = math.ceil((oldest_blocking + timedelta(seconds=window_seconds) - now)
                            .total_seconds())
    return RateLimitDecision(allowed=False, limit=limit, remaining=0,
                             retry_after_seconds=max(1, retry_after))


def _enabled(limit: int, caller: Principal) -> bool:
    """Batas berlaku? Tidak kalau dimatikan (limit 0) atau auth non-aktif —
    lihat catatan mode dev di docstring modul."""
    return limit > 0 and auth_service.auth_enabled() and not caller.is_anonymous


def check_generate(caller: Principal,
                   now: datetime | None = None) -> RateLimitDecision:
    """Boleh membuat job generate baru? Dihitung dari tabel `jobs` milik pemanggil."""
    limit = config.RATE_LIMIT_GENERATE_PER_WINDOW
    if not _enabled(limit, caller):
        return _ALLOWED_UNLIMITED
    return _decide(job_store.recent_job_times(caller.id, limit), limit,
                   config.RATE_LIMIT_WINDOW_SECONDS, now or datetime.now(timezone.utc))


def check_template_upload(caller: Principal,
                          now: datetime | None = None) -> RateLimitDecision:
    """Boleh meng-upload+mengompilasi template baru? Dihitung dari manifest tersimpan."""
    limit = config.RATE_LIMIT_TEMPLATE_UPLOAD_PER_WINDOW
    if not _enabled(limit, caller):
        return _ALLOWED_UNLIMITED
    return _decide(compiler_service.recent_template_upload_times(caller.id, limit),
                   limit, config.RATE_LIMIT_WINDOW_SECONDS,
                   now or datetime.now(timezone.utc))
