"""Endpoint kontrol data pribadi: ekspor & hapus (#16).

Router terpisah, bukan tambahan di `routes_document`/`routes_billing`, karena
subjeknya bukan dokumen atau tagihan melainkan AKUN — dan pengguna yang mencari
"hapus data saya" tak akan menebaknya ada di bawah `/documents`.

Kebijakannya seluruhnya di `user_data_service` (tak tahu HTTP); di sini cuma
penerjemahan ke status code — pola yang sama dengan `deps._enforce`.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.api.deps import get_current_user
from app.services import user_data_service
from app.services.auth_service import Principal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/me", tags=["akun"])


def _translate_anonymous(e: user_data_service.AnonymousAccountError) -> HTTPException:
    """409, bukan 401/403.

    401 berarti "login dulu" — menyesatkan, sebab di instance ini tidak ADA yang
    bisa di-login-i. 403 berarti "kamu tak berhak" — juga salah, tak ada aturan
    yang dilanggar. 409 Conflict menyatakan yang sebenarnya: permintaannya sah,
    tapi bertabrakan dengan konfigurasi server saat ini.
    """
    return HTTPException(status_code=409, detail=str(e))


@router.get("/export")
def export_my_data(principal: Principal = Depends(get_current_user)):
    """Unduh SELURUH data akun ini sebagai ZIP (`data.json` + dokumen + template).

    Sengaja tanpa rate limit terpisah: ini hak akses pengguna atas datanya
    sendiri, dan biayanya cuma I/O disk — tak ada panggilan LLM di jalur ini.
    Kalau ekspor ternyata dipakai menyerang disk, batasnya ditambahkan belakangan
    dengan bukti, bukan sekarang atas dasar dugaan.
    """
    try:
        zip_path = user_data_service.export_user_data(principal)
    except user_data_service.AnonymousAccountError as e:
        raise _translate_anonymous(e) from e
    return FileResponse(zip_path, media_type="application/zip",
                        filename="data-saya.zip")


@router.delete("/data")
def delete_my_data(principal: Principal = Depends(get_current_user)):
    """Hapus seluruh data akun ini. **Tidak bisa dibatalkan.**

    Mengembalikan ringkasan apa yang dihapus, bukan sekadar 204. Pengguna yang
    baru saja menghapus datanya berhak tahu penghapusan itu benar-benar mengenai
    sesuatu — "0 dokumen dihapus" adalah jawaban yang harus terlihat, bukan
    tersembunyi di balik status kosong.

    Akunnya sendiri (di Supabase) TIDAK ikut terhapus: identitas itu hidup di
    provider auth, di luar jangkauan aplikasi ini. Yang dihapus adalah seluruh
    data yang aplikasi ini simpan tentang akun tersebut.
    """
    try:
        return user_data_service.delete_user_data(principal)
    except user_data_service.AnonymousAccountError as e:
        raise _translate_anonymous(e) from e
