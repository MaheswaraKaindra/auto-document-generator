"""PlantUML backend — IR -> source PlantUML (struktur saja, tanpa theme).

`PlantUMLRenderer` mendispatch per `diagram_type` ke fungsi render tipe-spesifik
(activity/usecase/architecture/component). Menambah dukungan tipe baru = tambah
satu entri di `_DISPATCH` + satu modul render — tanpa menyentuh dispatcher.
"""
from __future__ import annotations

from app.diagram.ir.base import DiagramIR, DiagramType
from app.diagram.renderer.base import DiagramRenderer
from app.diagram.renderer.plantuml import (
    activity,
    architecture,
    component,
    usecase,
)

# tipe diagram -> fungsi render(ir) -> str
_DISPATCH = {
    DiagramType.ACTIVITY: activity.render,
    DiagramType.USE_CASE: usecase.render,
    DiagramType.ARCHITECTURE: architecture.render,
    DiagramType.COMPONENT: component.render,
}


class PlantUMLRenderer(DiagramRenderer):
    """IR -> source PlantUML STRUKTUR-saja (tanpa `!theme`/`skinparam`).

    Gaya visual (theme + dpi) sengaja TIDAK ditulis di sini: compiler_service.
    _normalize_plantuml menyuntiknya terpusat — sama seperti perlakuan pada
    PlantUML karangan LLM. Itulah yang membuat output renderer ini masuk ke jalur
    render (`_normalize_plantuml` -> `_run_plantuml`) yang SAMA tanpa perubahan,
    sehingga penggantian source-of-truth ke IR kelak nol-selisih visual.
    """

    def render(self, ir: DiagramIR) -> str:
        try:
            render_fn = _DISPATCH[ir.diagram_type]
        except KeyError:
            raise ValueError(
                f"PlantUMLRenderer belum mendukung diagram_type={ir.diagram_type!r}. "
                f"Tersedia: {', '.join(t.value for t in _DISPATCH)}."
            )
        return render_fn(ir)


__all__ = ["PlantUMLRenderer"]
