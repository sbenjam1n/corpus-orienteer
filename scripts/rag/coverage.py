#!/usr/bin/env python3
"""
Self-coverage audit: does the tool still understand the program's language?

The structured layers (entity extraction, supersession graph, type schema, ontology
seeds) are pattern/seed-driven. Their failure mode is SILENT: when the agent's prose
adopts new notation, a new object, or a new relation verb, the structured layers just
miss it — coverage degrades with no signal. This module makes that signal explicit.

It compares WHAT THE CORPUS CONTAINS against WHAT THE TOOL CAPTURES and reports the gap:

  uncaptured_tokens   recurring entity-like tokens NOT matched by any entity pattern
                      and not in the ontology seed   (candidate new notation/entities)
  uncaptured_relations  verbs adjacent to VR-N references that are NOT known relations
                        (candidate new supersession verbs)
  unseeded_objects    object-SHAPED, high-mention entities that resolve to no canonical
                      object   (the ontology seed is behind the corpus)
  alias_drift         a canonical object whose dominant RECENT surface form is not its
                      seed primary / not even in its alias list   (notation moved)

Deterministic, read-only, stdlib. The heuristics for "entity-like / relation-like" are
DOMAIN-AGNOSTIC; only the "what is already captured" baseline comes from this program's
patterns + seeds (imported from index_vrs.py + ontology.py). So this same module reports
coverage for ANY corpus once index_vrs/ontology are pointed at it.

Run after index_vrs.py + ontology.py (rebuild.sh wires it). Feeds the LLM reconciliation
pass (which reads the flagged VRs by meaning and proposes seed/config updates).
"""

import json, os, re, sys
from pathlib import Path
from collections import Counter, defaultdict

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("RAG_DATA_DIR", ROOT / "data" / "rag"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import index_vrs
import ontology

# --------------------------------------------------------------------------
# Domain-agnostic "is this technical notation?" heuristics
# --------------------------------------------------------------------------

# A token starting with a letter/Greek and continuing with word chars, sub/superscripts,
# ^ _ { } ~ ' - . A deliberately permissive shape for math-ish identifiers.
_TOKEN_RE = re.compile(r"[A-Za-zΑ-Ωα-ω][\w\^{}₀-₉⁰-⁹ₖ′~.\-]{1,38}", re.U)

_COMMON = set("""the and for that this with from have are was were will would which their
there been they when what your you our not but all can has had its into than then them
these those over under more most some such only also each both very much many any may””
section version status date analysis result results plan note table figure theorem lemma
proof case where here then thus hence cf via per see also let set map sum""".split())

_POWER_RE   = re.compile(r"[A-Za-z][²³⁰-⁹]+")   # x², y³  (single letter + SUPERscript)
_VERSION_RE = re.compile(r"v[\dxX]+[\d.xX\-]*")                     # v1.0, vX.X
_FRAGMENT_RE = re.compile(r"[a-z]\d+|vs[\-\d].*")                   # a1, a14, vs-64

def _is_entity_like(tok):
    """Domain-agnostic: does this look like a technical symbol/notation rather than prose?
    Subscripts are kept (C₂ is a group) but pure SUPERscript powers (x², y³), version
    strings (v1.0) and lowercase letter+digit fragments (a1) are excluded as noise."""
    if len(tok) < 2 or len(tok) > 40:
        return False
    low = tok.lower().strip("-.")
    if low in _COMMON:
        return False
    if tok.isalpha() and tok.islower():           # plain lowercase word
        return False
    if _POWER_RE.fullmatch(tok) or _VERSION_RE.fullmatch(tok) or _FRAGMENT_RE.fullmatch(tok):
        return False
    has_sub = any('₀' <= c <= '₉' or c == 'ₖ' for c in tok)
    has_greek = any('Α' <= c <= 'ω' for c in tok)
    has_sym = any(c in "^_~′{}" for c in tok)
    has_digit = any(c.isdigit() for c in tok)
    has_camel = bool(re.search(r"[a-z][A-Z]", tok))
    return has_sub or has_greek or has_sym or (has_digit and not tok.isdigit()) or has_camel

# Verb-ish token immediately governing a VR reference: "<verb> VR-N" or "VR-N <verb>".
_REL_BEFORE = re.compile(r"\b([A-Za-z]{3,20}(?:s|ed|es))\s+(?:the\s+)?(?:VR|AUDIT)-\d+")
_REL_AFTER  = re.compile(r"(?:VR|AUDIT)-\d+\s+(?:is\s+|was\s+)?([A-Za-z]{3,20}(?:s|ed))\b")

# Object-SHAPED tokens (generic families: twist-by-power, named field, Cremona-ish).
_OBJ_SHAPES = [
    re.compile(r"E\^\{?-?\d+\}?"),            # E^161, E^{-23}
    re.compile(r"K_[A-Za-z][\w]*"),           # K_A4, K_foo
    re.compile(r"\d{1,4}[a-z]\d{1,2}"),       # Cremona-ish label
]

# --------------------------------------------------------------------------

def _load(name, default):
    try:
        with open(DATA_DIR / name) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default

def _load_chunks():
    out = []
    p = DATA_DIR / "chunks.jsonl"
    if p.exists():
        with open(p) as f:
            for line in f:
                if line.strip():
                    out.append(json.loads(line))
    return out

def _known_relation_triggers():
    """Surface verbs the supersession patterns already recognize (corrects, refutes, ...)."""
    trig = set()
    for pat, rel in index_vrs.SUPERSESSION_PATTERNS:
        # strip the regex \b word-boundary so it doesn't glue a literal 'b' onto the verb
        # ("\\bcorrects" -> "bcorrects"); then pull the lexical verb tokens.
        for w in re.findall(r"[a-z]{3,}", pat.replace("\\b", " ")):
            if w not in ("by", "as", "of", "the", "in", "vr", "audit", "claim", "thesis",
                         "conclusion", "is", "period", "scripts", "from", "missing", "ed", "s"):
                trig.add(w)
    # add common inflections
    for w in list(trig):
        trig.update({w + "s", w + "ed", w.rstrip("e") + "ed", w + "es"})
    return trig

def build_coverage(top=40, min_vrs=5, recent_days=21):
    chunks = _load_chunks()
    registry = _load(name="entity_registry.json", default={})
    objects_seed, _, _, _ = ontology.load_seeds()
    exact, norm = ontology.build_alias_index(objects_seed)
    seed_alias_norms = set(norm.keys())
    known_rel = _known_relation_triggers()

    # ---- 1. uncaptured recurring entity-like tokens ----
    tok_vrs = defaultdict(set)        # token -> set(vr_id)
    for ch in chunks:
        if ch.get("status") in ("retracted", "deprecated"):
            continue
        vr = ch["vr_id"]
        for m in _TOKEN_RE.finditer(ch["content"]):
            t = m.group(0)
            if _is_entity_like(t):
                tok_vrs[t].add(vr)
    uncaptured = []
    for t, vrs in tok_vrs.items():
        if len(vrs) < min_vrs:
            continue
        if index_vrs.extract_entities(t):          # an entity pattern already matches it
            continue
        if t in registry:                          # already a registry entity
            continue
        if ontology.normalize_token(t) in seed_alias_norms:  # already a seed alias
            continue
        uncaptured.append({"token": t, "vrs": len(vrs),
                           "examples": sorted(vrs, key=lambda v: -int(re.search(r"\d+", v).group() if re.search(r"\d+", v) else 0))[:3]})
    uncaptured.sort(key=lambda x: -x["vrs"])

    # ---- 2. uncaptured relation verbs adjacent to VR refs ----
    rel_counts = Counter()
    rel_ex = {}
    for ch in chunks:
        c = ch["content"]
        for rx in (_REL_BEFORE, _REL_AFTER):
            for m in rx.finditer(c):
                v = m.group(1).lower()
                if v in known_rel or v in _COMMON:
                    continue
                rel_counts[v] += 1
                rel_ex.setdefault(v, ch["vr_id"])
    uncaptured_relations = [{"verb": v, "count": n, "example": rel_ex[v]}
                            for v, n in rel_counts.most_common(top) if n >= 3]

    # ---- 3. object-shaped, high-mention entities not in the ontology seed ----
    unseeded = []
    for ent, data in registry.items():
        if ent.startswith(("VR-", "AUDIT-")):
            continue
        mc = data.get("mention_count", 0)
        if mc < min_vrs:
            continue
        if ontology.resolve(ent, exact, norm):     # already a canonical object / alias
            continue
        shaped = any(rx.fullmatch(ent) for rx in _OBJ_SHAPES)
        typ = index_vrs.classify_type(ent)
        if shaped or typ in ("curve", "field"):
            unseeded.append({"entity": ent, "type": typ, "mentions": mc,
                             "object_shaped": shaped})
    unseeded.sort(key=lambda x: -x["mentions"])
    unseeded = unseeded[:top]

    # ---- 4. alias drift: canonical object whose dominant RECENT surface form isn't seeded
    dates = sorted({ch.get("date") for ch in chunks if ch.get("date")})
    cutoff = dates[-1] if dates else ""
    # crude "recent" = the lexicographically-largest ~recent_days slice of dates
    recent_cut = dates[max(0, len(dates) - recent_days)] if dates else ""
    alias_drift = []
    for obj in objects_seed:
        forms = Counter()
        aset = set([obj.get("primary", obj["id"])] + obj.get("aliases", []))
        for ch in chunks:
            if (ch.get("date") or "") < recent_cut:
                continue
            for a in aset:
                if len(a) >= 3 and a in ch["content"]:
                    forms[a] += 1
        if not forms:
            continue
        dominant, _ = forms.most_common(1)[0]
        sp = obj.get("primary", obj["id"])
        if dominant != sp:
            # Distinguish a COSMETIC primary-label mismatch (dominant folds to the same key —
            # it is already an alias that resolve()s correctly, e.g. stem_1 vs stem₁) from a
            # GENUINE new surface form that does NOT resolve (a real missing-alias gap). Only
            # the genuine kind needs a seed fix; flagging cosmetic ones as "drift" is the noise
            # that let an ASCII-only sweep ignore the real signal (F-j / AUDIT-217 / VR-1028).
            norm_only = ontology.normalize_token(dominant) == ontology.normalize_token(sp)
            # GENUINE iff the dominant surface form does NOT resolve to THIS object — i.e. a real
            # missing-alias gap. Keying genuine/cosmetic on normalize() alone (AUDIT-222 F-aliases)
            # mislabeled already-resolving non-folding aliases (e.g. '64a1' for E) as "GENUINE — add
            # as alias", producing ~13 standing false prompts. Since `dominant` is drawn from `aset`
            # (primary + existing aliases), it normally resolves to obj — so resolves=True is the
            # correct, honest verdict (no action). A future surface form that truly fails to resolve
            # (or resolves to a DIFFERENT object — an alias collision) is the only thing flagged.
            resolves = ontology.resolve(dominant, exact, norm) == obj["id"]
            alias_drift.append({"object": obj["id"], "seed_primary": sp,
                                "recent_dominant": dominant,
                                "normalization_variant": norm_only,
                                "resolves": resolves})

    report = {
        "generated": ontology._corpus_stamp(),
        "params": {"top": top, "min_vrs": min_vrs},
        "summary": {
            "uncaptured_tokens": len(uncaptured),
            "uncaptured_relations": len(uncaptured_relations),
            "unseeded_objects": len(unseeded),
            "alias_drift": len(alias_drift),
        },
        "uncaptured_tokens": uncaptured[:top],
        "uncaptured_relations": uncaptured_relations,
        "unseeded_objects": unseeded,
        "alias_drift": alias_drift,
    }
    return report

def run():
    rep = build_coverage()
    with open(DATA_DIR / "coverage_report.json", "w") as f:
        json.dump(rep, f, indent=2, default=str)
    s = rep["summary"]
    print(f"Coverage audit: {s['uncaptured_tokens']} uncaptured tokens, "
          f"{s['uncaptured_relations']} unknown relation verbs, "
          f"{s['unseeded_objects']} unseeded objects, {s['alias_drift']} alias-drift")
    return rep

if __name__ == "__main__":
    run()
