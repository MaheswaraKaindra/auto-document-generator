"""IR Component (Integration) Diagram — komponen dikelompokkan per paket + panggilan.

Dipakai untuk bab integrasi komponen: komponen UI/halaman (dikelompokkan per repo
lewat `package`) memanggil endpoint backend. Edge = pemanggilan berarah.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.diagram.ir.base import DiagramIR, DiagramType


class Package(BaseModel):
    id: str
    label: str


class ComponentNode(BaseModel):
    id: str
    label: str
    package: str | None = None   # Package.id; None = di luar paket mana pun


class ComponentEdge(BaseModel):
    source: str
    target: str
    label: str | None = None


class ComponentDiagramIR(DiagramIR):
    diagram_type: DiagramType = DiagramType.COMPONENT
    packages: list[Package] = Field(default_factory=list)
    nodes: list[ComponentNode] = Field(default_factory=list)
    edges: list[ComponentEdge] = Field(default_factory=list)
