"""Layer diagram: representasi diagram yang netral (IR) + renderer per-backend.

Redesign layer diagram (roadmap 2026-07-20, Option C). Tujuannya menjadikan
diagram punya arsitektur seperti compiler:

    Diagram IR (semantik, app/diagram/ir)  ==  AST
    Renderer   (per-backend, app/diagram/renderer)  ==  code generator

IR menyimpan MAKNA diagram; tiap renderer menerjemahkannya ke satu backend
(PlantUML sekarang; SVG/Mermaid/drawio/ReactFlow kelak). Arah dependensi SATU
arah: renderer meng-import IR, IR TIDAK PERNAH tahu renderer mana pun ada.

CATATAN INTEGRASI (penting, sengaja): modul ini BELUM disambung ke pipeline
generate dokumen yang hidup. Pipeline live tetap memakai PlantUML karangan LLM
langsung (lihat compiler_service._build_sdd_context) — jadi output DOCX TIDAK
berubah sama sekali. Menjadikan IR sebagai source of truth menuntut LLM meng-emit
IR (mengubah DocumentContent + prompt), sebuah langkah terpisah yang di-stage ke
fase berikutnya. Modul ini adalah fondasi + renderer pertama yang SIAP-PAKAI untuk
langkah itu, diuji berdiri sendiri.
"""
