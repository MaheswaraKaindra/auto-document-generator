"""Render UseCaseDiagramIR -> PlantUML use case diagram.

`left to right direction`, aktor stick-figure, use case oval di dalam rectangle
batas sistem, panah aktor -> use case. Referensi lewat alias id supaya label bebas
spasi/karakter khusus tanpa merusak sintaks.
"""
from __future__ import annotations

from app.diagram.ir.usecase import UseCaseDiagramIR
from app.diagram.renderer.plantuml._common import q


def render(ir: UseCaseDiagramIR) -> str:
    lines = ["@startuml", "left to right direction"]
    for actor in ir.actors:
        lines.append(f"actor {q(actor.label)} as {actor.id}")
    lines.append(f"rectangle {q(ir.system_name)} {{")
    for use_case in ir.use_cases:
        lines.append(f"  usecase {q(use_case.label)} as {use_case.id}")
    lines.append("}")
    for assoc in ir.associations:
        lines.append(f"{assoc.actor} --> {assoc.use_case}")
    lines.append("@enduml")
    return "\n".join(lines)
