"""Render ComponentDiagramIR -> PlantUML component diagram dengan paket.

Komponen dikelompokkan `package "Repo" { ... }` sesuai `node.package`; sisanya di
luar paket. Referensi lewat alias id (bukan `[Label]`) supaya nama file/route
ber-kurung siku TIDAK pernah masuk sintaks komponen — menghindari kelas bug
route-param yang pernah meng-crash jalur PlantUML LLM.
"""
from __future__ import annotations

from app.diagram.ir.component import ComponentDiagramIR
from app.diagram.renderer.plantuml._common import q


def render(ir: ComponentDiagramIR) -> str:
    lines = ["@startuml"]
    for package in ir.packages:
        lines.append(f"package {q(package.label)} {{")
        for node in ir.nodes:
            if node.package == package.id:
                lines.append(f"  component {q(node.label)} as {node.id}")
        lines.append("}")
    for node in ir.nodes:
        if not node.package:
            lines.append(f"component {q(node.label)} as {node.id}")
    for edge in ir.edges:
        arrow = f"{edge.source} --> {edge.target}"
        lines.append(f"{arrow} : {edge.label}" if edge.label else arrow)
    lines.append("@enduml")
    return "\n".join(lines)
