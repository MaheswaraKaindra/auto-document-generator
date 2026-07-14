import json
import os
from typing import List, Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()

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

class DocumentContent(BaseModel):
    document_type: str = Field(description="Jenis dokumen: 'SDD' atau 'UAT'")
    app_description: str = Field(description="Satu paragraf ringkasan fungsi utama sistem berdasarkan kode.")
    system_requirements: List[str] = Field(description="Daftar teknologi, library, atau framework yang terdeteksi.")
    diagrams: SDDDiagrams = Field(description="Kumpulan script murni Mermaid.js untuk berbagai bab SDD.")
    business_flow_description: str = Field(description="Narasi alur bisnis lintas-repo (Frontend memanggil Backend API apa).")
    uat_test_cases: List[UATTestCase] = Field(description="Daftar test case yang diekstrak dari UI components dan Endpoints.")

class LLMService:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0
        )
        
        self.structured_llm = self.llm.with_structured_output(DocumentContent)

    def generate_document_content(self, parsed_repo_context: dict, target_doc_type: str) -> dict:
        """
        Menerima Contract A (parsed_repo_context) dan mengembalikan Contract B.
        """
        
        system_prompt = """
        Anda adalah seorang Software Architect senior. Tugas Anda adalah menyusun konten untuk Solution Design Document (SDD) 
        berdasarkan metadata repositori JSON yang diberikan.

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

        human_prompt = """
        Berikut adalah metadata repositori (Contract A):
        {repo_context}
        """

        prompt_template = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", human_prompt),
        ])

        chain = prompt_template | self.structured_llm

        result_pydantic = chain.invoke({
            "target_doc_type": target_doc_type,
            "repo_context": json.dumps(parsed_repo_context, indent=2)
        })

        return result_pydantic.model_dump()