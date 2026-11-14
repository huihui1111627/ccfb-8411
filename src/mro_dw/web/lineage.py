"""从 dbt manifest.json / run_results.json 生成模型血缘 SVG。

- 节点：raw 源表 + staging/intermediate/marts 模型，按层分列
- 边：depends_on 父子关系
- 状态：run_results 里的 success/error/skipped 着色，
  直观展示"测试失败 -> 下游 SKIP"的阻断效果
"""
from __future__ import annotations

import html
import json

from ..paths import dbt_target_path

LAYER_BY_SCHEMA = {"raw": 0, "staging": 1, "intermediate": 2, "marts": 3}
LAYER_TITLE = {0: "raw 源", 1: "staging", 2: "intermediate", 3: "marts"}
LAYER_COLOR = {0: "#94a3b8", 1: "#38bdf8", 2: "#a78bfa", 3: "#34d399"}
STATUS_COLOR = {"success": "#16a34a", "error": "#dc2626",
                "skipped": "#9ca3af", "pass": "#16a34a", "fail": "#dc2626",
                "warn": "#d97706"}


def _load_json(path):
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_lineage() -> dict:
    # 不缓存：每次请求读取最新 manifest/run_results，重建后刷新即可见
    manifest = _load_json(dbt_target_path() / "manifest.json")
    if manifest is None:
        return {"available": False}
    run_results = _load_json(dbt_target_path() / "run_results.json")
    status: dict[str, str] = {}
    if run_results:
        for r in run_results.get("results", []):
            status[r["unique_id"]] = r["status"]

    nodes: dict[str, dict] = {}
    for uid, node in manifest.get("nodes", {}).items():
        if node.get("resource_type") != "model":
            continue
        schema = node.get("schema", "main")
        layer = LAYER_BY_SCHEMA.get(schema)
        if layer is None:
            continue
        nodes[uid] = {
            "id": uid,
            "name": node["name"],
            "layer": layer,
            "status": status.get(uid),
            "kind": "model",
        }
    for uid, src in manifest.get("sources", {}).items():
        nodes[uid] = {
            "id": uid,
            "name": src.get("name", uid),
            "layer": 0,
            "status": None,
            "kind": "source",
        }

    edges: list[tuple[str, str]] = []
    for uid, node in nodes.items():
        if node["kind"] != "model":
            continue
        raw = manifest["nodes"][uid]
        for parent in raw.get("depends_on", {}).get("nodes", []):
            if parent in nodes:
                edges.append((parent, uid))

    # 每个模型挂载的测试数与失败测试
    tests_by_node: dict[str, list[dict]] = {}
    for uid, node in manifest.get("nodes", {}).items():
        if node.get("resource_type") != "test":
            continue
        parents = node.get("depends_on", {}).get("nodes", [])
        for p in parents:
            if p in nodes:
                tests_by_node.setdefault(p, []).append(
                    {"name": node["name"], "status": status.get(uid, "unknown")})

    return {"available": True, "nodes": nodes, "edges": edges,
            "tests": tests_by_node, "status": status}


def render_svg() -> str:
    data = build_lineage()
    if not data.get("available"):
        return ('<div class="alert">未找到 dbt manifest，请先运行 '
                '<code>mro-dw build</code> 生成血缘。</div>')

    nodes, edges = data["nodes"], data["edges"]
    layers: dict[int, list[str]] = {0: [], 1: [], 2: [], 3: []}
    for uid, n in nodes.items():
        layers[n["layer"]].append(uid)
    for uids in layers.values():
        uids.sort(key=lambda u: nodes[u]["name"])

    box_w, box_h, vgap, xgap = 190, 46, 26, 120
    max_rows = max(len(v) for v in layers.values())
    width = 4 * box_w + 3 * xgap + 80
    height = max_rows * (box_h + vgap) + 90

    pos: dict[str, tuple[float, float]] = {}
    for layer, uids in layers.items():
        x = 40 + layer * (box_w + xgap)
        for i, uid in enumerate(uids):
            y = 60 + i * (box_h + vgap)
            pos[uid] = (x, y)

    parts: list[str] = [
        f'<svg viewBox="0 0 {width} {height}" width="100%" '
        f'role="img" aria-label="dbt 模型血缘图" font-family="sans-serif">',
        "<defs><marker id='arrow' markerWidth='9' markerHeight='9' refX='8' "
        "refY='3' orient='auto' markerUnits='strokeWidth'>"
        "<path d='M0,0 L8,3 L0,6 Z' fill='#64748b'/></marker></defs>",
    ]
    for layer, title in LAYER_TITLE.items():
        x = 40 + layer * (box_w + xgap)
        parts.append(
            f'<text x="{x + box_w / 2}" y="34" text-anchor="middle" '
            f'font-size="14" font-weight="700" fill="#334155">'
            f"{html.escape(title)}</text>")

    # 边
    for src, dst in edges:
        x1, y1 = pos[src]
        x2, y2 = pos[dst]
        mx = (x1 + box_w + x2) / 2
        parts.append(
            f'<path d="M{x1 + box_w},{y1 + box_h / 2} C{mx},{y1 + box_h / 2} '
            f'{mx},{y2 + box_h / 2} {x2},{y2 + box_h / 2}" fill="none" '
            f'stroke="#64748b" stroke-width="1.4" marker-end="url(#arrow)" opacity="0.75"/>')

    # 节点
    for uid, (x, y) in pos.items():
        n = nodes[uid]
        fill = LAYER_COLOR[n["layer"]]
        stroke = STATUS_COLOR.get(n["status"] or "", "#475569")
        sw = 2.2 if n["status"] else 1.2
        dash = ' stroke-dasharray="5 4"' if n["status"] == "skipped" else ""
        parts.append(
            f'<rect x="{x}" y="{y}" width="{box_w}" height="{box_h}" rx="7" '
            f'fill="{fill}" fill-opacity="0.16" stroke="{stroke}" '
            f'stroke-width="{sw}"{dash}/>')
        label = html.escape(n["name"][:26])
        parts.append(
            f'<text x="{x + box_w / 2}" y="{y + 22}" text-anchor="middle" '
            f'font-size="12" font-weight="600" fill="#0f172a">{label}</text>')
        sub = "source" if n["kind"] == "source" else "model"
        if n["status"]:
            sub += f" · {n['status']}"
        parts.append(
            f'<text x="{x + box_w / 2}" y="{y + 38}" text-anchor="middle" '
            f'font-size="10" fill="#475569">{html.escape(sub)}</text>')

    parts.append("</svg>")
    return "".join(parts)


def test_summary() -> list[dict]:
    data = build_lineage()
    if not data.get("available"):
        return []
    out: list[dict] = []
    for uid, tests in sorted(data["tests"].items(),
                             key=lambda kv: nodesort(kv[0], data)):
        for t in tests:
            out.append({"model": data["nodes"][uid]["name"], **t})
    return out


def nodesort(uid: str, data: dict) -> tuple:
    n = data["nodes"][uid]
    return n["layer"], n["name"]
