import json
import logging
from typing import List, Optional

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from app.core import config
from app.domain.exceptions import ContextWindowExceededError

load_dotenv()

logger = logging.getLogger(__name__)

# Dibaca dari .env (LLM_MODEL) supaya ganti model tidak perlu menyentuh kode.
# Ini model yang dipakai APLIKASI untuk menulis dokumen — terpisah dari model
# yang dipakai Claude Code saat mengerjakan project ini.
MODEL = config.LLM_MODEL


class UATTestCase(BaseModel):
    test_id: str = Field(description="ID unik untuk test case, misal: UAT-01")
    role: str = Field(description="Peran user yang melakukan test, misal: Admin atau User")
    activity: str = Field(description="Aktivitas utama yang diuji")
    steps: str = Field(description="Langkah-langkah pengujian (bernomor)")
    expected_result: str = Field(description="Hasil sistem yang diharapkan")


class ActivityDiagram(BaseModel):
    activity_name: str = Field(description="Nama fitur/modul spesifik, misal: 'Proses Login User' atau 'Manajemen Inventaris'")
    description: str = Field(description="Narasi singkat mengenai apa yang terjadi di aktivitas ini.")
    mermaid_script: str = Field(description="Script murni Mermaid flowchart TD khusus untuk aktivitas ini.")


class SDDDiagrams(BaseModel):
    system_architecture: str = Field(
        description="Mermaid graph LR: Komponen makro (User, Repo Frontend, Repo Backend, Database)."
    )
    component_integration: str = Field(
        description="Mermaid graph TD: Relasi teknis UI Component ke API Endpoint."
    )
    use_case_diagram: str = Field(
        description="Mermaid flowchart LR: Menyimulasikan Use Case UML. Aktor menggunakan node ((Actor)) dan aksi menggunakan node ([Action])."
    )
    activity_diagrams: List[ActivityDiagram] = Field(
        description="Daftar diagram aktivitas modular yang dipecah per fitur utama."
    )


class FeatureRequirement(BaseModel):
    feature_name: str = Field(description="Nama fitur, misal: 'Manajemen User' atau 'Pendataan Inventaris'")
    description: str = Field(description="Satu-dua kalimat menjelaskan apa yang bisa dilakukan user dengan fitur ini, ditulis dengan bahasa yang mudah dipahami non-teknis.")


class UseCase(BaseModel):
    use_case_id: str = Field(description="ID unik, misal: UC-01")
    actor: str = Field(description="Peran/role yang menjalankan use case ini")
    pre_condition: str = Field(description="Syarat yang harus terpenuhi sebelum use case ini bisa dijalankan")
    description: str = Field(description="Ringkasan fitur apa saja yang tercakup dalam use case ini untuk aktor tersebut")
    acceptance_criteria: List[str] = Field(description="Daftar kriteria penerimaan, satu kalimat per item, spesifik dan bisa diverifikasi")


class DocumentContent(BaseModel):
    document_type: str = Field(description="Jenis dokumen: 'SDD' atau 'UAT'")
    app_description: str = Field(description="Satu paragraf ringkasan fungsi utama sistem berdasarkan kode, ditulis dengan bahasa yang bisa dipahami pembaca non-teknis (product owner, QA, user bisnis), bukan hanya developer.")
    system_requirements: List[str] = Field(description="Daftar teknologi, library, atau framework yang terdeteksi.")
    feature_requirements: List[FeatureRequirement] = Field(description="Daftar fitur aplikasi beserta deskripsinya, diturunkan dari endpoint/UI component/class yang ditemukan di kode.")
    diagrams: SDDDiagrams = Field(description="Kumpulan script murni Mermaid.js untuk berbagai bab SDD.")
    use_cases: List[UseCase] = Field(description="Daftar use case terstruktur per aktor (bukan cuma diagram), lengkap dengan pre-condition, description, dan acceptance criteria.")
    business_flow_description: str = Field(description="Narasi alur bisnis lintas-repo (Frontend memanggil Backend API apa).")
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
- Field lain (`app_description`, `system_requirements`, `business_flow_description`) tetap diisi
  lengkap terlepas dari target_doc_type.

ATURAN FEATURE REQUIREMENTS (feature_requirements):
1. Satu entry per fitur/modul utama (bukan per endpoint/per fungsi individual) — kelompokkan endpoint
   dan UI component yang berkaitan menjadi satu fitur.
2. `description` ditulis dari sudut pandang user: apa yang bisa mereka lakukan, bukan cara kerjanya.

ATURAN USE CASE (use_cases):
1. Kelompokkan per aktor/role yang ditemukan di kode (misal dari nama role di endpoint/middleware/UI),
   atau per aktor generik ("User", "Admin") jika role tidak eksplisit di kode.
2. `acceptance_criteria` harus berupa kalimat spesifik dan bisa diverifikasi (bukan "sistem berjalan baik"),
   diturunkan dari endpoint/fitur yang benar-benar ada.

ATURAN DIAGRAM 1: SYSTEM ARCHITECTURE (diagrams.system_architecture)
1. Gunakan syntax `graph LR`. Level makro (User -> Frontend -> Backend -> Database). Jangan masukkan nama file/fungsi.

ATURAN DIAGRAM 2: COMPONENT INTEGRATION (diagrams.component_integration)
1. Gunakan syntax `graph TD`. Tarik panah (-->) dari 'ui_component' di Frontend menuju 'api_endpoints' di Backend.

ATURAN DIAGRAM 3: USE CASE DIAGRAM (diagrams.use_case_diagram)
1. Gunakan syntax `flowchart LR`.
2. Buat aktor eksternal dengan kurung ganda, contoh: `User(("User"))`.
3. Buat aksi (use case) dengan kurung siku lengkung, contoh: `UC1(["Melakukan Login"])`.

ATURAN DIAGRAM 4: ACTIVITY DIAGRAMS (diagrams.activity_diagrams)
1. Jangan buat satu diagram raksasa! Pecah alur sistem menjadi beberapa aktivitas modular (misal: satu untuk Login, satu untuk Transaksi, dll) berdasarkan endpoint/UI yang Anda temukan di JSON.
2. Untuk setiap aktivitas, buat `activity_name`, `description`, dan `mermaid_script`-nya masing-masing.
3. Gunakan syntax `flowchart TD` untuk setiap aktivitas.
4. Gunakan node belah ketupat untuk kondisi logika, contoh: `Cek{{"Valid?"}}`.

ATURAN UMUM & PENCEGAHAN SYNTAX ERROR (SANGAT PENTING):
- OUTPUT DIAGRAM HARUS SYNTAX MERMAID MURNI. Dilarang menggunakan tag ```mermaid.
- WAJIB MENGGUNAKAN TANDA KUTIP GANDA (" ") untuk setiap teks/label di dalam node.
- WAJIB MENGGUNAKAN ENTER / NEWLINE UNTUK MEMISAHKAN SETIAP BARIS PERNYATAAN.
- LARANGAN KEYWORD (RESERVED WORDS): JANGAN PERNAH menggunakan kata `end`, `start`, atau `subgraph` sebagai ID Node.
  CONTOH SALAH (AKAN FATAL ERROR): `start((Start)) --> A` atau `E --> end((End))`
  CONTOH BENAR: `StartNode(("Start")) --> A` atau `E --> EndNode(("End"))`
- Patuhi skema JSON output yang telah ditetapkan secara ketat!
- WAJIB MENGGUNAKAN ENTER / NEWLINE UNTUK MEMISAHKAN SETIAP BARIS PERNYATAAN. Dilarang keras menulis seluruh diagram dalam satu baris string!
  CONTOH FORMAT YANG BENAR:
  flowchart LR
  User(("User"))
  NodeA["Proses"]
  User --> NodeA

  CONTOH FORMAT YANG SALAH (AKAN ERROR):
  flowchart LR User(("User")) --> NodeA["Proses"]
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

        Pola yang sama dengan _render_mermaid_to_image di compiler_service:
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
                f"{json.dumps(parsed_repo_context, indent=2)}"
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

        response = self.client.messages.parse(
            model=MODEL,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            messages=messages,
            output_format=DocumentContent,
        )

        usage = response.usage
        # Tanpa log ini, cache yang diam-diam tidak pernah aktif mustahil
        # ketahuan — gejalanya cuma tagihan yang lebih mahal dari perkiraan.
        # cache_read 0 terus-menerus untuk repo yang sama = ada yang merusak
        # prefix (lihat catatan prefix match di atas).
        logger.info(
            "LLM %s: input=%s cache_write=%s cache_read=%s output=%s",
            target_doc_type,
            usage.input_tokens,
            usage.cache_creation_input_tokens,
            usage.cache_read_input_tokens,
            usage.output_tokens,
        )

        return response.parsed_output.model_dump()
