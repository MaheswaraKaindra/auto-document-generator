"""Kontrak renderer diagram: IR -> string source backend.

Tiap backend (PlantUML sekarang; SVG/Mermaid/drawio/ReactFlow kelak)
meng-implement `DiagramRenderer`. Renderer mengonsumsi IR (app/diagram/ir) dan
menghasilkan source untuk backend-nya. Arah dependensi satu arah: renderer tahu
IR, IR tidak tahu renderer — analogi AST -> code generator.

Menambah backend baru = menambah SATU subclass DiagramRenderer di folder
renderer/<backend>/, TANPA menyentuh IR maupun pipeline. Itu inti extensibility
desain ini.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.diagram.ir.base import DiagramIR


class DiagramRenderer(ABC):
    """Antarmuka semua renderer. Implementasi memilih strategi per `diagram_type`."""

    @abstractmethod
    def render(self, ir: DiagramIR) -> str:
        """Ubah IR jadi source string backend ini (mis. PlantUML)."""
        raise NotImplementedError
