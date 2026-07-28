"""Activity diagram gaya draw.io: PlantUML -> IR -> (PNG untuk docx | .drawio untuk disunting).

KENAPA ADA MODUL INI. Dokumen acuan (PREMCO) menggambar activity diagram di
draw.io: tabel berlajur User|Sistem, pita judul, kotak rounded, diamond keputusan,
alur menjulur ke BAWAH. PlantUML mendekatinya tapi tak bisa dikendalikan sampai
detail itu, dan `.drawio` sendiri tak bisa jadi gambar di docx tanpa mesin render
draw.io (Electron/Chromium) — dependency yang sengaja dihindari produk ini.

Jalan keluarnya: KITA yang menghitung tata letaknya. Begitu posisi node dan
belokan panah dihitung sendiri, keduanya bisa dipancarkan ke DUA keluaran dari
geometri yang SAMA:
  * `render_png`  -> PNG yang disisipkan ke .docx
  * `to_drawio`   -> file .drawio yang bisa dibuka & disunting tangan
Jadi gambar di dokumen dan file suntingannya tidak akan pernah berbeda bentuk.

JAMINAN TATA LETAK (inilah yang membuatnya rapi, bukan kebetulan):
  * Satu node per baris -> diagram menjulur ke bawah, bukan melebar. Cabang
    keputusan ditumpuk berurutan (bukan disebar), jadi `switch` 6-arah pun tidak
    membuat diagram melar.
  * Urutan baris topological -> semua panah mengalir ke bawah.
  * Panah hanya bergerak MENDATAR di lorong antar-baris dan MENURUN di napas kiri
    lajur; dua area itu dijamin bebas node. Karena itu panah tak pernah memotong
    node — bukan sekadar "jarang", tapi tak mungkin.

BATAS YANG DISENGAJA: parser hanya memahami subset PlantUML yang SYSTEM_PROMPT
kita sendiri wajibkan (`|Lane|`, `:Aksi;`, if/else/endif, switch/case/endswitch).
Script di luar itu (repeat/while/fork) dilaporkan lewat `supports()` supaya
pemanggil jatuh kembali ke PlantUML — lebih baik diagram gaya lama daripada
diagram yang isinya hilang diam-diam.
"""
from __future__ import annotations

import html
import re

from PIL import Image, ImageDraw, ImageFont

from app.diagram.ir.activity import (ActivityDiagramIR, ActivityEdge, ActivityNode,
                                     ActivityNodeKind, Lane)

# --- Geometri (satuan poin diagram; PNG di-render pada kelipatan _SS) ---------
NODE_W, NODE_H = 230, 54
DEC_W, DEC_H = 200, 76
DOT = 34
COL_GAP = 90            # napas kiri/kanan node di dalam lajur
ROW_GAP = 76            # lorong antar-baris; WAJIB > 2x sebaran offset panah,
                        # kalau tidak garis panah terdorong masuk pita baris berikutnya
HEADER, LANE_HDR = 44, 32
MARGIN = 30
SPINE_X0 = 26           # x tulang punggung, di dalam napas kiri lajur
EDGE_STEP = 8           # jarak antar panah di lorong yang sama
LANE_W = NODE_W + 2 * COL_GAP

_SS = 3                 # supersampling render PNG (digambar besar, diperkecil)
_INK, _PAPER = (0, 0, 0), (255, 255, 255)
_FONTS = ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf",
          "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")

# --- Sintaks yang dipahami (subset yang diwajibkan SYSTEM_PROMPT) ------------
_LANE = re.compile(r"^\|([^|]+)\|$")
_ACTION = re.compile(r"^:(.+);$")
_IF = re.compile(r"^if\s*\((.+?)\)\s*then\s*\((.*?)\)$", re.I)
_ELSEIF = re.compile(r"^elseif\s*\((.+?)\)\s*then\s*\((.*?)\)$", re.I)
_ELSE = re.compile(r"^else\s*\((.*?)\)$", re.I)
_SWITCH = re.compile(r"^switch\s*\((.+?)\)$", re.I)
_CASE = re.compile(r"^case\s*\((.*?)\)$", re.I)
_TITLE = re.compile(r"^title\s+(.+)$", re.I)
# Konstruksi yang BELUM didukung — kehadirannya membatalkan jalur ini.
_UNSUPPORTED = re.compile(r"^\s*(repeat|while|fork|split|partition|detach|backward)\b", re.I | re.M)


def supports(diagram_script: str) -> bool:
    """Bisakah script ini dirender lewat jalur IR? False = pemanggil harus jatuh
    kembali ke PlantUML (mis. ada `repeat`/`fork` yang parser belum pahami)."""
    if _UNSUPPORTED.search(diagram_script):
        return False
    return any(_ACTION.match(ln.strip()) for ln in diagram_script.splitlines())


# --- PlantUML -> IR ----------------------------------------------------------
def parse_activity(script: str, fallback_title: str = "") -> ActivityDiagramIR:
    ir = ActivityDiagramIR(title=fallback_title)
    lanes: dict[str, str] = {}
    seq = [0]

    def nid(prefix: str) -> str:
        seq[0] += 1
        return f"{prefix}{seq[0]}"

    def lane_id(label: str) -> str:
        label = label.strip()
        if label not in lanes:
            lid = re.sub(r"\W+", "_", label.lower()) or f"lane{len(lanes)}"
            lanes[label] = lid
            ir.lanes.append(Lane(id=lid, label=label))
        return lanes[label]

    cur_lane: str | None = None
    tails: list[tuple[str, str | None]] = []
    stack: list[dict] = []

    def add(kind: ActivityNodeKind, label: str = "") -> ActivityNode:
        node = ActivityNode(id=nid(kind.value[:2]), kind=kind, label=label, lane=cur_lane)
        ir.nodes.append(node)
        for src, guard in tails:
            ir.edges.append(ActivityEdge(source=src, target=node.id, guard=guard))
        return node

    for raw in script.splitlines():
        line = raw.strip()
        if not line or line.startswith(("@startuml", "@enduml", "skinparam", "!")):
            continue
        if m := _TITLE.match(line):
            ir.title = ir.title or m.group(1).strip()
            continue
        if m := _LANE.match(line):
            cur_lane = lane_id(m.group(1))
            continue
        if line.lower() == "start":
            tails = [(add(ActivityNodeKind.START).id, None)]
            continue
        if line.lower() in ("stop", "end"):
            add(ActivityNodeKind.END)
            tails = []
            continue
        if m := _ACTION.match(line):
            tails = [(add(ActivityNodeKind.ACTION, m.group(1).strip()).id, None)]
            continue
        if m := _IF.match(line):
            node = add(ActivityNodeKind.DECISION, m.group(1).strip())
            stack.append({"decision": node.id, "ends": [], "lane": cur_lane})
            tails = [(node.id, m.group(2).strip() or None)]
            continue
        if m := _SWITCH.match(line):
            node = add(ActivityNodeKind.DECISION, m.group(1).strip())
            stack.append({"decision": node.id, "ends": [], "lane": cur_lane})
            tails = []
            continue
        if m := (_ELSEIF.match(line) or _ELSE.match(line) or _CASE.match(line)):
            if not stack:
                continue
            frame = stack[-1]
            frame["ends"].extend(tails)          # tutup cabang yang sedang berjalan
            guard = (m.group(2) if _ELSEIF.match(line) else m.group(1)).strip() or None
            tails = [(frame["decision"], guard)]
            cur_lane = frame["lane"]
            continue
        if line.lower() in ("endif", "endswitch"):
            if not stack:
                continue
            frame = stack.pop()
            frame["ends"].extend(tails)
            cur_lane = frame["lane"]
            merge = ActivityNode(id=nid("mg"), kind=ActivityNodeKind.MERGE, lane=cur_lane)
            ir.nodes.append(merge)
            for src, guard in frame["ends"]:
                ir.edges.append(ActivityEdge(source=src, target=merge.id, guard=guard))
            tails = [(merge.id, None)]
            continue
    return ir


def elide_merges(ir: ActivityDiagramIR) -> ActivityDiagramIR:
    """Buang node MERGE, sambungkan cabangnya LANGSUNG ke penerus.

    Merge itu simpul UML "cabang bertemu kembali", tapi digambar sebagai belah
    ketupat KOSONG tanpa label dia tak menyampaikan apa pun ke pembaca dokumen —
    dan acuan draw.io pun tidak menggambarnya. Ketupat disisakan HANYA untuk
    keputusan berlabel. Rantai merge (dari `if` bersarang) ditelusuri transitif.
    """
    merges = {n.id for n in ir.nodes if n.kind is ActivityNodeKind.MERGE}
    if not merges:
        return ir
    out: dict[str, list[tuple[str, str | None]]] = {}
    for e in ir.edges:
        out.setdefault(e.source, []).append((e.target, e.guard))

    def resolve(nid: str, seen: frozenset = frozenset()) -> list[str]:
        if nid not in merges:
            return [nid]
        if nid in seen:
            return []
        found: list[str] = []
        for target, _guard in out.get(nid, []):
            found.extend(resolve(target, seen | {nid}))
        return found

    ir.nodes = [n for n in ir.nodes if n.id not in merges]
    rewired, seen_pairs = [], set()
    for e in ir.edges:
        if e.source in merges:
            continue
        for target in resolve(e.target):
            key = (e.source, target, e.guard)
            if key not in seen_pairs:
                seen_pairs.add(key)
                rewired.append(ActivityEdge(source=e.source, target=target, guard=e.guard))
    ir.edges = rewired
    return ir


# --- Tata letak --------------------------------------------------------------
def _rows(ir: ActivityDiagramIR) -> dict[str, int]:
    """Satu node per baris. Topological dengan preferensi DFS: cabang yang sedang
    berjalan diselesaikan dulu, jadi tiap cabang menempati blok baris bersambung —
    dan karena topological, baris tujuan SELALU di bawah baris sumber."""
    succ: dict[str, list[str]] = {}
    indeg = {n.id: 0 for n in ir.nodes}
    for e in ir.edges:
        succ.setdefault(e.source, []).append(e.target)
        if e.target in indeg:
            indeg[e.target] += 1
    ready = [n.id for n in ir.nodes if indeg[n.id] == 0] or [ir.nodes[0].id]
    order, placed, last = [], set(), None
    while ready:
        pick = next((c for c in succ.get(last, []) if c in ready), None) or ready[0]
        ready.remove(pick)
        order.append(pick)
        placed.add(pick)
        last = pick
        for t in succ.get(pick, []):
            if t in placed:
                continue
            indeg[t] -= 1
            if indeg[t] <= 0 and t not in ready:
                ready.append(t)
    order += [n.id for n in ir.nodes if n.id not in placed]
    row = {nid: i for i, nid in enumerate(order)}

    # PASANGKAN aksi lintas-lajur yang berurutan ke BARIS YANG SAMA.
    # Ini yang membuat diagram acuan terlihat bersih: "User menekan tombol" dan
    # "Sistem menampilkan formulir" duduk bersebelahan, dihubungkan garis PENDEK
    # mendatar. Tanpa ini tiap perpindahan lajur harus turun -> memutar lewat
    # lorong -> naik lagi, dan garis-garis panjang itulah yang terlihat kusut
    # dan seolah menggantung.
    preds: dict[str, list[str]] = {}
    for e in ir.edges:
        preds.setdefault(e.target, []).append(e.source)
    lane_of = {n.id: n.lane for n in ir.nodes}
    taken = {(lane_of[n], row[n]) for n in row}
    for nid in order:
        parents = preds.get(nid, [])
        if len(parents) != 1:
            continue
        parent = parents[0]
        # hanya kalau si induk memang cuma punya SATU penerus (pasangan
        # permintaan-respons), bukan cabang keputusan
        if len(succ.get(parent, [])) != 1 or lane_of[parent] == lane_of[nid]:
            continue
        slot = (lane_of[nid], row[parent])
        if slot in taken:
            continue
        # Aman terhadap urutan: baris nid hanya MENGECIL, sedangkan penerusnya
        # tetap di baris yang lebih besar -> panah tetap mengalir ke bawah.
        taken.discard((lane_of[nid], row[nid]))
        row[nid] = row[parent]
        taken.add(slot)

    used = sorted(set(row.values()))                # rapatkan baris yang kosong
    remap = {r: i for i, r in enumerate(used)}
    return {nid: remap[r] for nid, r in row.items()}


def _size(node: ActivityNode) -> tuple[int, int]:
    if node.kind in (ActivityNodeKind.START, ActivityNodeKind.END):
        return DOT, DOT
    if node.kind is ActivityNodeKind.DECISION:
        return DEC_W, DEC_H
    return NODE_W, NODE_H


def layout(ir: ActivityDiagramIR):
    """Geometri diagram. Lajur MENUTUP PENUH lebar dan bersambung tanpa celah
    (acuan: dua lajur bersebelahan rapat); node di tengah pita lajurnya, napas
    kirinya jadi jalur turun panah."""
    row = _rows(ir)
    lanes = [l.id for l in ir.lanes] or [None]
    lane_col = {lid: i for i, lid in enumerate(lanes)}

    def col_x(c: int) -> int:
        return c * LANE_W + (LANE_W - NODE_W) // 2

    def row_y(r: int) -> int:
        return HEADER + LANE_HDR + MARGIN + r * (NODE_H + ROW_GAP)

    pos = {}
    for n in ir.nodes:
        w, h = _size(n)
        c = lane_col.get(n.lane, 0)
        pos[n.id] = (col_x(c) + (NODE_W - w) // 2,
                     row_y(row[n.id]) + (NODE_H - h) // 2, w, h, c, row[n.id])
    width = len(lanes) * LANE_W
    height = row_y(max(row.values(), default=0)) + NODE_H + MARGIN
    lane_geom = {lid: (lane_col[lid] * LANE_W, LANE_W) for lid in lanes}
    return pos, row_y, width, height, lane_geom


def _paths(ir: ActivityDiagramIR, pos, row_y):
    """Jalur tiap panah sebagai daftar titik, beserta sisi keluar/masuknya.

    Tiga bentuk, sesuai acuan:
      * SEBARIS lintas lajur -> garis PENDEK mendatar (pasangan aksi-respons).
      * Sekolom, baris tepat di bawahnya -> garis lurus menurun.
      * Sisanya -> lewat lorong: mendatar di lorong antar-baris, menurun di napas
        kiri lajur. Dua area itu bebas node, jadi panah tak mungkin memotong node.

    Panah TIDAK lagi digeser-geser antar sesamanya: pemilik menyatakan garis boleh
    bertumpuk, dan menumpuknya justru lebih bersih daripada berkas garis sejajar.
    """
    def corr_y(r):
        return row_y(r) + NODE_H + ROW_GAP // 2

    def spine_x(lane_col):
        return lane_col * LANE_W + SPINE_X0

    out = []
    for i, e in enumerate(ir.edges):
        if e.source not in pos or e.target not in pos:
            continue
        sx, sy, sw, sh, sc, sr = pos[e.source]
        tx, ty, tw, th, tc, tr = pos[e.target]
        if sr == tr and sc != tc:                       # pasangan aksi-respons
            if tx > sx:
                pts = [(sx + sw, sy + sh / 2), (tx, ty + th / 2)]
                sides = ("right", "left")
            else:
                pts = [(sx, sy + sh / 2), (tx + tw, ty + th / 2)]
                sides = ("left", "right")
            out.append((i, e, pts, sides))
            continue
        x_from, y_from = sx + sw / 2, sy + sh
        x_to, y_to = tx + tw / 2, ty
        pts = [(x_from, y_from)]
        if tr == sr + 1:
            # Baris BERSEBELAHAN: cukup bentuk Z dengan SATU belokan di lorong.
            # (Dulu semua lintas-lajur dipaksa memutar ke spine kiri dulu — itu
            # yang melahirkan garis panjang melintasi seluruh diagram.)
            if sc != tc:
                cy = corr_y(sr)
                pts += [(x_from, cy), (x_to, cy)]
        else:
            # Lompatan jauh: turun lewat spine. Semua cabang dari SATU keputusan
            # memakai spine yang sama, jadi mereka menyatu jadi satu batang dengan
            # cabang pendek menyempil — persis pola acuan.
            cy1, cy2 = corr_y(sr), corr_y(tr - 1)
            cx = spine_x(min(sc, tc))
            pts += [(x_from, cy1), (cx, cy1), (cx, cy2), (x_to, cy2)]
        pts.append((x_to, y_to))
        out.append((i, e, pts, ("bottom", "top")))
    return out


# --- Keluaran 1: PNG untuk docx ---------------------------------------------
def _font(size: int):
    for name in _FONTS:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap(draw, text, font, max_w):
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if draw.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def _centered(draw, box, text, font, pad):
    x0, y0, x1, y1 = box
    lines = _wrap(draw, text, font, (x1 - x0) - 2 * pad)
    lh = (font.getbbox("Ag")[3] - font.getbbox("Ag")[1]) + 4 * _SS
    y = (y0 + y1) / 2 - lh * len(lines) / 2
    for ln in lines:
        draw.text(((x0 + x1) / 2 - draw.textlength(ln, font=font) / 2, y),
                  ln, fill=_INK, font=font)
        y += lh


def _longest_segment(points):
    """Titik tengah segmen TERPANJANG sebuah jalur, plus apakah ia mendatar.

    Dipakai menempelkan label cabang: segmen terpanjang adalah bagian yang paling
    jelas milik garis itu sendiri (bukan tunggak pendek yang berimpit dengan
    garis tetangga), jadi label mendarat di tempat yang tak ambigu.
    """
    best, best_len = (points[0], points[-1]), -1.0
    for a, b in zip(points, points[1:]):
        length = abs(b[0] - a[0]) + abs(b[1] - a[1])
        if length > best_len:
            best_len, best = length, (a, b)
    (x1, y1), (x2, y2) = best
    return ((x1 + x2) / 2, (y1 + y2) / 2), abs(x2 - x1) > abs(y2 - y1)


def _arrow_head(draw, p_from, p_to, size=9):
    (x1, y1), (x2, y2) = p_from, p_to
    s = size * _SS
    if abs(x2 - x1) < 1:
        d = 1 if y2 > y1 else -1
        pts = [(x2, y2), (x2 - s * .55, y2 - d * s), (x2 + s * .55, y2 - d * s)]
    else:
        d = 1 if x2 > x1 else -1
        pts = [(x2, y2), (x2 - d * s, y2 - s * .55), (x2 - d * s, y2 + s * .55)]
    draw.polygon(pts, fill=_INK)


# Piksel per titik diagram. TETAP (bukan "paksa lebar sekian") supaya UKURAN
# HURUF seragam antar diagram — diagram pendek dan panjang harus terbaca sama
# besar di halaman; kalau tiap diagram dipaksa selebar kanvas, yang isinya sedikit
# akan tampak berhuruf raksasa.
_PX_PER_POINT = 2.2


def render_png(ir: ActivityDiagramIR, out_path: str) -> None:
    pos, row_y, width, height, lane_geom = layout(ir)
    W, H = int(width * _SS), int(height * _SS)
    img = Image.new("RGB", (W, H), _PAPER)
    d = ImageDraw.Draw(img)
    f_node, f_lane, f_title, f_small = (_font(13 * _SS), _font(15 * _SS),
                                        _font(17 * _SS), _font(11 * _SS))
    lw = max(1, int(1.4 * _SS))

    d.rectangle([0, 0, W - lw, H - lw], outline=_INK, width=lw)
    d.line([0, HEADER * _SS, W, HEADER * _SS], fill=_INK, width=lw)
    d.text((W / 2 - d.textlength(ir.title, font=f_title) / 2,
            HEADER * _SS / 2 - f_title.size * .62), ir.title, fill=_INK, font=f_title)
    hdr = (HEADER + LANE_HDR) * _SS
    d.line([0, hdr, W, hdr], fill=_INK, width=lw)
    for lane in ir.lanes:
        lx, lwid = lane_geom[lane.id]
        if lx > 0:
            d.line([lx * _SS, HEADER * _SS, lx * _SS, H], fill=_INK, width=lw)
        d.text(((lx + lwid / 2) * _SS - d.textlength(lane.label, font=f_lane) / 2,
                (HEADER * _SS + hdr) / 2 - f_lane.size * .62),
               lane.label, fill=_INK, font=f_lane)

    for i, e, pts, _sides in _paths(ir, pos, row_y):  # panah dulu, node menimpanya
        scaled = [(x * _SS, y * _SS) for x, y in pts]
        for a, b in zip(scaled, scaled[1:]):
            d.line([a, b], fill=_INK, width=lw)
        _arrow_head(d, scaled[-2], scaled[-1])
        if e.guard:
            # Label DITEMPELKAN pada segmen TERPANJANG milik garisnya sendiri.
            # Dulu semua label cabang ditumpuk di bawah node keputusan, sehingga
            # pembaca tak bisa tahu "Ya" itu garis yang mana — kesalahan yang
            # membuat diagramnya salah dibaca, bukan sekadar kurang rapi.
            (lx, ly), horizontal = _longest_segment(scaled)
            tw_ = d.textlength(e.guard, font=f_small)
            th_ = f_small.size
            if horizontal:
                bx, by = lx - tw_ / 2, ly - th_ - 5 * _SS
            else:
                bx, by = lx + 6 * _SS, ly - th_ / 2
            pad = 3 * _SS
            d.rectangle([bx - pad, by - pad, bx + tw_ + pad, by + th_ + pad],
                        fill=_PAPER)          # latar putih supaya tak tertimpa garis
            d.text((bx, by), e.guard, fill=_INK, font=f_small)

    for n in ir.nodes:
        x, y, w, h, _c, _r = pos[n.id]
        box = [x * _SS, y * _SS, (x + w) * _SS, (y + h) * _SS]
        if n.kind is ActivityNodeKind.START:
            d.ellipse(box, fill=_INK)
        elif n.kind is ActivityNodeKind.END:
            d.ellipse(box, fill=_PAPER, outline=_INK, width=lw)
            pad = 5 * _SS
            d.ellipse([box[0] + pad, box[1] + pad, box[2] - pad, box[3] - pad], fill=_INK)
        elif n.kind is ActivityNodeKind.DECISION:
            cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
            d.polygon([(cx, box[1]), (box[2], cy), (cx, box[3]), (box[0], cy)], fill=_PAPER)
            d.line([(cx, box[1]), (box[2], cy), (cx, box[3]), (box[0], cy), (cx, box[1])],
                   fill=_INK, width=lw)
            _centered(d, box, n.label, f_small, 18 * _SS)
        else:
            d.rounded_rectangle(box, radius=10 * _SS, fill=_PAPER, outline=_INK, width=lw)
            _centered(d, box, n.label, f_node, 10 * _SS)

    out_w = max(1, int(width * _PX_PER_POINT))
    img.resize((out_w, max(1, int(H * out_w / W))), Image.LANCZOS).save(out_path)


# --- Keluaran 2: .drawio untuk disunting -------------------------------------
def _style(node: ActivityNode) -> str:
    if node.kind is ActivityNodeKind.START:
        return "ellipse;fillColor=#000000;strokeColor=#000000;"
    if node.kind is ActivityNodeKind.END:
        return "ellipse;shape=endState;fillColor=#000000;strokeColor=#000000;"
    if node.kind is ActivityNodeKind.DECISION:
        return "rhombus;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#000000;"
    return "rounded=1;arcSize=30;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#000000;"


def to_drawio(ir: ActivityDiagramIR) -> str:
    """XML mxGraph dengan geometri yang SAMA dengan PNG-nya."""
    pos, row_y, width, height, lane_geom = layout(ir)
    cells = [f'<mxCell id="pool" value="{html.escape(ir.title)}" '
             f'style="swimlane;horizontal=1;startSize={HEADER};html=1;fillColor=none;" '
             f'vertex="1" parent="1"><mxGeometry x="40" y="40" width="{width}" '
             f'height="{height}" as="geometry"/></mxCell>']
    for lane in ir.lanes:
        lx, lwid = lane_geom[lane.id]
        cells.append(f'<mxCell id="lane_{lane.id}" value="{html.escape(lane.label)}" '
                     f'style="swimlane;horizontal=1;startSize={LANE_HDR};html=1;'
                     f'fillColor=none;strokeColor=#000000;" vertex="1" parent="pool">'
                     f'<mxGeometry x="{lx}" y="{HEADER}" width="{lwid}" '
                     f'height="{height - HEADER}" as="geometry"/></mxCell>')
    for n in ir.nodes:
        x, y, w, h, _c, _r = pos[n.id]
        cells.append(f'<mxCell id="{n.id}" value="{html.escape(n.label)}" '
                     f'style="{_style(n)}" vertex="1" parent="pool">'
                     f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')
    for i, e, pts, sides in _paths(ir, pos, row_y):
        inner = "".join(f'<mxPoint x="{int(px)}" y="{int(py)}"/>' for px, py in pts[1:-1])
        arr = f'<Array as="points">{inner}</Array>' if inner else ""
        anchor = {"bottom": "exitX=0.5;exitY=1;", "top": "entryX=0.5;entryY=0;",
                  "right": "exitX=1;exitY=0.5;", "left": "entryX=0;entryY=0.5;"}
        exit_a = {"bottom": "exitX=0.5;exitY=1;", "right": "exitX=1;exitY=0.5;",
                  "left": "exitX=0;exitY=0.5;"}[sides[0]]
        entry_a = {"top": "entryX=0.5;entryY=0;", "left": "entryX=0;entryY=0.5;",
                   "right": "entryX=1;entryY=0.5;"}[sides[1]]
        del anchor
        cells.append(f'<mxCell id="e{i}" value="{html.escape(e.guard or "")}" '
                     f'style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=block;'
                     f'{exit_a}{entry_a}" edge="1" parent="pool" '
                     f'source="{e.source}" target="{e.target}">'
                     f'<mxGeometry relative="1" as="geometry">{arr}</mxGeometry></mxCell>')
    return ('<mxfile host="app.diagrams.net"><diagram name="' + html.escape(ir.title)
            + '"><mxGraphModel dx="1200" dy="900" grid="1" gridSize="10" page="1" '
            'pageWidth="850" pageHeight="1600"><root>'
            '<mxCell id="0"/><mxCell id="1" parent="0"/>' + "".join(cells)
            + '</root></mxGraphModel></diagram></mxfile>')


def build_ir(diagram_script: str, title: str = "") -> ActivityDiagramIR:
    """Jalur lengkap PlantUML -> IR siap render."""
    return elide_merges(parse_activity(diagram_script, title))
