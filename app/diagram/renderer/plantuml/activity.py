"""Render ActivityDiagramIR -> PlantUML activity (start / :action; / if-else / stop).

Menerjemahkan GRAF IR ke sintaks PlantUML yang BLOK-terstruktur. Cakupan renderer
PERTAMA ini (sengaja, jujur): alur linear + keputusan (if / elseif / else) yang
cabangnya menuju terminal — persis bentuk yang produk hasilkan hari ini (lihat
grammar activity di SYSTEM_PROMPT llm_service). Rekonstruksi kontrol-flow yang
menyatu-kembali (reconvergence sesudah endif) dan loop `repeat/while` adalah
PERLUASAN renderer, bukan batas IR: IR sudah bisa mewakilinya lewat edge/MERGE,
hanya penerjemahan ke sintaks blok PlantUML yang butuh kerja lebih. Backend graf
murni (Mermaid/ReactFlow) tidak butuh langkah ini sama sekali.
"""
from __future__ import annotations

from collections import defaultdict

from app.diagram.ir.activity import ActivityDiagramIR, ActivityNodeKind
from app.diagram.renderer.plantuml._common import action_label, branch, condition


def render(ir: ActivityDiagramIR) -> str:
    nodes = {n.id: n for n in ir.nodes}
    lane_label = {lane.id: lane.label for lane in ir.lanes}
    succ: dict[str, list[tuple[str, str | None]]] = defaultdict(list)
    for edge in ir.edges:
        succ[edge.source].append((edge.target, edge.guard))

    lines = ["@startuml"]
    state = {"lane": None}
    emitted: set[str] = set()

    def switch_lane(node) -> None:
        # Swimlane opsional: pindah partition hanya saat lane node berganti.
        if ir.lanes and node.lane and node.lane != state["lane"]:
            lines.append(f"|{lane_label.get(node.lane, node.lane)}|")
            state["lane"] = node.lane

    def emit(node_id: str) -> None:
        if node_id in emitted or node_id not in nodes:
            return
        emitted.add(node_id)
        node = nodes[node_id]
        switch_lane(node)

        if node.kind == ActivityNodeKind.START:
            lines.append("start")
        elif node.kind == ActivityNodeKind.ACTION:
            lines.append(f":{action_label(node.label)};")
        elif node.kind == ActivityNodeKind.END:
            lines.append("stop")
            return
        elif node.kind == ActivityNodeKind.DECISION:
            branches = succ.get(node_id, [])
            if branches:
                first_target, first_guard = branches[0]
                lines.append(f"if ({condition(node.label)}) then{branch(first_guard)}")
                emit(first_target)
                for target, guard in branches[1:-1]:
                    lines.append(f"elseif ({condition(node.label)}) then{branch(guard)}")
                    emit(target)
                if len(branches) > 1:
                    last_target, last_guard = branches[-1]
                    lines.append(f"else{branch(last_guard)}")
                    emit(last_target)
                lines.append("endif")
            return
        # MERGE/FORK/JOIN pada renderer pertama diperlakukan pass-through.

        # Node non-terminal & non-decision: lanjut ke penerus tunggal.
        for target, _guard in succ.get(node_id, []):
            emit(target)

    starts = [n for n in ir.nodes if n.kind == ActivityNodeKind.START]
    for start in starts:
        emit(start.id)

    lines.append("@enduml")
    return "\n".join(lines)
