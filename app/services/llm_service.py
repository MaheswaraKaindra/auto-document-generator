import json
import logging
from typing import List, Optional

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError

from app.core import config
from app.domain.exceptions import ContextWindowExceededError, DocumentTruncatedError

load_dotenv()

logger = logging.getLogger(__name__)

# Dibaca dari .env (LLM_MODEL) supaya ganti model tidak perlu menyentuh kode.
# Ini model yang dipakai APLIKASI untuk menulis dokumen — terpisah dari model
# yang dipakai Claude Code saat mengerjakan project ini.
MODEL = config.LLM_MODEL


def format_contract_a(parsed_repo_context: dict) -> str:
    """Serialisasi Contract A persis seperti yang dikirim ke LLM.

    DIEKSPOR supaya siapa pun yang ingin mengukur Contract A mengukur BENDA YANG
    SAMA. Ini bukan kerapian: `scripts/validation/` dulu memakai `json.dumps()`
    polos sementara di sini `indent=2`, jadi laporan ukurannya **meleset 21-25%**
    — medusa dilaporkan 2.831 KB padahal yang dikirim 1,58 juta token. Tiap
    keputusan yang bersandar pada angka itu ikut meleset. Dua tempat men-serialisasi
    hal yang sama = dua tempat yang bisa berbeda diam-diam.

    Compact rapat, tanpa spasi. Indentasi tidak menambah informasi apa pun untuk
    LLM — dia cuma dibayar. Diukur pada saleor: indent=2 = 1.224.476 token (122%
    context window, DITOLAK) vs rapat = 854.181 token (85%, MUAT). Aplikasi
    e-commerce Django nyata jadi bisa dilayani hanya dengan berhenti membayari
    spasi.

    Deterministik (dict Python menjaga urutan sisip), jadi prompt caching tetap
    nyantol — cocok-dari-depan butuh byte yang identik.
    """
    return json.dumps(parsed_repo_context, separators=(",", ":"))

# max_tokens itu batas TOTAL: thinking + teks jawaban berbagi jatah yang sama.
# Ini yang bikin 16.000 patah pada esteler-app (2026-07-15): claude-sonnet-5
# menjalankan adaptive thinking secara DEFAULT kalau field `thinking` tidak
# diisi — beda dari Sonnet 4.6 yang default-nya mati. Thinking memakan ~11K,
# menyisakan ~5K untuk JSON, dan dokumennya terpotong di tengah string.
#
# Thinking sengaja TIDAK dimatikan: tugas ini justru sintesis (baca puluhan
# endpoint, rancang fitur/use case/diagram), persis jenis kerja yang diuntungkan
# thinking. Yang dinaikkan jatahnya. 32.000 = ruang untuk ~15K thinking + ~15K
# dokumen, masih jauh di bawah batas keluaran model (128K).
MAX_OUTPUT_TOKENS = 32_000


class UATTestCase(BaseModel):
    test_id: str = Field(description="ID unik untuk test case, misal: UAT-01")
    role: str = Field(description="Peran user yang melakukan test, misal: Admin atau User")
    module: str = Field(
        description="Nama layar/halaman atau modul/fitur yang diuji, misal: "
        "'Halaman Login Website' atau 'Manajemen Inventaris'. Test case yang menguji "
        "layar/fitur yang SAMA HARUS memakai nilai `module` yang SAMA PERSIS — test case "
        "dikelompokkan per `module` di dokumen (satu tabel per modul)."
    )
    activity: str = Field(description="Aktivitas utama yang diuji")
    steps: str = Field(description="Langkah-langkah pengujian (bernomor)")
    expected_result: str = Field(description="Hasil sistem yang diharapkan")


class ActivityDiagram(BaseModel):
    activity_name: str = Field(description="Nama fitur/modul spesifik, misal: 'Proses Login User' atau 'Manajemen Inventaris'")
    description: str = Field(description="Narasi singkat mengenai apa yang terjadi di aktivitas ini.")
    actor: str = Field(description="Role/aktor yang menjalankan aktivitas ini, misal: 'Admin' atau 'Customer'")
    pre_condition: str = Field(description="Syarat yang harus terpenuhi sebelum aktivitas ini bisa dimulai")
    steps: List[str] = Field(description="Langkah-langkah aktivitas berurutan, satu kalimat per langkah ('Aktor melakukan X' / 'Sistem merespons Y'), konsisten dengan isi diagram_script")
    diagram_script: str = Field(description="Source PlantUML activity diagram murni untuk aktivitas ini (@startuml ... @enduml), BERLAJUR: pakai |NamaAktor| dan |Sistem| sebelum langkah sesuai pelakunya, dan sertakan percabangan (if/switch) sejauh berjejak di kode.")


class SDDDiagrams(BaseModel):
    system_architecture: str = Field(
        description="PlantUML component diagram level makro: actor User, component per repo/aplikasi, database & cloud HANYA kalau berjejak di metadata."
    )
    component_integration: str = Field(
        description="PlantUML component diagram: panah dari komponen UI/halaman ke endpoint backend yang dipanggilnya."
    )
    business_process_flow: str = Field(
        description="PlantUML activity diagram: FLOWCHART proses bisnis end-to-end, TANPA swimlane, wajib memuat minimal 2 titik keputusan (if/switch) yang berjejak di kode. Menggambar business_flow_steps."
    )
    use_case_diagram: str = Field(
        description="PlantUML use case diagram: actor + usecase di dalam rectangle sistem, dihubungkan panah, plus relasi <<include>>/<<extend>> antar-use-case bila berjejak."
    )
    activity_diagrams: List[ActivityDiagram] = Field(
        description="Daftar diagram aktivitas modular yang dipecah per fitur utama."
    )


class FeatureRequirement(BaseModel):
    feature_name: str = Field(description="Nama fitur, misal: 'Manajemen User' atau 'Pendataan Inventaris'")
    description: str = Field(description="Satu-dua kalimat menjelaskan apa yang bisa dilakukan user dengan fitur ini, ditulis dengan bahasa yang mudah dipahami non-teknis.")


class UserRole(BaseModel):
    role_name: str = Field(description="Nama role/aktor pengguna, misal: 'Admin' atau 'Customer'")
    description: str = Field(description="Apa yang boleh dilakukan role ini di sistem — hak akses & tanggung jawabnya, 1-2 kalimat non-teknis.")


class SystemRequirementItem(BaseModel):
    name: str = Field(description="Kategori requirement, misal: 'Programming Language', 'Web Framework', 'Database', 'External Service'")
    detail: str = Field(description="Isi kategorinya sesuai jejak di metadata, misal: 'Python — Flask' atau 'PostgreSQL (via SQLAlchemy)'")


class UseCase(BaseModel):
    use_case_id: str = Field(description="ID unik, misal: UC-01")
    actor: str = Field(description="Peran/role yang menjalankan use case ini")
    pre_condition: str = Field(description="Syarat yang harus terpenuhi sebelum use case ini bisa dijalankan")
    description: str = Field(description="Ringkasan fitur apa saja yang tercakup dalam use case ini untuk aktor tersebut")
    acceptance_criteria: List[str] = Field(description="Daftar kriteria penerimaan, satu kalimat per item, spesifik dan bisa diverifikasi")


class DocumentContent(BaseModel):
    document_type: str = Field(description="Jenis dokumen: 'SDD' atau 'UAT'")
    app_description: str = Field(description="Satu paragraf ringkasan fungsi utama sistem berdasarkan kode, ditulis dengan bahasa yang bisa dipahami pembaca non-teknis (product owner, QA, user bisnis), bukan hanya developer.")
    user_roles: List[UserRole] = Field(description="Daftar role/aktor pengguna sistem beserta hak aksesnya, diturunkan dari role yang terlihat di kode.")
    system_requirements: List[SystemRequirementItem] = Field(description="Requirement teknis terstruktur (kategori + isi) yang terdeteksi dari metadata kode.")
    feature_requirements: List[FeatureRequirement] = Field(description="Daftar fitur aplikasi beserta deskripsinya, diturunkan dari endpoint/UI component/class yang ditemukan di kode.")
    diagrams: SDDDiagrams = Field(description="Kumpulan source PlantUML murni untuk berbagai bab SDD.")
    use_cases: List[UseCase] = Field(description="Daftar use case terstruktur per aktor (bukan cuma diagram), lengkap dengan pre-condition, description, dan acceptance criteria.")
    business_flow_description: str = Field(description="Satu paragraf pengantar alur bisnis end-to-end (lintas-repo bila ada), non-teknis.")
    business_flow_steps: List[str] = Field(description="Tahapan alur proses bisnis bernomor dari awal sampai selesai, satu kalimat per tahap (siapa melakukan apa, sistem merespons apa).")
    uat_test_cases: List[UATTestCase] = Field(description="Daftar test case yang diekstrak dari UI components dan Endpoints.")


SYSTEM_PROMPT = """
Anda adalah seorang Software Architect senior sekaligus QA Lead yang menyusun konten dokumen teknis
(Solution Design Document / SDD dan User Acceptance Test / UAT) berdasarkan metadata repositori JSON
yang diberikan (hasil parsing Tree-sitter, bukan kode mentah).

PRINSIP UMUM PENULISAN (PENTING — ini SaaS yang dipakai berbagai kalangan, bukan cuma developer):
- `app_description`, `feature_requirements[].description`, `use_cases[].description`, dan
  `business_flow_description` HARUS bisa dipahami pembaca non-teknis (product owner, QA manual, user
  bisnis) — jelaskan APA yang bisa dilakukan sistem, bukan detail implementasi/nama fungsi/class.
- Jangan mengarang fitur yang tidak ada dasarnya di metadata JSON yang diberikan. Turunkan
  feature_requirements, use_cases, dan uat_test_cases dari api_endpoints/classes/functions/ui_component
  yang benar-benar ada.

ALOKASI FOKUS BERDASARKAN JENIS DOKUMEN YANG DIMINTA (target_doc_type):
- Jika target_doc_type == "SDD": prioritaskan kedalaman pada `diagrams` (terutama activity_diagrams —
  pecah jadi beberapa aktivitas modular per fitur utama), `feature_requirements`, dan `use_cases`
  (lengkap dengan acceptance_criteria yang spesifik). `uat_test_cases` cukup berisi beberapa test case
  representatif untuk fitur-fitur utama saja (tidak perlu exhaustive).
- Jika target_doc_type == "UAT": prioritaskan kedalaman pada `uat_test_cases` — buat test case untuk
  SETIAP fitur/endpoint/UI component utama yang ditemukan di metadata, bukan cuma beberapa. Untuk
  `diagrams` dan `use_cases`, cukup buat versi ringkas/high-level (tetap harus valid, jangan kosong).

ATURAN UAT TEST CASES (uat_test_cases):
1. Isi `module` dengan nama layar/halaman atau fitur yang diuji. Test case yang menguji layar/fitur
   yang SAMA WAJIB memakai nilai `module` yang SAMA PERSIS (huruf demi huruf) — dokumen
   mengelompokkan test case per `module` jadi satu tabel per layar, jadi konsistensi nilai ini penting.
2. URUTKAN test case sehingga yang ber-`module` sama berdampingan (jangan diselang-seling), dan
   kelompokkan secara logis (mis. semua layar milik satu peran/aplikasi berdekatan).
3. `steps` = langkah bernomor/berbaris; tiap langkah pada barisnya sendiri (pisahkan dengan newline).
- Field lain (`app_description`, `system_requirements`, `business_flow_description`) tetap diisi
  lengkap terlepas dari target_doc_type.

ATURAN BUKTI UNTUK DIAGRAM (SANGAT PENTING):
- Jangan menggambar komponen yang tidak punya jejak APA PUN di metadata JSON. Jejak bisa ada di mana
  saja: `dependencies`, `description` (docstring), nama class/function, endpoint. Contoh: JANGAN
  menggambar kotak Database kalau tidak ada satu pun jejak library database/ORM/koneksi DB di
  metadata. Diagram kecil yang semua kotaknya berjejak LEBIH BAIK daripada diagram lengkap yang
  separuhnya tebakan.

ATURAN USER ROLES (user_roles):
1. Turunkan dari role/aktor yang benar-benar terlihat di kode (route admin vs customer, middleware
   auth, nama tabel/kolom role). Kalau kode tidak membedakan role, cukup satu entry (mis. "User").
2. `description` = apa yang boleh dilakukan role itu di sistem, 1-2 kalimat non-teknis.

ATURAN SYSTEM REQUIREMENTS (system_requirements):
1. Tiap entry: `name` = kategori ("Programming Language", "Web Framework", "Database",
   "External Service", "Runtime", dst.), `detail` = isinya sesuai jejak di metadata.
2. Hanya tulis yang berjejak — jangan menebak versi atau menambah teknologi yang tidak terlihat.

ATURAN FEATURE REQUIREMENTS (feature_requirements):
1. Satu entry per fitur/modul utama (bukan per endpoint/per fungsi individual) — kelompokkan endpoint
   dan UI component yang berkaitan menjadi satu fitur.
2. `description` ditulis dari sudut pandang user: apa yang bisa mereka lakukan, bukan cara kerjanya.

ATURAN USE CASE (use_cases):
1. Kelompokkan per aktor/role yang ditemukan di kode (misal dari nama role di endpoint/middleware/UI),
   atau per aktor generik ("User", "Admin") jika role tidak eksplisit di kode.
2. `acceptance_criteria` harus berupa kalimat spesifik dan bisa diverifikasi (bukan "sistem berjalan baik"),
   diturunkan dari endpoint/fitur yang benar-benar ada.

ATURAN BUSINESS FLOW (business_flow_description, business_flow_steps):
1. `business_flow_description`: satu paragraf pengantar alur bisnis end-to-end, non-teknis.
2. `business_flow_steps`: 5-12 tahapan bernomor dari awal sampai selesai, satu kalimat per tahap,
   bergantian sudut pandang pengguna dan sistem ("Customer menambahkan menu ke keranjang", "Sistem
   membuat kode pesanan unik"). Harus konsisten dengan diagrams.business_process_flow.

SEMUA DIAGRAM = SOURCE PLANTUML MURNI (BUKAN MERMAID):
- Setiap field diagram WAJIB source PlantUML valid: baris pertama `@startuml`, baris terakhir
  `@enduml`. TANPA code fence markdown (```).
- DILARANG menulis `!theme`, `skinparam`, warna, atau font — gaya visual disuntik sistem secara
  terpusat. Tulis ISI diagram saja.
- Satu pernyataan per baris. Label yang mengandung spasi/karakter khusus WAJIB dalam tanda kutip
  ganda.

ATURAN DIAGRAM 1: SYSTEM ARCHITECTURE (diagrams.system_architecture)
1. Component diagram level makro. Baris kedua: `left to right direction`.
2. Elemen: `actor "User"`, `component "Nama" as Alias` per aplikasi/repo, `database "Nama"` HANYA
   kalau berjejak, `cloud "Nama"` untuk layanan eksternal yang berjejak. Hubungkan dengan `-->`.
3. Jangan masukkan nama file/fungsi.

ATURAN DIAGRAM 2: COMPONENT INTEGRATION (diagrams.component_integration)
1. Component diagram: kelompokkan per repo dengan `package "NamaRepo" { ... }`.
2. Tarik panah dari komponen UI/halaman ke endpoint backend yang dipanggilnya, contoh:
   `[Login.js] --> [POST /users/login]`.

ATURAN DIAGRAM 3: USE CASE DIAGRAM (diagrams.use_case_diagram)
1. Baris kedua: `left to right direction`.
2. Aktor: `actor Admin` (atau `actor "Nama Panjang" as Alias`). Use case oval di dalam kotak sistem:
   `rectangle "NamaSistem" { usecase "Melakukan Login" as UC1 }`.
3. Hubungkan: `Admin --> UC1`. Setiap use case harus terhubung ke minimal satu aktor.
4. TAMBAHKAN relasi antar-use-case kalau (dan HANYA kalau) berjejak di metadata:
   - `<<include>>` = perilaku WAJIB yang selalu dijalankan use case lain. Contoh paling lazim:
     endpoint yang dilindungi middleware auth => use case-nya meng-include "Login".
     Tulis: `UC3 ..> UC1 : <<include>>`  (UC3 selalu membutuhkan UC1)
   - `<<extend>>` = perilaku OPSIONAL/kondisional yang memperluas use case lain. Contoh: fitur
     yang cuma jalan pada kondisi tertentu (mis. "Beri Rating" hanya setelah pesanan selesai).
     Tulis: `UC9 ..> UC8 : <<extend>>`  (UC9 memperluas UC8)
   - Secukupnya saja (1-4 relasi). JANGAN mengarang relasi supaya diagram terlihat ramai —
     use case tanpa relasi antar-use-case itu normal dan lebih baik daripada relasi karangan.

DASAR SINTAKS ACTIVITY (dipakai ATURAN DIAGRAM 4 & 5)
- Mulai `start`, aksi `:Kalimat langkah;` (WAJIB diawali `:` dan diakhiri `;`), akhiri `stop`.
- Keputusan 2 cabang: `if (Kondisi?) then (Ya) ... else (Tidak) ... endif`.
- Keputusan >2 cabang: `switch (Pertanyaan?)` lalu `case (Pilihan A)` ... `case (Pilihan B)` ...
  ditutup `endswitch`.
- Pengulangan/kembali ke langkah sebelumnya: `repeat ... repeat while (Kondisi?) is (Ya) not (Tidak)`.

ATURAN DIAGRAM 4: BUSINESS PROCESS FLOW (diagrams.business_process_flow)
1. Ini FLOWCHART proses bisnis end-to-end — bukan diagram per-fitur, dan BUKAN diagram berlajur.
   DILARANG memakai swimlane (`|Lane|`) di diagram ini.
2. WAJIB memuat MINIMAL 2 titik keputusan (`if`/`switch`) yang benar-benar berjejak di metadata —
   contoh jejak: validasi input, cabang status pesanan/pembayaran, role berbeda, sukses vs gagal.
   Alur lurus tanpa satu pun percabangan TIDAK memadai untuk proses bisnis.
3. Gambarkan perjalanan bisnis utuh dari pemicu awal sampai hasil akhir, konsisten dengan
   `business_flow_steps`.

ATURAN DIAGRAM 5: ACTIVITY DIAGRAMS PER FITUR (diagrams.activity_diagrams)
1. Pecah per fitur utama (satu untuk Login, satu untuk Manajemen Menu, dst.) berdasarkan
   endpoint/UI di JSON — jangan satu diagram raksasa.
2. WAJIB memakai SWIMLANE: tulis `|Nama Aktor|` sebelum langkah yang dikerjakan MANUSIA dan
   `|Sistem|` sebelum langkah yang dikerjakan sistem. Tulis baris lane hanya saat lane BERGANTI.
   Nama lane aktor harus SAMA dengan field `actor` aktivitas itu.
3. Ceritakan WORKFLOW FITUR SECARA UTUH, bukan satu jalur lurus: masuk ke halaman -> aksi-aksi
   yang tersedia (mis. tambah/edit/hapus pakai `switch`) -> validasi -> hasil -> kembali ke daftar
   atau selesai. Sertakan percabangan dan pengulangan SEJAUH berjejak di metadata.
4. Sasaran kepadatan: sekitar 8-16 langkah dan 1-3 titik keputusan per diagram — TAPI angka ini
   BUKAN kuota. Kalau kode hanya mendukung 6 langkah, tulis 6. Lihat ATURAN KEJUJURAN di bawah.
5. BATAS LEBAR: maksimal 4 `case` dalam satu `switch`. Tiap `case` menjadi satu kolom SEJAJAR,
   jadi cabang yang terlalu banyak membuat diagram sangat lebar dan hurufnya mengecil saat
   dimuat ke halaman dokumen. Kalau aksinya lebih dari 4, KELOMPOKKAN yang sejenis menjadi satu
   case (mis. "Mengubah data pesanan" mencakup tandai-siap/selesai/batal), atau pecah aksi yang
   berdiri sendiri ke diagram aktivitas terpisah.
6. Untuk setiap aktivitas isi SEMUA field: `activity_name`, `description`, `actor`, `pre_condition`,
   `steps` (langkah bernomor — harus menceritakan alur yang SAMA dengan diagramnya), dan
   `diagram_script`.
7. Frasa tiap langkah WAJIB berawalan subjek yang jelas: "<Aktor> melakukan X" atau
   "Sistem melakukan Y". Ini menentukan penempatan lajur — kalimat tanpa subjek di depan
   (mis. "Validasi data") membuat langkahnya salah lajur.

ATURAN KEJUJURAN UNTUK KEPADATAN DIAGRAM (SANGAT PENTING):
- DILARANG menambah langkah, cabang, atau relasi hanya untuk memenuhi angka sasaran. Setiap
  langkah & cabang harus punya jejak di metadata (endpoint, nama fungsi/class, docstring,
  dependency, komponen UI).
- Diagram 8 langkah yang SEMUA langkahnya berjejak JAUH LEBIH BAIK daripada 16 langkah yang
  separuhnya karangan. Dokumen ini dinilai dari kebenarannya, bukan dari kepadatannya.

PENCEGAHAN SYNTAX ERROR PLANTUML:
- `if` WAJIB ditutup `endif`; `switch` WAJIB ditutup `endswitch`; `repeat` WAJIB ditutup
  `repeat while (...)`. Blok yang bersarang ditutup dari yang terdalam.
- Jangan memakai karakter `;` di DALAM teks langkah — dia penutup pernyataan.
- Baris lane ditulis sendirian: `|Admin|` (tanpa `:` dan tanpa `;`).
- Contoh ACTIVITY PER FITUR yang benar (berlajur, bercabang):
  @startuml
  |Admin|
  start
  :Admin membuka halaman manajemen menu;
  switch (Aksi yang dipilih?)
  case (Tambah)
    :Admin mengisi formulir menu baru;
  case (Edit)
    :Admin mengubah data menu;
  case (Hapus)
    :Admin menekan tombol hapus;
  endswitch
  |Sistem|
  :Sistem memvalidasi data menu;
  if (Data valid?) then (Ya)
    :Sistem menyimpan menu ke database;
    |Admin|
    :Admin melihat daftar menu terbaru;
  else (Tidak)
    :Sistem menampilkan pesan kesalahan;
    |Admin|
    :Admin memperbaiki isian formulir;
  endif
  stop
  @enduml
- Contoh BUSINESS PROCESS FLOW yang benar (TANPA lajur, tetap bercabang):
  @startuml
  start
  :Customer memilih menu dan menambahkannya ke keranjang;
  :Customer mengisi data pemesanan;
  if (Data pemesanan lengkap?) then (Ya)
    :Sistem membuat pesanan dengan kode unik;
  else (Tidak)
    :Sistem meminta Customer melengkapi data;
    stop
  endif
  :Admin memproses pesanan;
  if (Pesanan selesai diproses?) then (Ya)
    :Customer memberikan rating pesanan;
  else (Tidak)
    :Sistem menampilkan status pesanan berjalan;
  endif
  stop
  @enduml
- Patuhi skema JSON output yang telah ditetapkan secara ketat!
"""


# Jawaban dari Models API, di-cache per model. Bukan optimasi — tanpa cache,
# setiap generation menambah satu panggilan jaringan untuk fakta yang tidak
# berubah selama proses hidup.
_CONTEXT_WINDOW_CACHE: dict[str, Optional[int]] = {}


def _context_window(client: anthropic.Anthropic, model: str) -> Optional[int]:
    """Berapa token input yang muat di model ini? TANYA API-nya, jangan hardcode.

    Daftar hardcoded pasti basi — context window berubah antar model dan antar
    rilis. Dan daftar basi di sini justru berbahaya: guard-nya meloloskan repo
    yang sebenarnya kebesaran, API yang menolak, lalu kita kembali ke pesan
    "coba lagi nanti" yang menyesatkan — persis masalah yang guard ini ada untuk
    mencegah. Ini pelajaran yang sama dengan manifest.py: tanya sumber
    kebenarannya, jangan menebak lalu berharap tebakannya tetap benar.

    None = tidak bisa ditanya (jaringan putus, model tak dikenal). Sengaja
    GAGAL-MEMBUKA: pemeriksaan yang gagal tidak boleh menghalangi generation
    yang mungkin sebenarnya baik-baik saja. Kalau ternyata memang kebesaran,
    API tetap menolaknya — kita cuma kehilangan pesan yang bagus.
    """
    if model not in _CONTEXT_WINDOW_CACHE:
        try:
            _CONTEXT_WINDOW_CACHE[model] = client.models.retrieve(model).max_input_tokens
        except Exception:
            logger.warning(
                "Tidak bisa menanyakan context window %s ke Models API; "
                "pemeriksaan ukuran dilewati untuk panggilan ini.",
                model,
                exc_info=True,
            )
            _CONTEXT_WINDOW_CACHE[model] = None
    return _CONTEXT_WINDOW_CACHE[model]


class LLMService:
    def __init__(self):
        # Repo nyata bisa punya banyak fitur/endpoint sehingga generation-nya
        # (diagram + feature_requirements + use_cases + uat_test_cases sekaligus,
        # non-streaming) bisa melebihi default client timeout (10 menit) —
        # naikkan supaya repo besar tidak keburu di-cancel oleh SDK.
        self.client = anthropic.Anthropic(timeout=1500.0)

    def _guard_context_window(self, messages: list) -> None:
        """Tolak SEBELUM membayar kalau Contract A tidak akan muat.

        Pola yang sama dengan _run_plantuml di compiler_service:
        periksa dulu, gagal dengan pesan yang menyebut sebab asli beserta
        angkanya, jangan habiskan request percuma.

        Diukur pada repo nyata (2026-07-15): Contract A saleor = 1.224.476 token
        = 122% dari context window 1M. Tanpa guard ini, aplikasi bisnis Python
        sungguhan cuma menghasilkan 502 "coba lagi nanti" — saran yang tidak
        akan pernah menolong, berapa kali pun dicoba.

        count_tokens gratis (bukan generation), jadi guard ini tidak menambah
        biaya. Angkanya sedikit di bawah kenyataan karena skema output_format
        belum ikut terhitung — jadi ini LANTAI: yang ditolak di sini pasti
        memang kebesaran, tapi yang lolos tipis masih bisa ditolak API.
        """
        window = _context_window(self.client, MODEL)
        if window is None:
            return

        counted = self.client.messages.count_tokens(
            model=MODEL, system=SYSTEM_PROMPT, messages=messages
        ).input_tokens
        if counted <= window:
            return

        raise ContextWindowExceededError(
            f"Repo ini terlalu besar untuk model {MODEL}: metadata kodenya "
            f"{counted:,} token, sementara model ini cuma memuat {window:,}. "
            f"Mengulang tidak akan menolong. Pilih repo/cakupan yang lebih kecil, "
            f"atau pakai model dengan context window lebih besar lewat LLM_MODEL di .env."
        )

    def generate_document_content(self, parsed_repo_context: dict, target_doc_type: str) -> dict:
        """
        Menerima Contract A (parsed_repo_context) dan mengembalikan Contract B.
        """
        # Contract A ditaruh DULUAN, target_doc_type BELAKANGAN. Ini bukan soal
        # gaya penulisan — prompt caching itu cocok-dari-depan (prefix match):
        # begitu ada satu byte berbeda, semua yang sesudahnya batal. Versi
        # sebelumnya menaruh target_doc_type di depan, sehingga Contract A yang
        # puluhan ribu token itu dibayar PENUH dua kali ketika repo yang sama
        # diminta SDD lalu UAT — padahal isinya identik.
        #
        # cache_control ditaruh di akhir blok Contract A, jadi yang ter-cache
        # adalah SYSTEM_PROMPT + Contract A (system dirender sebelum messages).
        # Panggilan kedua untuk repo yang sama cuma bayar ~10% untuk bagian itu.
        context_block = {
            "type": "text",
            "text": (
                "Berikut adalah metadata repositori (Contract A):\n"
                f"{format_contract_a(parsed_repo_context)}"
            ),
            "cache_control": {"type": "ephemeral"},
        }
        # Satu-satunya bagian yang berubah antara SDD dan UAT. Ditaruh sesudah
        # breakpoint supaya tidak merusak cache — dan kebetulan ini juga posisi
        # terbaik untuk instruksi tugas: paling dekat dengan titik generation.
        task_block = {
            "type": "text",
            "text": f"Jenis dokumen yang diminta saat ini (target_doc_type): {target_doc_type}",
        }
        messages = [{"role": "user", "content": [context_block, task_block]}]

        self._guard_context_window(messages)

        # .stream() bukan .parse(): dengan max_tokens sebesar ini, request
        # non-streaming beresiko putus di tengah karena koneksi menganggur.
        # CLAUDE.md sudah menyarankan arah ini sejak timeout dinaikkan jadi 1500
        # detik — "pertimbangkan pindah ke .stream() daripada menaikkan timeout
        # terus-menerus". get_final_message() tetap mengembalikan ParsedMessage,
        # jadi structured output tidak berubah sama sekali.
        with self.client.messages.stream(
            model=MODEL,
            max_tokens=MAX_OUTPUT_TOKENS,
            system=SYSTEM_PROMPT,
            messages=messages,
            output_format=DocumentContent,
        ) as stream:
            try:
                response = stream.get_final_message()
            except ValidationError as e:
                # JSON terpotong itu GEJALA; sebabnya max_tokens. Tanpa
                # pemeriksaan ini yang sampai ke pengembang cuma "Invalid JSON:
                # EOF while parsing a string" dari Pydantic — terbaca seperti LLM
                # mengeluarkan sampah, padahal jatah keluaran kita sendiri yang
                # kurang. Persis kelas kesalahan yang sama dengan 502 yang dulu
                # menelan 414 mermaid.ink.
                snapshot = stream.current_message_snapshot
                if snapshot is not None and snapshot.stop_reason == "max_tokens":
                    raise DocumentTruncatedError(
                        f"Dokumen terpotong: model berhenti karena menabrak batas keluaran "
                        f"{MAX_OUTPUT_TOKENS:,} token (max_tokens), bukan karena selesai. "
                        f"Repo ini menghasilkan dokumen yang lebih besar dari jatah tersebut. "
                        f"Naikkan MAX_OUTPUT_TOKENS di llm_service.py."
                    ) from e
                raise

        usage_dict = {
            "input_tokens": getattr(usage, "input_tokens", 0) or 0,
            "output_tokens": getattr(usage, "output_tokens", 0) or 0,
            "cache_creation_input_tokens": getattr(usage, "cache_creation_input_tokens", 0) or 0,
            "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", 0) or 0,
        }
        logger.info(
            "LLM %s: input=%s cache_write=%s cache_read=%s output=%s",
            target_doc_type,
            usage_dict["input_tokens"],
            usage_dict["cache_creation_input_tokens"],
            usage_dict["cache_read_input_tokens"],
            usage_dict["output_tokens"],
        )

        content = response.parsed_output.model_dump()
        content["_usage"] = usage_dict
        return content

