"""IR Activity Diagram — graf alur-kendali dengan swimlane opsional.

Mewakili DUA diagram di produk: activity per-fitur (`activity_diagrams[]`) dan
`business_process_flow` — keduanya activity diagram. Node = langkah/keputusan;
edge = urutan (dengan `guard` untuk label cabang keputusan); lane = swimlane
opsional (mis. "User" vs "System").
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.diagram.ir.base import DiagramIR, DiagramType


class ActivityNodeKind(str, Enum):
    START = "start"
    END = "end"
    ACTION = "action"
    DECISION = "decision"
    MERGE = "merge"     # titik menyatu-kembali sesudah percabangan
    FORK = "fork"       # mulai eksekusi paralel
    JOIN = "join"       # gabung eksekusi paralel


class Lane(BaseModel):
    id: str
    label: str


class ActivityNode(BaseModel):
    id: str
    kind: ActivityNodeKind
    label: str = ""              # kosong untuk start/end
    lane: str | None = None      # id lane; None = tanpa swimlane


class ActivityEdge(BaseModel):
    source: str
    target: str
    guard: str | None = None     # label cabang ("Ya"/"Valid"); None = edge biasa


class ActivityDiagramIR(DiagramIR):
    diagram_type: DiagramType = DiagramType.ACTIVITY
    lanes: list[Lane] = Field(default_factory=list)
    nodes: list[ActivityNode] = Field(default_factory=list)
    edges: list[ActivityEdge] = Field(default_factory=list)
