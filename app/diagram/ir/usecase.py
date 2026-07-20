"""IR Use Case Diagram — aktor, use case, dan asosiasi di antaranya.

Struktur bipartit: aktor dihubungkan ke use case yang berada di dalam batas
sistem (`system_name`). Netral terhadap backend — tidak menyimpan posisi/oval.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.diagram.ir.base import DiagramIR, DiagramType


class Actor(BaseModel):
    id: str
    label: str


class UseCaseNode(BaseModel):
    id: str
    label: str


class Association(BaseModel):
    actor: str       # Actor.id
    use_case: str    # UseCaseNode.id


class UseCaseDiagramIR(DiagramIR):
    diagram_type: DiagramType = DiagramType.USE_CASE
    system_name: str = "System"
    actors: list[Actor] = Field(default_factory=list)
    use_cases: list[UseCaseNode] = Field(default_factory=list)
    associations: list[Association] = Field(default_factory=list)
