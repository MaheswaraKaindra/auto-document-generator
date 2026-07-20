"""IR System Architecture Diagram — komponen makro + ketergantungan berarah.

Node bertipe (aktor/komponen/database/cloud) dihubungkan panah berarah. Dipakai
untuk bab arsitektur sistem: User -> aplikasi -> database/layanan eksternal.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.diagram.ir.base import DiagramIR, DiagramType


class ArchNodeKind(str, Enum):
    ACTOR = "actor"
    COMPONENT = "component"
    DATABASE = "database"
    CLOUD = "cloud"      # layanan eksternal (mis. Cloudinary, Groq)


class ArchNode(BaseModel):
    id: str
    label: str
    kind: ArchNodeKind = ArchNodeKind.COMPONENT


class ArchEdge(BaseModel):
    source: str
    target: str
    label: str | None = None


class ArchitectureDiagramIR(DiagramIR):
    diagram_type: DiagramType = DiagramType.ARCHITECTURE
    left_to_right: bool = True    # orientasi makro; layout tetap urusan backend
    nodes: list[ArchNode] = Field(default_factory=list)
    edges: list[ArchEdge] = Field(default_factory=list)
