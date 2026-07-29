#!/usr/bin/env python3
"""tiers — optional corpus-tier declarations (P6 M1 substrate).

Reads `tiers.json` from SEED_DIR (same override chain as the other seeds:
RAG_SEED_DIR, else the engine dir). ABSENT ⟹ None ⟹ the engine behaves exactly as the
single-tier deployment — byte-identical outputs (the P6 C1 compatibility invariant,
regression-tested).

M1 scope (see docs/CORPUS_TIERS_DESIGN.md and plans/P6_corpus_tiers.md):
- tiers with `"contract": "vr"` contribute discovery roots (their docs follow the
  VR/AUDIT document contract and are chunk-indexed);
- every chunk and file_meta record is stamped with its tier id;
- tiers with `"indexed": false` (derived artifacts) are EXCLUDED from discovery even if
  a declared root overlaps the corpus — the generalized self-consumption guard;
- other declared tiers (threads / versioned papers / living plans / channels) are
  REGISTERED (resolvable via tier_of, reported in stats) but not chunked until their
  parsers land (M2/M4). Registering them is already useful: orient and monitors can
  refuse to treat their files as vr-contract documents.

Schema (tiers.json):
  { "tiers": [ { "id": str, "roots": [repo-root-relative prefixes],
                 "contract": "vr" | "rounds" | "versioned" | "living" | "channel",
                 "indexed": bool (default true), "authority": int,
                 "citable_as_receipt": bool, ... }, ... ] }
"""

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEED_DIR = Path(os.environ.get("RAG_SEED_DIR", Path(__file__).resolve().parent))


def load():
    """The declared tier list, or None (single-tier compatibility mode)."""
    try:
        cfg = json.loads((SEED_DIR / "tiers.json").read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    tiers = cfg.get("tiers")
    return tiers or None


def _rel(path):
    p = Path(path).resolve()
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def _norm_root(r):
    """Normalize a declared root through the SAME resolution as _rel(path), so the
    prefix comparison is symmetric. Asymmetry bug: contract_vr_roots resolves roots
    for discovery, but tier_of compared them raw — on macOS an absolute tmp root
    (/var/…, a symlink of /private/var/…) then matched no resolved doc path, so a
    doc discovered via a tier root was stamped by the wrong tier."""
    p = Path(r.rstrip("/"))
    p = (p if p.is_absolute() else ROOT / p).resolve()
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def tier_of(path, tiers):
    """The declared tier owning `path` (longest-matching root wins), or None."""
    if not tiers:
        return None
    rel = _rel(path)
    best, best_len = None, -1
    for t in tiers:
        for r in t.get("roots", []):
            rr = _norm_root(r)
            if (rel == rr or rel.startswith(rr + "/")) and len(rr) > best_len:
                best, best_len = t, len(rr)
    return best


def excluded(path, tiers):
    """True if `path` falls in an `indexed: false` tier (derived — never a source)."""
    t = tier_of(path, tiers)
    return bool(t) and t.get("indexed") is False


def contract_vr_roots(tiers, corpus_dir):
    """Extra discovery roots: contract='vr' tiers' roots beyond the main corpus dir."""
    roots = []
    corpus = str(Path(corpus_dir).resolve())
    for t in tiers or []:
        if t.get("indexed") is False or t.get("contract") != "vr":
            continue
        for r in t.get("roots", []):
            p = (ROOT / r).resolve()
            if str(p) != corpus and p.is_dir():
                roots.append((t["id"], p))
    return roots


def versioned_tiers(tiers):
    """Tiers whose supersession is implicit in filename version numbers (P6 M2)."""
    return [t for t in tiers or []
            if t.get("contract") == "versioned" or t.get("supersession") == "version_number"]


def build_versioned_docs(tiers):
    """P6 M2: version-number supersession synthesis.

    For each versioned tier: group files by FAMILY (filename with the version match
    removed), parse versions via the tier's `version_pattern` (regex over the
    filename; every captured group is a numeric version component), and mark every
    doc but the highest non-archived version `superseded` (docs under
    `archive_roots` are always superseded + `archived`). Content is NOT chunked —
    versioned docs do not follow the VR contract; this is graph metadata that makes
    superseded versions VISIBLE to orient with zero new authoring discipline.
    Deterministic: sorted walks, corpus-derived data only.
    """
    import re
    out = []
    for t in versioned_tiers(tiers):
        pat = t.get("version_pattern")
        if not pat:
            continue
        rx = re.compile(pat)
        archive_prefixes = [str((ROOT / a).resolve()) for a in t.get("archive_roots", [])]
        families = {}
        for root in t.get("roots", []):
            rp = (ROOT / root).resolve()
            if not rp.is_dir():
                continue
            for f in sorted(rp.rglob("*.md")):
                m = rx.search(f.name)
                if not m:
                    continue
                version = tuple(int(g) for g in m.groups() if g is not None)
                family = f"{t['id']}:{rx.sub('', f.name)}"
                archived = any(str(f.resolve()).startswith(a + "/") or
                               str(f.resolve()) == a for a in archive_prefixes)
                families.setdefault(family, []).append(
                    {"path": _rel(f), "version": list(version), "archived": archived})
        for family, docs in sorted(families.items()):
            live = [d for d in docs if not d["archived"]]
            current = max(live, key=lambda d: d["version"]) if live else None
            for d in sorted(docs, key=lambda d: d["version"]):
                rec = {"tier": t["id"], "family": family, "path": d["path"],
                       "version": d["version"], "archived": d["archived"]}
                if current and d["path"] != current["path"]:
                    rec["status"] = "superseded"
                    rec["superseded_by"] = current["path"]
                elif current:
                    rec["status"] = "current"
                else:
                    rec["status"] = "superseded"   # archive-only family: no live current
                    rec["superseded_by"] = None
                out.append(rec)
    return out


def classify_versioned_citations(texts_with_labels, versioned_docs):
    """P6 M2 orient hook: which versioned docs do the given inputs cite or ARE they,
    and what is each one's verdict? Returns [(path, status, superseded_by|None)] for
    every versioned doc that appears as an input label or as a path substring in an
    input text — candidates to READ, never verdicts about the citing document."""
    hits = {}
    for rec in versioned_docs:
        path = rec["path"]
        for label, text in texts_with_labels:
            if label == path or path in text:
                hits[path] = (rec["status"] + (" (archived)" if rec["archived"] else ""),
                              rec.get("superseded_by"))
                break
    return [(p, s, sb) for p, (s, sb) in sorted(hits.items())]


# --- P6 M3: thread tiers, capture ledger, receipt discipline -------------------

DEFAULT_ROUND_PATTERN = r"(?m)^#{1,4}[^\n]*\bR(\d+)\b"

def thread_tiers(tiers):
    """Tiers holding dialogic round-structured threads (correspondence)."""
    return [t for t in tiers or []
            if t.get("contract") == "rounds" or t.get("supersession") == "rounds"]


def build_thread_registry(tiers):
    """Minimal thread registry (full rounds/party parsing is M4): for each thread-tier
    file `<PREFIX>-<N>_<slug>.md`, the set of round numbers found via the tier's
    `round_pattern` (one numeric group; default: round tokens R<k> in headings).
    Deterministic: sorted walks, content-derived only."""
    import re
    out = []
    for t in thread_tiers(tiers):
        prefix = (t.get("doc_id") or {}).get("primary", "THREAD")
        rx = re.compile(t.get("round_pattern", DEFAULT_ROUND_PATTERN))
        stem_rx = re.compile(rf"^({re.escape(prefix)})-(\d+)")
        for root in t.get("roots", []):
            rp = (ROOT / root).resolve()
            if not rp.is_dir():
                continue
            for f in sorted(rp.glob(f"{prefix}-*.md")):
                m = stem_rx.match(f.stem)
                if not m:
                    continue
                text = f.read_text(encoding="utf-8", errors="replace")
                rounds = sorted({int(g.group(1)) for g in rx.finditer(text)})
                out.append({"tier": t["id"], "thread_id": f"{prefix}-{m.group(2)}",
                            "path": _rel(f), "rounds": rounds,
                            "citable_as_receipt": bool(t.get("citable_as_receipt"))})
    return out


_CAPTURE_RE_TMPL = r"\bcaptures?\s+{prefix}-(\d+)(?:\s+R(\d+))?\b"
_SOFTENERS = ("not a receipt", "never a receipt", "verification-weight", "captures",
              "advisory", "unreconciled", "to be captured", "candidate")


def build_capture_ledger(tiers, all_meta, chunks, metadata_text_of):
    """P6 M3: (a) `captures THREAD-N [R<k>]` edges from vr-tier doc METADATA (title/
    Status/Supersession lines — the same metadata-only discipline as correction verbs;
    body prose discussing a capture creates no edge); (b) the unreconciled-rounds
    report (thread rounds with no capturing doc); (c) receipt-laundering CANDIDATES:
    vr-tier chunks citing a round of a `citable_as_receipt: false` thread outside any
    capture declaration and without a softener in the window — regions to READ, never
    verdicts. Returns dict or None when no thread tiers are declared."""
    import re
    registry = build_thread_registry(tiers)
    if not registry:
        return None
    prefixes = sorted({(t.get("doc_id") or {}).get("primary", "THREAD")
                       for t in thread_tiers(tiers)})
    edges = []
    for meta in all_meta:
        mt = metadata_text_of(meta)
        for prefix in prefixes:
            for m in re.finditer(_CAPTURE_RE_TMPL.format(prefix=re.escape(prefix)), mt):
                edges.append({"vr": meta.get("id"),
                              "thread": f"{prefix}-{m.group(1)}",
                              "round": int(m.group(2)) if m.group(2) else None})
    edges = list({(e["vr"], e["thread"], e["round"]): e for e in edges}.values())
    captured = {(e["thread"], e["round"]) for e in edges}
    captured_whole = {e["thread"] for e in edges if e["round"] is None}
    unreconciled = []
    for th in registry:
        for r in th["rounds"]:
            if (th["thread_id"], r) not in captured and th["thread_id"] not in captured_whole:
                unreconciled.append({"thread": th["thread_id"], "round": r,
                                     "path": th["path"]})
    # receipt-laundering candidates: round citations in non-receipt threads, in chunks
    nonreceipt = {th["thread_id"] for th in registry if not th["citable_as_receipt"]}
    cands = []
    for ch in chunks:
        if ch.get("status") in ("retracted", "deprecated", "corrected"):
            continue
        content = ch.get("content", "")
        for prefix in prefixes:
            for m in re.finditer(rf"\b({re.escape(prefix)}-(\d+))\s+R(\d+)\b", content):
                tid, rnd = m.group(1), int(m.group(3))
                if tid not in nonreceipt:
                    continue
                if (tid, rnd) in captured or tid in captured_whole:
                    continue
                w = content[max(0, m.start() - 90): m.end() + 90].lower()
                if any(sf in w for sf in _SOFTENERS):
                    continue
                span = re.sub(r"\s+", " ", content[max(0, m.start() - 40): m.end() + 40]).strip()
                cands.append({"vr": ch.get("vr_id"), "thread": tid, "round": rnd,
                              "span": span[:120]})
    dedup = {(c["vr"], c["thread"], c["round"]): c for c in cands}
    return {"threads": registry, "captures": edges, "unreconciled_rounds": unreconciled,
            "receipt_candidates": sorted(dedup.values(),
                                         key=lambda c: (c["vr"], c["thread"], c["round"]))}


# --- P6 M4: thread-round chunking + party parsing + detector scoping ------------

def build_thread_chunks(tiers, extract_entities):
    """Chunk thread-tier files per ROUND (each round = one chunk; section = "R<k>").
    Party comes from the tier's `party_pattern` (regex with one group, applied to the
    round's heading line) when `party_headers` is true — config only, no guessing.
    Thread chunks carry tier + party and status "active"; they are EXCLUDED from
    claim-status/strata (their claims are party-scoped and unreconciled by definition —
    the capture ledger is their surface) and participate only in detectors their tier
    declares (see detectors_for)."""
    import re
    chunks = []
    for t in thread_tiers(tiers):
        prefix = (t.get("doc_id") or {}).get("primary", "THREAD")
        rx = re.compile(t.get("round_pattern", DEFAULT_ROUND_PATTERN))
        party_rx = re.compile(t["party_pattern"]) if t.get("party_pattern") else None
        stem_rx = re.compile(rf"^({re.escape(prefix)})-(\d+)")
        for root in t.get("roots", []):
            rp = (ROOT / root).resolve()
            if not rp.is_dir():
                continue
            for f in sorted(rp.glob(f"{prefix}-*.md")):
                m = stem_rx.match(f.stem)
                if not m:
                    continue
                tid = f"{prefix}-{m.group(2)}"
                text = f.read_text(encoding="utf-8", errors="replace")
                marks = list(rx.finditer(text))
                for i, mk in enumerate(marks):
                    end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
                    body = text[mk.start():end].strip()
                    heading = body.split("\n", 1)[0]
                    rnd = int(mk.group(1))
                    party = None
                    if t.get("party_headers") and party_rx:
                        pm = party_rx.search(heading)
                        party = pm.group(1).strip() if pm else None
                    ch = {"chunk_id": f"{tid}:R{rnd}", "vr_id": tid,
                          "section": f"R{rnd}", "content": body[:4000],
                          "date": None, "iter": None, "status": "active",
                          "supersession": [], "entities": sorted(extract_entities(body)),
                          "content_hash": __import__("hashlib").sha256(
                              body[:4000].encode()).hexdigest()[:16],
                          "tier": t["id"]}
                    if party:
                        ch["party"] = party
                    chunks.append(ch)
    return chunks


def detectors_for(tiers):
    """tier id -> declared detector list. None value = the tier declared NO `detectors`
    key ⟹ FULL participation (a deployment must opt OUT explicitly with [], never be
    silently darkened by an absent key). Returns None in single-tier mode."""
    if not tiers:
        return None
    return {t["id"]: t.get("detectors") for t in tiers}


def chunk_in_scope(chunk, det_map, detector):
    """Does `chunk` participate in `detector`? Yes when: single-tier mode; the chunk is
    unstamped; its tier has no `detectors` key (absent = allow all). Explicitly
    declared lists are exact: [] = none, [names] = only those."""
    if det_map is None:
        return True
    tier = chunk.get("tier")
    if tier is None:
        return True
    declared = det_map.get(tier)
    if declared is None:
        return True
    return detector in declared
