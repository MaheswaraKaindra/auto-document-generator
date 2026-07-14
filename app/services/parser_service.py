import json
import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

# Load environment variables dari file .env
load_dotenv()

def generate_file_metadata_prompt(file_name: str, file_content: str) -> str:
    prompt = f"""
    Anda adalah asisten AI khusus rekayasa perangkat lunak. Tugas Anda adalah mengekstrak 
    struktur dan metadata dari source code secara objektif.
    
    ATURAN KETAT:
    1. JANGAN menjelaskan alur logika kode.
    2. JANGAN menambahkan teks pembuka atau penutup.
    3. Output HARUS berupa JSON murni yang bisa langsung di-parse oleh sistem.

    Informasi Target:
    - Nama File: {file_name}
    
    Source Code:
    ```
    {file_content}
    ```
    
    Ekstrak data tersebut ke dalam skema JSON berikut:
    {{
        "file_name": "{file_name}",
        "type": "controller|service|repository|ui_component|model|other",
        "dependencies": ["daftar_import_atau_library_yang_dipakai"],
        "classes": [
            {{
                "class_name": "NamaClass",
                "methods": [
                    {{
                        "method_name": "namaFungsi",
                        "parameters": ["param1", "param2"],
                        "return_type": "tipe_data",
                        "description": "Ringkasan 1 kalimat apa yang dilakukan fungsi ini"
                    }}
                ]
            }}
        ],
        "api_endpoints": [
            // ISI HANYA JIKA FILE INI ADALAH CONTROLLER/ROUTER
            {{
                "method": "GET/POST/PUT/DELETE",
                "path": "/api/v1/contoh",
                "payload": "Keterangan data yang diterima (jika ada)"
            }}
        ]
    }}
    """
    return prompt

# if __name__ == "__main__":
#     dummy_file_name = "InventoryController.py"
#     dummy_file_content = """
#     from fastapi import APIRouter, Depends
#     from services import InventoryService

#     router = APIRouter(prefix="/api/inventory")

#     @router.post("/add")
#     def add_item(item_data: dict, service: InventoryService = Depends()):
#         '''Menambahkan item baru ke database inventory SPBU'''
#         return service.insert_item(item_data)
#     """

#     isolated_prompt = generate_file_metadata_prompt(dummy_file_name, dummy_file_content)
#     print("--- PROMPT YANG AKAN DIKIRIM KE LLM ---")
#     print(isolated_prompt)
    
#     print("\n--- MENGIRIM REQUEST KE API GEMINI (Mohon Tunggu) ---")
    
#     try:
#         # Inisialisasi LLM dengan Gemini (Otomatis membaca GOOGLE_API_KEY dari .env)
#         # temperature=0 memastikan respons kaku, konsisten, dan mematuhi skema JSON
#         llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
        
#         # Eksekusi prompt
#         response = llm.invoke(isolated_prompt)
#         llm_response = response.content
        
#         # Membersihkan tag markdown ```json ... ``` jika ditambahkan oleh Gemini
#         if llm_response.startswith("```json"):
#             llm_response = llm_response.replace("```json\n", "").replace("\n```", "").strip()
#         elif llm_response.startswith("```"):
#             llm_response = llm_response.replace("```\n", "").replace("\n```", "").strip()
            
#         # Parse teks string dari Gemini menjadi dictionary Python
#         metadata = json.loads(llm_response)
        
#         print("\n--- HASIL PARSING JSON ---")
#         print(json.dumps(metadata, indent=4))
        
#     except Exception as e:
#         print(f"\n[ERROR] Terjadi kesalahan saat memanggil Gemini atau mem-parsing JSON: {e}")