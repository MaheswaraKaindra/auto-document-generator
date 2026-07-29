"""CORS: daftar origin datang dari env, bukan dari `*` yang hardcode (#15).

Batas yang harus jujur diakui di muka, sama seperti test CORS yang sudah ada di
`test_routes_document.py`: **TestClient tidak menegakkan CORS sama sekali** — dia
bukan browser, dan dia akan menjawab request dari origin mana pun. Jadi yang
diuji di sini KONFIGURASINYA (nilai apa yang sampai ke middleware), bukan
perilaku penolakannya. Hanya browser sungguhan yang membuktikan yang terakhir.

Itu bukan alasan melewatkan test ini: yang paling mungkin salah bukan
CORSMiddleware-nya (kode pihak ketiga yang matang), melainkan penguraian env —
dan itu justru yang diperiksa di sini.
"""

import importlib

import pytest

import app.main
from app.core import config


@pytest.fixture(autouse=True)
def _pulihkan_config_dan_app():
    """Kembalikan `config` & `app.main` ke keadaan env asli sesudah tiap test.

    Test di file ini memuat ulang kedua modul itu, dan keduanya menyimpan nilai
    env sebagai konstanta saat IMPORT. Tanpa pemulihan, test SETELAHNYA — di
    file mana pun — akan mewarisi origin karangan dari test terakhir yang jalan.

    Pemulihannya ditaruh di fixture, bukan di sebuah test penutup: test penutup
    tak ikut jalan saat seseorang menyaring dengan `-k`, dan pencemarannya baru
    terlihat sebagai kegagalan di file lain yang sama sekali tak bersalah.
    """
    yield
    importlib.reload(config)
    importlib.reload(app.main)


def _reload_config(monkeypatch, value):
    """Muat ulang config dengan ALLOWED_ORIGINS tertentu."""
    if value is None:
        monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    else:
        monkeypatch.setenv("ALLOWED_ORIGINS", value)
    return importlib.reload(config)


def test_default_hanya_dev_server_bukan_bintang(monkeypatch):
    """Tanpa env, defaultnya dev server Vite — BUKAN `*`.

    Ini inti #15: sebelumnya `*` adalah nilai bawaan, jadi setiap deploy
    mewarisinya tanpa ada yang pernah memutuskannya."""
    reloaded = _reload_config(monkeypatch, None)

    assert "*" not in reloaded.ALLOWED_ORIGINS
    assert "http://localhost:5173" in reloaded.ALLOWED_ORIGINS
    assert "http://127.0.0.1:5173" in reloaded.ALLOWED_ORIGINS


def test_daftar_dipisah_koma_dan_spasi_diabaikan(monkeypatch):
    reloaded = _reload_config(
        monkeypatch, "https://a.contoh.com, https://b.contoh.com")

    assert reloaded.ALLOWED_ORIGINS == [
        "https://a.contoh.com", "https://b.contoh.com"]


def test_garis_miring_di_ujung_dipangkas(monkeypatch):
    """Browser mengirim Origin TANPA garis miring ujung, dan CORSMiddleware
    mencocokkan string persis — jadi `https://app.contoh.com/` di env tak akan
    pernah cocok dengan apa pun. Gagalnya senyap: tak ada error di server, cuma
    request yang ditolak di browser pengguna. Dipangkas supaya salah-tempel URL
    tidak berubah jadi jam-jam menebak."""
    reloaded = _reload_config(monkeypatch, "https://app.contoh.com/")

    assert reloaded.ALLOWED_ORIGINS == ["https://app.contoh.com"]


def test_bintang_masih_bisa_tapi_harus_ditulis(monkeypatch):
    """`*` tidak dilarang — ada instance internal yang memang menginginkannya.
    Yang berubah: ia kini pilihan eksplisit, bukan warisan default."""
    reloaded = _reload_config(monkeypatch, "*")

    assert reloaded.ALLOWED_ORIGINS == ["*"]


def test_middleware_memakai_nilai_config_bukan_hardcode(monkeypatch):
    """Jaring pengaman terhadap kelas bug yang paling mungkin: config diurai
    dengan benar, tapi `main.py` tetap memasang daftar hardcode-nya sendiri."""
    _reload_config(monkeypatch, "https://app.contoh.com")
    reloaded_main = importlib.reload(app.main)

    cors = next(
        (m for m in reloaded_main.app.user_middleware if "CORS" in str(m.cls)),
        None,
    )
    assert cors is not None, "CORS middleware hilang"
    assert cors.kwargs.get("allow_origins") == ["https://app.contoh.com"]

    # `expose_headers` harus SELAMAT dari perubahan ini — tanpanya setiap
    # pengguna mengunduh "dokumen.docx" alih-alih nama sebenarnya (lihat
    # test_cors_exposes_content_disposition di test_routes_document.py).
    assert "Content-Disposition" in cors.kwargs.get("expose_headers", [])

    # Kredensial lintas-origin tak pernah dibutuhkan: token dikirim lewat header
    # Authorization, bukan cookie. Menyalakannya juga membuat `*` ilegal menurut
    # spec CORS, jadi ini sekaligus menjaga opsi itu tetap sah.
    assert not cors.kwargs.get("allow_credentials", False)
