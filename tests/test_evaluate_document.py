"""Tes `scripts/evaluate_document.py` — alat ukur MUTU ISI dokumen.

Kenapa alat ukurnya sendiri perlu dites: metrik yang salah lebih berbahaya
daripada tidak punya metrik. Versi pertama menuduh 115 istilah "tak berjejak"
pada fixture yang isinya justru benar — dan tuduhan sebanyak itu bukan cuma
derau, ia MENENGGELAMKAN temuan yang sungguhan. Tiap false positive yang pernah
terjadi dikunci di sini supaya tak kembali.
"""
from scripts.evaluate_document import consistency, grounding, representation

# Contract A minimal: satu repo Vue/TS dengan satu endpoint & satu docstring.
_CONTRACT_A = {
    "repositories": [{
        "repo_tag": "App",
        "files": [
            {"file_name": "index.vue", "file_path": "pages/index.vue",
             "type": "ui_component", "dependencies": ["nuxt", "cloudinary"],
             "functions": [{"function_name": "load",
                            "description": "Ambil data dari Neon."}],
             "api_endpoints": []},
            {"file_name": "list.ts", "file_path": "server/api/list.ts",
             "type": "controller", "dependencies": [],
             "api_endpoints": [{"method": "GET", "path": "/api/produk"}]},
        ],
    }],
}


def _doc(**extra):
    return {"document_type": "SDD", "app_description": "", **extra}


def test_grounding_menangkap_karangan():
    hasil = grounding(_CONTRACT_A, _doc(app_description="Memakai RedisCluster."))
    assert "RedisCluster" in hasil["tak_berjejak"]


def test_grounding_menggeledah_seluruh_contract_a_bukan_satu_field():
    """"Neon" pernah dituduh karangan padahal ada di DOCSTRING — gara-gara yang
    digeledah cuma `dependencies`."""
    hasil = grounding(_CONTRACT_A, _doc(app_description="Basis data Neon.Serverless"))
    assert hasil["tak_berjejak"] == []


def test_alias_plantuml_bukan_klaim_isi():
    """`[pages/index.vue] as FeHome` — `FeHome` mesin diagram, `pages/index.vue`
    yang mengklaim. Tanpa ini satu diagram menyumbang puluhan tuduhan palsu:
    pada MyPertamina, 47 dari 48 "tak berjejak" ternyata alias."""
    doc = _doc(diagrams={"system_architecture":
                         "@startuml\n[pages/index.vue] as FeHome\n@enduml"})
    assert grounding(_CONTRACT_A, doc)["tak_berjejak"] == []


def test_bahasa_berjejak_lewat_ekstensi_file():
    """Repo Vue tak pernah menuliskan kata "typescript", tapi file `.ts`-nya
    adalah bukti sah — bukti ada di tempat yang tidak digeledah."""
    hasil = grounding(_CONTRACT_A, _doc(app_description="Ditulis TypeScript."))
    assert hasil["tak_berjejak"] == []


def test_nama_bertitik_cocok_lewat_pangkalnya():
    """Repo memakai nama paket ("nuxt"), dokumen memakai nama produk ("Nuxt.js")."""
    hasil = grounding(_CONTRACT_A, _doc(app_description="Dibangun Nuxt.js."))
    assert hasil["tak_berjejak"] == []


def test_representasi_menangkap_endpoint_yang_tak_diceritakan():
    sepi = representation(_CONTRACT_A, _doc(app_description="Aplikasi web."))
    assert sepi["tak_tersinggung"] == ["/api/produk"]

    disebut = representation(_CONTRACT_A, _doc(app_description="Menampilkan produk."))
    assert disebut["rasio"] == 1.0


def test_konsistensi_menangkap_aksi_diagram_yang_tak_diceritakan():
    """Pembaca melihat sesuatu di gambar yang tak ada penjelasannya."""
    doc = _doc(diagrams={"activity_diagrams": [{
        "activity_name": "Checkout",
        "steps": ["User membuka halaman keranjang"],
        "diagram_script": "@startuml\n:User membuka halaman keranjang;\n"
                          ":Sistem memotong stok gudang;\n@enduml"}]})
    hasil = consistency(doc)
    assert hasil["jumlah"] == 1
    assert "Checkout" in hasil["masalah"][0]


def test_konsistensi_membolehkan_teks_MERINGKAS_diagram():
    """Versi pertama metrik ini membandingkan JUMLAH langkah dan langsung
    melahirkan false positive: satu aktivitas meringkas enam aksi jadi satu
    kalimat sementara diagramnya memecahnya jadi enam node. Ceritanya sama,
    kedalamannya beda — dan meringkas itu SAH."""
    doc = _doc(diagrams={"activity_diagrams": [{
        "activity_name": "Kelola Pesanan",
        "steps": ["Admin memilih aksi: proses pesanan, tandai siap, batalkan"],
        "diagram_script": "@startuml\n:Admin memilih proses pesanan;\n"
                          ":Admin memilih tandai siap;\n"
                          ":Admin memilih batalkan pesanan;\n@enduml"}]})
    assert consistency(doc)["jumlah"] == 0
