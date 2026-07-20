"""Render ArchitectureDiagramIR -> PlantUML component diagram (level makro).

Tiap node jadi elemen bertipe (actor/component/database/cloud) dengan alias id;
edge jadi panah berarah, dengan label opsional.
"""
from __future__ import annotations

from app.diagram.ir.architecture import ArchitectureDiagramIR, ArchNodeKind
from app.diagram.renderer.plantuml._common import q

_KEYWORD = {
    ArchNodeKind.ACTOR: "actor",
    ArchNodeKind.COMPONENT: "component",
    ArchNodeKind.DATABASE: "database",
    ArchNodeKind.CLOUD: "cloud",
}


def render(ir: ArchitectureDiagramIR) -> str:
    lines = ["@startuml"]
    if ir.left_to_right:
        lines.append("left to right direction")
    for node in ir.nodes:
        lines.append(f"{_KEYWORD[node.kind]} {q(node.label)} as {node.id}")
    for edge in ir.edges:
        arrow = f"{edge.source} --> {edge.target}"
        lines.append(f"{arrow} : {edge.label}" if edge.label else arrow)
    lines.append("@enduml")
    return "\n".join(lines)
