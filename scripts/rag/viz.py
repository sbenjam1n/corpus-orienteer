#!/usr/bin/env python3
"""
Graph/relationship visualization for the RAG ontology + supersession layers.

Emits Mermaid (default — renders natively in GitHub markdown and at mermaid.live, no
install) and Graphviz DOT (--dot, for `dot` users). If the mermaid CLI `mmdc` is on PATH,
`--png`/`--svg` render an image directly. Stdlib-only to generate; rendering is optional.

Targets (see query.py `viz` mode):
  links        the domain-object graph (canonical objects + typed links: twist_of,
               defined_over, has_galois_group, …) — the ontology, drawn
  graph VR-N   the supersession neighbourhood of a VR (correction + reference edges)
  arc VR-N     the correction graph of the arc containing VR-N

Outputs to data/rag/viz/<name>.{mmd,dot,svg,png}.
"""

import json, re, sys, shutil, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "rag"
VIZ_DIR = DATA_DIR / "viz"

# correction-class relations get a distinct (red) edge; reference-class are muted.
_CORRECTION = {"corrects", "refutes", "retracts", "supersedes", "downgrades", "amends",
               "correction_of", "corrected_by", "corrected_by_audit", "superseded_by",
               "retracted", "deprecated", "affected_by", "reopens"}
_TYPE_STYLE = {  # (mermaid classDef fill, stroke ; graphviz fillcolor)
    "curve": ("#cfe2ff", "#3b82f6"), "field": ("#d1fae5", "#10b981"),
    "group": ("#fee2e2", "#ef4444"), "parameter": ("#fef9c3", "#ca8a04"),
    "descent_map": ("#ede9fe", "#7c3aed"), "selmer": ("#fae8ff", "#c026d3"),
    "control_curve": ("#cffafe", "#0891b2"), "named_constant": ("#f1f5f9", "#64748b"),
    "other": ("#eeeeee", "#999999"),
}

def _load(name, default=None):
    try:
        return json.loads((DATA_DIR / name).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default

def _safe(s):
    """Mermaid/DOT-safe node id. Preserves the minus sign (encoded `m`) so signed twists
    do NOT collide: E^-7 -> n_E_m7 vs E^7 -> n_E_7."""
    s = s.replace("-", "m")
    return "n_" + re.sub(r"[^0-9A-Za-z]+", "_", s).strip("_")

def _label(s):
    return s.replace('"', "'")

# --------------------------------------------------------------------------
# graph builders -> (title, nodes:{id:type}, edges:[(src,rel,dst,is_correction)])
# --------------------------------------------------------------------------

def build_domain_links():
    objs = (_load("objects.json", {}) or {}).get("objects", {})
    links = (_load("domain_links.json", {}) or {}).get("links", [])
    type_of = {oid: o.get("type", "other") for oid, o in objs.items()}
    nodes, edges = {}, []
    for l in links:
        s, d, rel = l["source"], l["target"], l["relation"]
        # only edges between canonical objects — drops non-object targets like the
        # is_tower_level levels (Q->0, stem_1->1, stem_2->2).
        if s not in objs or d not in objs:
            continue
        nodes[s] = type_of.get(s, "other")
        nodes[d] = type_of.get(d, "other")
        edges.append((s, rel, d, False, bool(l.get("superseded"))))
    return ("Domain-object graph (ontology)", nodes, edges)

def build_supersession(vr, depth=1):
    edges_all = (_load("supersession.json", {}) or {}).get("edges", [])
    keep, frontier = [], {vr}
    seen_edges = set()
    for _ in range(depth):
        nxt = set()
        for e in edges_all:
            if e["source"] in frontier or e["target"] in frontier:
                key = (e["source"], e["relation"], e["target"])
                if key not in seen_edges:
                    seen_edges.add(key); keep.append(e)
                    nxt.add(e["source"]); nxt.add(e["target"])
        frontier = nxt
    nodes, edges = {}, []
    for e in keep:
        nodes.setdefault(e["source"], "vr"); nodes.setdefault(e["target"], "vr")
        edges.append((e["source"], e["relation"], e["target"], e["relation"] in _CORRECTION, False))
    nodes[vr] = "focus"
    return (f"Supersession neighbourhood of {vr} (depth {depth})", nodes, edges)

def build_arc(vr):
    arcs = _load("arcs.json", []) or []
    arc = next((a for a in arcs if vr in a.get("members", [])), None)
    if not arc:
        return None
    nodes = {m: "vr" for m in arc["members"]}
    nodes[vr] = "focus"
    edges = [(e["source"], e["relation"], e["target"], True, False)
             for e in arc.get("correction_edges", [])]
    return (f"Arc {arc['members'][0]}..{arc['members'][-1]} ({arc['size']} VRs, {arc['state']})",
            nodes, edges)

# --------------------------------------------------------------------------
# renderers
# --------------------------------------------------------------------------

def to_mermaid(title, nodes, edges, direction="LR"):
    out = [f"%%{{init: {{'flowchart': {{'curve':'basis'}}}}}}%%", f"graph {direction}"]
    out.append(f'  %% {title}')
    for nid, t in sorted(nodes.items()):
        shape = (f'(["{_label(nid)}"])' if t in ("vr", "focus")            # stadium for VR/AUDIT
                 else f'["{_label(nid)}"]')
        cls = "focus" if t == "focus" else (t if t in _TYPE_STYLE else "other")
        out.append(f'  {_safe(nid)}{shape}:::{cls}')
    for s, rel, d, corr, sup in edges:
        arrow = "-.->" if sup else ("==>" if corr else "-->")
        lab = rel + (" ⚠sup" if sup else "")
        out.append(f'  {_safe(s)} {arrow}|{lab}| {_safe(d)}')
    for t, (fill, stroke) in _TYPE_STYLE.items():
        out.append(f"  classDef {t} fill:{fill},stroke:{stroke},color:#111")
    out.append("  classDef vr fill:#f8fafc,stroke:#475569,color:#111")
    out.append("  classDef focus fill:#fde68a,stroke:#b45309,stroke-width:3px,color:#111")
    return "\n".join(out)

def to_dot(title, nodes, edges):
    out = [f'digraph "{title}" {{', '  rankdir=LR; node [style=filled,fontname=Helvetica];']
    for nid, t in sorted(nodes.items()):
        fill = "#fde68a" if t == "focus" else _TYPE_STYLE.get(t, _TYPE_STYLE["other"])[0]
        shape = "ellipse" if t in ("vr", "focus") else "box"
        out.append(f'  "{nid}" [fillcolor="{fill}", shape={shape}];')
    for s, rel, d, corr, sup in edges:
        style = "dashed" if sup else "solid"
        color = "#ef4444" if corr else "#64748b"
        out.append(f'  "{s}" -> "{d}" [label="{rel}", color="{color}", style={style}];')
    out.append("}")
    return "\n".join(out)

def _puppeteer_config():
    """mmdc's puppeteer needs a browser + (in sandboxes) --no-sandbox. Point it at a
    chrome-headless-shell / chrome from the puppeteer cache if present. Install once with:
    `npx puppeteer browsers install chrome-headless-shell`."""
    cache = Path.home() / ".cache" / "puppeteer"
    pats = ["chrome-headless-shell/*/*/chrome-headless-shell",
            "chrome/*/*/chrome", "chrome/*/*/*.app/Contents/MacOS/*"]
    cands = [c for p in pats for c in cache.glob(p) if c.is_file()]
    cfg = {"args": ["--no-sandbox"]}
    if cands:
        cfg["executablePath"] = str(cands[0])
    VIZ_DIR.mkdir(parents=True, exist_ok=True)
    cfgp = VIZ_DIR / ".pptr.json"; cfgp.write_text(json.dumps(cfg))
    return cfgp

_HTML = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<script src="https://cdn.jsdelivr.net/npm/d3@7"></script>
<style>
 html,body{margin:0;height:100%;font:13px/1.4 -apple-system,BlinkMacSystemFont,Helvetica,Arial,sans-serif;color:#111}
 #svg{position:fixed;inset:0;width:100%;height:100%;background:#fafafa}
 #hud{position:fixed;top:10px;left:10px;z-index:10;background:rgba(255,255,255,.96);border:1px solid #e5e7eb;border-radius:10px;padding:12px 14px;max-width:300px;box-shadow:0 2px 10px rgba(0,0,0,.08)}
 #hud h1{font-size:14px;margin:0 0 8px;font-weight:600}
 #hud .hint{font-size:11px;color:#6b7280;margin:6px 0}
 .legend span{display:inline-flex;align-items:center;margin:2px 10px 2px 0;font-size:11px}
 .legend i{width:11px;height:11px;border-radius:3px;margin-right:5px}
 #filters{margin-top:8px;max-height:34vh;overflow:auto}
 #filters label{display:block;font-size:11px;margin:2px 0;cursor:pointer;color:#374151}
 .node circle{stroke:#fff;stroke-width:1.5px;cursor:grab}
 .node text{font-size:11px;fill:#111;pointer-events:none;paint-order:stroke;stroke:#fafafa;stroke-width:3px}
 .lbl{font-size:9px;fill:#6b7280;pointer-events:none}
 #tip{position:fixed;z-index:20;pointer-events:none;background:#111827;color:#fff;padding:5px 8px;border-radius:5px;font-size:11px;opacity:0;transition:opacity .08s;max-width:300px}
</style></head>
<body>
<div id="hud"><h1>__TITLE__</h1><div class="legend" id="legend"></div>
 <div class="hint">drag nodes · scroll to zoom · drag background to pan · hover for detail</div>
 <div id="filters"></div></div>
<div id="tip"></div><svg id="svg"></svg>
<script>
const G = __DATA__;
const COLORS = {curve:"#3b82f6",field:"#10b981",group:"#ef4444",parameter:"#ca8a04",
 descent_map:"#7c3aed",selmer:"#c026d3",control_curve:"#0891b2",named_constant:"#64748b",
 vr:"#64748b",focus:"#f59e0b",other:"#9ca3af"};
const svg=d3.select("#svg"),tip=d3.select("#tip"),W=()=>innerWidth,H=()=>innerHeight;
const deg={};G.links.forEach(l=>{deg[l.source]=(deg[l.source]||0)+1;deg[l.target]=(deg[l.target]||0)+1;});
G.nodes.forEach(n=>n.deg=deg[n.id]||0);
const defs=svg.append("defs");
[["ac","#ef4444"],["ar","#9ca3af"]].forEach(([id,c])=>defs.append("marker").attr("id",id)
 .attr("viewBox","0 -5 10 10").attr("refX",20).attr("refY",0).attr("markerWidth",6).attr("markerHeight",6)
 .attr("orient","auto").append("path").attr("d","M0,-5L10,0L0,5").attr("fill",c));
const g=svg.append("g");
svg.call(d3.zoom().scaleExtent([0.1,4]).on("zoom",e=>g.attr("transform",e.transform)));
const link=g.append("g").selectAll("path").data(G.links).join("path").attr("class","link").attr("fill","none")
 .attr("stroke",d=>d.corr?"#ef4444":"#9ca3af").attr("stroke-width",d=>d.corr?2:1.2)
 .attr("stroke-dasharray",d=>d.sup?"4 3":null).attr("marker-end",d=>`url(#${d.corr?'ac':'ar'})`)
 .on("mousemove",(e,d)=>tipShow(e,`${d.source.id||d.source} —${d.rel}${d.sup?' (superseded)':''}→ ${d.target.id||d.target}`))
 .on("mouseout",()=>tip.style("opacity",0));
const lbl=g.append("g").selectAll("text").data(G.links).join("text").attr("class","lbl").text(d=>d.rel);
const node=g.append("g").selectAll("g").data(G.nodes).join("g").attr("class","node").call(drag());
node.append("circle").attr("r",d=>6+Math.min(d.deg,10)).attr("fill",d=>COLORS[d.type]||COLORS.other)
 .on("mousemove",(e,d)=>tipShow(e,`${d.id} · ${d.type} · degree ${d.deg}`)).on("mouseout",()=>tip.style("opacity",0));
node.append("text").attr("x",11).attr("y",4).text(d=>d.id);
const sim=d3.forceSimulation(G.nodes)
 .force("link",d3.forceLink(G.links).id(d=>d.id).distance(95).strength(.5))
 .force("charge",d3.forceManyBody().strength(-300))
 .force("center",d3.forceCenter(W()/2,H()/2))
 .force("collide",d3.forceCollide().radius(d=>20+Math.min(d.deg,10))).on("tick",tick);
function tick(){link.attr("d",d=>`M${d.source.x},${d.source.y}L${d.target.x},${d.target.y}`);
 lbl.attr("x",d=>(d.source.x+d.target.x)/2).attr("y",d=>(d.source.y+d.target.y)/2);
 node.attr("transform",d=>`translate(${d.x},${d.y})`);}
function drag(){return d3.drag().on("start",(e,d)=>{if(!e.active)sim.alphaTarget(.3).restart();d.fx=d.x;d.fy=d.y;})
 .on("drag",(e,d)=>{d.fx=e.x;d.fy=e.y;}).on("end",(e,d)=>{if(!e.active)sim.alphaTarget(0);d.fx=null;d.fy=null;});}
function tipShow(e,t){tip.style("opacity",1).style("left",(e.clientX+12)+"px").style("top",(e.clientY+12)+"px").text(t);}
d3.select("#legend").selectAll("span").data([...new Set(G.nodes.map(n=>n.type))]).join("span")
 .html(t=>`<i style="background:${COLORS[t]||COLORS.other}"></i>${t}`);
const rels=[...new Set(G.links.map(l=>l.rel))].sort(),f=d3.select("#filters");
f.append("div").style("cssText","font-weight:600;font-size:11px;margin:4px 0 2px").text("relations:");
rels.forEach(r=>{const lab=f.append("label");
 lab.append("input").attr("type","checkbox").property("checked",true).attr("data-rel",r).on("change",upd);
 lab.append("span").text(" "+r);});
function upd(){const on=new Set();d3.selectAll("#filters input").each(function(){if(this.checked)on.add(this.getAttribute("data-rel"));});
 link.style("display",d=>on.has(d.rel)?null:"none");lbl.style("display",d=>on.has(d.rel)?null:"none");}
addEventListener("resize",()=>sim.force("center",d3.forceCenter(W()/2,H()/2)).alpha(.3).restart());
</script></body></html>"""

def to_html(title, nodes, edges):
    data = {"title": title,
            "nodes": [{"id": n, "type": t} for n, t in nodes.items()],
            "links": [{"source": s, "target": d, "rel": rel, "corr": corr, "sup": sup}
                      for (s, rel, d, corr, sup) in edges]}
    return _HTML.replace("__TITLE__", _label(title)).replace("__DATA__", json.dumps(data))

def render_mmdflux(name, mermaid_text, ascii_only=False):
    """Render Mermaid to a terminal diagram (Unicode boxes/arrows) via `mmdflux` if
    available. Returns the .txt path or None."""
    if not shutil.which("mmdflux"):
        return None
    VIZ_DIR.mkdir(parents=True, exist_ok=True)
    src = VIZ_DIR / f"{name}.mmd"; src.write_text(mermaid_text)
    out = VIZ_DIR / f"{name}.txt"
    try:
        res = subprocess.run(
            ["mmdflux", "--color", "off", "-f", "ascii" if ascii_only else "text", str(src)],
            check=True, capture_output=True, text=True, timeout=60)
        out.write_text(res.stdout)
        return out
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None

def render(name, mermaid_text, fmt):
    """Render Mermaid to svg/png via mmdc if available. Returns output path or None."""
    if not shutil.which("mmdc"):
        return None
    VIZ_DIR.mkdir(parents=True, exist_ok=True)
    src = VIZ_DIR / f"{name}.mmd"; out = VIZ_DIR / f"{name}.{fmt}"
    src.write_text(mermaid_text)
    try:
        subprocess.run(["mmdc", "-i", str(src), "-o", str(out), "-b", "white",
                        "-p", str(_puppeteer_config())],
                       check=True, capture_output=True, timeout=180)
        return out
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None

def make(target, arg=None, fmt="mmd", depth=1):
    if target == "links":
        g = build_domain_links()
    elif target == "graph":
        g = build_supersession(arg, depth=depth)
    elif target == "arc":
        g = build_arc(arg)
        if g is None:
            return None, f"no arc contains {arg}"
    else:
        return None, f"unknown target '{target}' (use: links | graph VR-N | arc VR-N)"
    title, nodes, edges = g
    if not nodes:
        return None, "empty graph (no nodes)"
    name = "domain_links" if target == "links" else f"{target}_{_safe(arg)}"
    VIZ_DIR.mkdir(parents=True, exist_ok=True)
    if fmt == "dot":
        path = VIZ_DIR / f"{name}.dot"; path.write_text(to_dot(*g)); return path, None
    if fmt == "html":
        path = VIZ_DIR / f"{name}.html"; path.write_text(to_html(*g)); return path, None
    mermaid = to_mermaid(*g)
    if fmt in ("text", "ascii"):
        out = render_mmdflux(name, mermaid, ascii_only=(fmt == "ascii"))
        return (out, None) if out else (VIZ_DIR / f"{name}.mmd", "mmdflux unavailable; wrote .mmd")
    if fmt in ("svg", "png"):
        out = render(name, mermaid, fmt)
        return (out, None) if out else (VIZ_DIR / f"{name}.mmd", "mmdc unavailable/failed; wrote .mmd")
    path = VIZ_DIR / f"{name}.mmd"; path.write_text(mermaid)
    return path, None

if __name__ == "__main__":
    tgt = sys.argv[1] if len(sys.argv) > 1 else "links"
    a = sys.argv[2] if len(sys.argv) > 2 else None
    p, err = make(tgt, a)
    print(err or f"wrote {p}")
