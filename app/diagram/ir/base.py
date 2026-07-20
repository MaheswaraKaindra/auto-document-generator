"""Diagram IR — representasi diagram yang NETRAL & SEMANTIK (basis semua tipe).

IR menyimpan MAKNA diagram (aktor, node, edge, tipe), BUKAN:
- syntax backend (PlantUML/Mermaid) — itu urusan renderer,
- koordinat x/y atau informasi layout — itu urusan engine layout tiap backend.

Analoginya AST di compiler: IR = representasi semantik; tiap renderer = satu
"code generator" backend. IR tak boleh meng-import renderer mana pun.

Model = GRAF (nodes + edges [+ lanes]). Sengaja graf, bukan blok-terstruktur ala
PlantUML `if/else/endif`: graf memetakan LANGSUNG ke Mermaid flowchart, ReactFlow,
dan drawio (semuanya node+edge). Justru PlantUML activity yang "aneh" (butuh
rekonstruksi struktur dari graf) — dan itu tepat: menegaskan PlantUML cuma SATU
backend, bukan representasi utama.

Pydantic BaseModel (bukan dataclass biasa): dapat validasi gratis, dan siap
dipakai sebagai skema structured-output kalau kelak LLM meng-emit IR langsung
(fase "IR jadi source of truth").
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class DiagramType(str, Enum):
    """Diskriminator tipe diagram — dipakai renderer untuk dispatch. Nilai baru
    (SEQUENCE/DEPLOYMENT) ditambahkan di sini saat tipe barunya diperkenalkan."""
    ACTIVITY = "activity"
    USE_CASE = "use_case"
    ARCHITECTURE = "architecture"
    COMPONENT = "component"


class DiagramIR(BaseModel):
    """Basis semua IR diagram. Subclass menetapkan `diagram_type`-nya sendiri dan
    menambah field sesuai semantik tipenya. `title` = judul diagram (mis. nama
    aktivitas), netral terhadap backend."""
    diagram_type: DiagramType
    title: str = ""
