#!/usr/bin/env python3
"""
Ontology layer for the VR/AUDIT RAG corpus.

Turns hand-curated seeds + the index_vrs.py outputs into a Palantir-style object
layer (see docs/ontology_rag_assessment.md). Five pieces:

  1. Canonical objects — entity resolution over surface aliases (stem_2/stem2/stem2_,
     K₁ vs K̃₁, E^161/E^{161}/E161 all fold to one id). The aliasing problem the
     assessment flagged as the prerequisite for everything else.
  2. Object records with (curve,field)-BOUND properties — rank/|Sha|/digits live on
     a pair id "curve@field" (E^161 has rank 0 over Q AND rank 1 over M'); conductor/
     CM/root-number live on the curve; degree/Galois-group on the field. Each property
     carries value + VR provenance + epistemic stratum.
  3. Typed domain links — defined_over, has_galois_group, twist_of — supersession-aware
     (a link whose source VR is retracted/superseded is tagged, not silently asserted).
  4. Interfaces — shared contracts (Citable / Provenanced / Statused / Computed /
     Twistable / Extension) an object satisfies. Palantir "object type interfaces".
  5. Object monitors — declared watch conditions evaluated against the corpus now
     (the D=-23 escalation generalized; tc1 PENDING; "SETTLED needs an independent route").

Plus a seed<->corpus DRIFT report: the indexer is used to VALIDATE the seed (flag where
a seeded value disagrees with the corpus), not to extract values from prose.

Run AFTER index_vrs.py (rebuild.sh wires it). Stdlib only. Degrades gracefully if the
seeds are absent (writes empty outputs + a note).

Seeds (scripts/rag/, git-tracked):
  canonical_objects.json  {objects:[{id,type,title,primary,aliases,dropped,note}]}
  object_properties_seed.json  {properties:[{subject,prop,value,vr_id,stratum,source}]}
  domain_links_seed.json  {links:[{source,relation,target,vr_id}]}
  monitors_seed.json  {monitors:[{id,watch,severity,detector_type,detector_args,rationale}]}

Outputs (data/rag/, gitignored):
  objects.json, domain_links.json, object_drift.json, monitors.json
(concept-LOCATE is computed ON DEMAND by query.py — see locate_object — not precomputed here.)
"""

import json, os, re, sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[2]
# Standalone/porting overrides (Plans/rag_standalone_extraction_execution.md Stage 1):
# RAG_CORPUS_DIR / RAG_DATA_DIR / RAG_SEED_DIR redirect the corpus, outputs, and
# domain-config+seeds. Defaults preserve the in-repo deployment exactly.
DATA_DIR = Path(os.environ.get("RAG_DATA_DIR", ROOT / "data" / "rag"))
SEED_DIR = Path(os.environ.get("RAG_SEED_DIR", Path(__file__).resolve().parent))

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tiers as tiers_mod  # noqa: E402  (P6 M4: detector scoping by tier)
_DET_MAP = tiers_mod.detectors_for(tiers_mod.load())

# --------------------------------------------------------------------------
# Alias normalization (the canonicalizer core)
# --------------------------------------------------------------------------

_SUBSCRIPTS = {ord(c): str(i) for i, c in enumerate("₀₁₂₃₄₅₆₇₈₉")}
_SUBSCRIPTS[ord("ₖ")] = "k"

def normalize_token(s):
    """Fold a surface form to a comparison key: subscripts->digits, all tilde spellings
    (combining ̃, ascii ~, the word 'tilde') -> a single 'tilde' marker, drop braces/
    spaces/underscores. Tilde-PRESERVING so K_1 and K̃_1 do NOT collapse (a real
    different field), but stem_2 / stem2 / stem2_ / stem₂ and K~1 / K̃1 / Ktilde1 each
    converge to one key."""
    if s is None:
        return ""
    s = s.translate(_SUBSCRIPTS)
    s = s.replace("̃", "tilde").replace("~", "tilde")
    s = re.sub(r"(?:tilde)+", "tilde", s)
    for ch in "{}() _":
        s = s.replace(ch, "")
    return s

# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------

def _corpus_stamp():
    """Deterministic as-of stamp: reuse the indexer's corpus-derived stamp (max doc date +
    doc count) so rebuilding the same corpus twice is byte-identical — never wall clock."""
    return _load(DATA_DIR / "index_stats.json", {}).get("generated", "unknown")

def _load(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default

def load_seeds():
    return (
        _load(SEED_DIR / "canonical_objects.json", {"objects": []}).get("objects", []),
        _load(SEED_DIR / "object_properties_seed.json", {"properties": []}).get("properties", []),
        _load(SEED_DIR / "domain_links_seed.json", {"links": []}).get("links", []),
        _load(SEED_DIR / "monitors_seed.json", {"monitors": []}).get("monitors", []),
    )

def load_index_outputs():
    return (
        _load(DATA_DIR / "entity_registry.json", {}),
        _load(DATA_DIR / "supersession.json", {"edges": []}),
        _load(DATA_DIR / "claim_status.json", {}),
    )

def load_chunks():
    chunks = []
    p = DATA_DIR / "chunks.jsonl"
    if p.exists():
        with open(p) as f:
            for line in f:
                if line.strip():
                    chunks.append(json.loads(line))
    return chunks

# --------------------------------------------------------------------------
# Alias index + resolution
# --------------------------------------------------------------------------

def build_alias_index(objects):
    exact, norm = {}, {}
    for obj in objects:
        oid = obj["id"]
        for a in [obj["id"], obj.get("primary", "")] + obj.get("aliases", []):
            if not a:
                continue
            exact.setdefault(a, oid)
            norm.setdefault(normalize_token(a), oid)
    return exact, norm

def resolve(token, exact, norm):
    if token in exact:
        return exact[token]
    return norm.get(normalize_token(token))

def match_aliases(obj):
    """Aliases safe for corpus joins: drop 1-char forms (e.g. 'Q') that would match
    everything. The full alias list is still used for exact resolution."""
    seen, out = set(), []
    for a in [obj.get("primary", obj["id"])] + obj.get("aliases", []):
        if a and len(a) >= 3 or (a and any(ch.isdigit() for ch in a)):
            if a not in seen:
                seen.add(a); out.append(a)
    return out

# --------------------------------------------------------------------------
# Interfaces (shared contracts)
# --------------------------------------------------------------------------

INTERFACES = {
    "Citable":     "has a stable id and human-readable title",
    "Provenanced": "at least one fact carries a VR id",
    "Statused":    "at least one fact carries an epistemic stratum, or object is dropped",
    "Computed":    "has a numerically verified fact (bsd_digits, or stratum proved/verified/banked)",
    "Twistable":   "is an elliptic curve",
    "Extension":   "is a number field over Q",
}

_COMPUTED_STRATA = {"proved", "verified", "banked"}

def object_interfaces(obj, own_props, pair_props):
    facts = list(own_props.values()) + [p for pp in pair_props.values() for p in pp.values()]
    ifaces = ["Citable"]
    if any(f.get("vr_id") for f in facts):
        ifaces.append("Provenanced")
    if obj.get("dropped") or any(f.get("stratum") for f in facts):
        ifaces.append("Statused")
    if any(f.get("prop") == "bsd_digits" for f in facts) or \
       any((f.get("stratum") or "").lower() in _COMPUTED_STRATA for f in facts):
        ifaces.append("Computed")
    if obj["type"] == "curve":
        ifaces.append("Twistable")
    if obj["type"] == "field":
        ifaces.append("Extension")
    return ifaces

# --------------------------------------------------------------------------
# Drift detector: validate seed property values against the corpus
# --------------------------------------------------------------------------

# Drift-check only VOLATILE quantities (rank/|Sha|/digits/conductor) — the ones that
# actually evolve and get corrected. Immutable structural facts (degree, defining_poly,
# discriminant) are deliberately left no_detector: they don't drift, and a related field's
# degree co-occurring in tower prose (Q(√-23) degree 2 vs its degree-6 closure) is a
# false-positive trap, not a real signal.
_PROP_VALUE_RE = {
    "rank":        re.compile(r"rank\b[^.\n]{0,45}?[=:]\s*(-?\d+)"),
    "sha_order":   re.compile(r"(?:\|?[Ss]ha\|?|Ш)\b[^.\n]{0,30}?[=:≅]\s*\(?\s*(\d+)"),
    "conductor":   re.compile(r"conductor\b[^.\n]{0,20}?(\d{1,5})"),
    "bsd_digits":  re.compile(r"(\d{1,3})\s*(?:digit|dp\b|decimal)"),
}

def _apply_drift_config():
    """PORTABILITY: a ported domain drift-checks its OWN volatile quantities. domain_config's
    optional "drift_value_patterns" ({prop: regex-with-one-value-group}) REPLACES the embedded
    r14 defaults above. Mutates _PROP_VALUE_RE in place so importers (orient.py) see it."""
    cfg = _load(SEED_DIR / "domain_config.json", {})
    pats = cfg.get("drift_value_patterns")
    if pats:
        _PROP_VALUE_RE.clear()
        _PROP_VALUE_RE.update({k: re.compile(v) for k, v in pats.items()})

_apply_drift_config()

def _active(chunk):
    return chunk.get("status") not in ("retracted", "deprecated")

_WINDOW = 70  # chars around a value match within which subject aliases must co-occur

def _alias_rx(alias):
    """Word-boundary matcher for an alias so short forms don't substring-match longer ones
    (E^5 must NOT match E^5033; E^-23 must NOT match E^-23527)."""
    return re.compile(r"(?<![0-9A-Za-z])" + re.escape(alias) + r"(?![0-9A-Za-z])")

def _find_vals(cand_chunks, rx, group_rxs):
    """Find (value, vr) where rx matches in a candidate chunk AND every alias-group has a
    boundary-matched member within ±_WINDOW of the match. cand_chunks are ACTIVE chunks
    already known (precomputed in compute_drift) to contain every alias-group — so this only
    value-scans them; the per-chunk full-content alias filter is hoisted out (computed once
    per object, reused across that object's properties) to avoid the per-property rescan."""
    out = []
    for ch in cand_chunks:
        content = ch["content"]
        for m in rx.finditer(content):
            lo, hi = max(0, m.start() - _WINDOW), m.end() + _WINDOW
            win = content[lo:hi]
            if all(any(r.search(win) for r in grp) for grp in group_rxs):
                out.append((m.group(1), ch["vr_id"]))
    return out

def compute_drift(properties, objects_by_id, exact, norm, chunks):
    """Validate seeded values against the corpus — HIGH PRECISION (binding (curve,field)->
    value from prose is unreliable, so we refuse to cry wolf). For each seeded property we
    report confirmation coverage; we only FLAG genuine drift when the seed value never
    appears near the subject AND a SINGLE alternative value dominates across >=3 distinct
    VRs (the stale-seed signal). Aliases are word-boundary matched.

    PERF (behavior-identical): each object's alias-present ACTIVE-chunk set is precomputed ONCE
    (a fast literal-substring `in` gate, then the boundary regex) and reused across all that
    object's properties — instead of the old per-property full-corpus rescan (which was 2.8M
    re.search calls / ~58s). Drift stats and flags are unchanged; only the redundant scanning
    is removed."""
    rx_map = {o["id"]: [_alias_rx(a) for a in match_aliases(o)] for o in objects_by_id.values()}
    lit_map = {o["id"]: match_aliases(o) for o in objects_by_id.values()}
    active = [ch for ch in chunks if _active(ch)]
    # precompute, per object, the active chunks containing any of its aliases (boundary-matched).
    # The literal `in` gate is C-fast and rejects most chunks before any regex runs; the regex
    # confirm makes the result identical to the old inline `all(any(r.search(content)))` filter.
    present = {}
    for oid, grp in rx_map.items():
        lits = lit_map[oid]
        present[oid] = ([ch for ch in active
                         if any(a in ch["content"] for a in lits)
                         and any(r.search(ch["content"]) for r in grp)]
                        if grp else [])
    flags = []
    stats = {"confirmed": 0, "unconfirmed": 0, "flagged": 0, "unverified": 0, "no_detector": 0}
    for pr in properties:
        prop = pr["prop"]
        rx = _PROP_VALUE_RE.get(prop)
        sm = re.search(r"-?\d+", str(pr.get("value", "")))  # guard non-str/missing values
        if rx is None or sm is None:
            stats["no_detector"] += 1
            continue
        subj = pr["subject"]
        if "@" in subj:
            cid, fid = subj.split("@", 1)
            groups = [rx_map.get(cid, []), rx_map.get(fid, [])]
            fset = {id(ch) for ch in present.get(fid, [])}      # pair: chunks with BOTH aliases
            cand = [ch for ch in present.get(cid, []) if id(ch) in fset]
        else:
            groups = [rx_map.get(subj, [])]
            cand = present.get(subj, [])
        if not all(groups):
            stats["unverified"] += 1
            continue
        seed_val = sm.group(0)
        by_val = defaultdict(set)
        for v, vr in _find_vals(cand, rx, groups):
            by_val[v].add(vr)
        if not by_val:
            stats["unverified"] += 1
        elif seed_val in by_val:
            stats["confirmed"] += 1
        else:
            dominant = [(v, len(vrs)) for v, vrs in by_val.items() if len(vrs) >= 3]
            if len(dominant) == 1:
                stats["flagged"] += 1
                v, n = dominant[0]
                flags.append({
                    "subject": subj, "prop": prop, "seed_value": pr["value"],
                    "corpus_value": v, "corpus_vr_count": n,
                    "note": f"corpus asserts {prop}={v} near this subject in {n} VRs; seed says {seed_val}",
                })
            else:
                stats["unconfirmed"] += 1  # found other values but no single dominant — inconclusive
    return {"generated": _corpus_stamp(), "stats": stats, "flags": flags}

# --------------------------------------------------------------------------
# Monitors
# --------------------------------------------------------------------------

def _read_text(rel):
    p = ROOT / rel
    try:
        return p.read_text(encoding="utf-8")
    except (FileNotFoundError, UnicodeDecodeError):
        return None

def _rel(path):
    """Normalize an absolute-or-relative witness path to ROOT-relative for _read_text."""
    p = Path(path)
    if p.is_absolute():
        try:
            return str(p.relative_to(ROOT))
        except ValueError:
            return str(p)
    return str(p)

def evaluate_monitor(mon, claim_status, chunks):
    dt = mon.get("detector_type")
    args = mon.get("detector_args", {})
    state, evidence = "unknown", ""
    # Self-consumption guard: a chunk that NAMES this monitor is quoting/discussing its
    # definition, not asserting the watched predicate — the guard vocabulary itself must
    # never be a candidate (the "linter counts its own Referenced-By sections" bug class).
    # Applied to every corpus-scanning detector below; file scans get it as a window
    # exclusion since whole-file skipping would be too coarse for CLAUDE.md.
    _mid = mon.get("id", "")
    def _quotes_self(text):
        return bool(_mid) and _mid in text
    # doc-level: every chunk of a doc that names this monitor anywhere is excluded
    _self_docs = {ch.get("vr_id") for ch in chunks
                  if _mid and _mid in ch.get("content", "")} if _mid else set()
    def _doc_quotes_self(ch):
        return ch.get("vr_id") in _self_docs

    if dt == "text_present":
        # unmet if `pattern` present AND (no `also_absent`, or `also_absent` is absent).
        txt = _read_text(_rel(args.get("file", "")))
        if txt is None:
            state, evidence = "error", f"file not found: {args.get('file')}"
        else:
            present = args.get("pattern", "") in txt
            grounded = bool(args.get("also_absent")) and args["also_absent"] in txt
            state = "unmet" if (present and not grounded) else "met"
            g = f"; grounding '{args['also_absent']}' {'present' if grounded else 'ABSENT'}" if args.get("also_absent") else ""
            evidence = f"pattern {'present' if present else 'absent'}{g}"

    elif dt == "text_absent":
        # unmet if ANY required pattern is absent.
        txt = _read_text(_rel(args.get("file", "")))
        pats = args.get("patterns") or ([args["pattern"]] if args.get("pattern") else [])
        if txt is None:
            state, evidence = "error", f"file not found: {args.get('file')}"
        else:
            missing = [p for p in pats if p not in txt]
            state = "unmet" if missing else "met"
            evidence = f"{len(missing)}/{len(pats)} required patterns absent" + \
                       (f": {', '.join(missing[:3])}" if missing else "")

    elif dt == "json_field":
        # unmet_if: 'present' or 'absent' of `field` in the JSON at `file`.
        # A missing/unparseable witness is an ERROR (fail loud), NOT a satisfied condition —
        # otherwise deleting the witness of an unmet_if=present monitor masks the open gap.
        data = _load(ROOT / _rel(args.get("file", "")), None)
        field, uif = args.get("field", ""), args.get("unmet_if", "present")
        if data is None:
            state, evidence = "error", f"witness file absent/unparseable: {args.get('file')}"
        else:
            present = field in data
            state = "unmet" if (present if uif == "present" else not present) else "met"
            evidence = f"field '{field}' {'present' if present else 'absent'}"

    elif dt == "json_count":
        data = _load(ROOT / _rel(args.get("file", "")), None)
        field, mx = args.get("field", "findings"), args.get("max", 0)
        if data is None:
            state, evidence = "error", f"file not found: {args.get('file')}"
        else:
            # Dotted path support: "summary.DANGLING_REF" walks nested dicts so a monitor can
            # guard a per-CATEGORY provenance signal, not just a flat total. A plain field
            # (no dot) walks once → identical to the prior data.get(field, 0). NOTE: a missing
            # path resolves to 0 (always-MET) — guard against a silently-dead monitor with a
            # smoke-test that asserts the evidence carries the live value, not 0 (AUDIT-222 F2).
            cur = data
            for part in field.split("."):
                cur = cur.get(part, 0) if isinstance(cur, dict) else 0
            v = cur
            n = len(v) if isinstance(v, list) else v
            state = "unmet" if n > mx else "met"
            evidence = f"{field}={n} (plateau {mx})"

    elif dt == "claim_pending":
        ent = args.get("entity", "")
        hits = [vr for vr, cs in claim_status.items()
                for s in cs.get("strata", []) if ent.lower() in s.get("claim", "").lower()]
        state = "unmet" if hits else "met"
        evidence = f"{ent}: {len(hits)} strata mentions" + (f" (e.g. {hits[0]})" if hits else "")

    elif dt == "settled_independent_route":
        viol = []
        for ch in chunks:
            c = ch["content"]
            if _doc_quotes_self(ch):
                continue
            if re.search(r"\bSETTLED\b", c) and not re.search(r"independent\s+(route|verification|confirm|derivation|check)", c, re.I):
                viol.append(ch["vr_id"])
        viol = sorted(set(viol))
        state = "unmet" if viol else "met"
        evidence = f"{len(viol)} VR(s) declare SETTLED without an 'independent route' phrase" + \
                   (f" (e.g. {', '.join(viol[:5])})" if viol else "")

    elif dt == "forbidden_predicate":
        # CLAIM-level check — the thing the four token-level coverage detectors structurally cannot
        # do: flag chunks that ASSERT a predicate contradicting a seeded object fact, e.g.
        # "stem_k = the splitting field" / "Gal(stem_k/ℚ) = <wreath group>" (the VR-94/AUDIT-215
        # category-error mislabel; stem_k is the non-Galois root field, Ω_k is the splitting field).
        # Identity-targeted (not bare co-occurrence) + window-exclusion of negation/quote/correction/
        # closure/^{gal}/subfield/relative cues ⟹ high precision (validated 0 FP on the cleaned
        # corpus). CANDIDATE-emitting: lists regions to READ; NEVER an auto-verdict — a window
        # co-occurrence cannot separate assert-P from quote-P / negate-P / adjacent-correct-P.
        # Each candidate carries the matched SPAN + the seeded fact it contradicts (`contradicts`)
        # — an OWL-Explanation-style minimal justification, not a bare flag. Scope: the chunk corpus
        # (verification_ready/) AND the canonical defs via scan_files (they are not chunked).
        pats = [re.compile(p, re.I) for p in args.get("patterns", [])]
        excl = [re.compile(p, re.I) for p in args.get("exclude", [])]
        if _mid:
            excl.append(re.compile(re.escape(_mid)))   # self-consumption guard (file scans)
        win = args.get("window", 70)
        _dated = re.compile(r"\b20\d\d-\d\d-\d\d\b")   # §15 changelog / version-history rows QUOTE
                                                       # the old mislabel while recording its fix —
                                                       # they are dated table rows; live defs are not.
        contradicts = args.get("contradicts", "a seeded object fact")
        def _scan(text):
            """[(line, matched_span)] for forbidden-predicate assertions outside any excluded window
            and not on a dated changelog line. The span IS the justification — the exact asserted
            text that contradicts `contradicts`. One hit per line (regions to READ)."""
            lines = text.split("\n")
            hits, seen = [], set()
            for rx in pats:
                for m in rx.finditer(text):
                    w = text[max(0, m.start() - win): m.end() + win]
                    if any(e.search(w) for e in excl):
                        continue
                    ln = text.count("\n", 0, m.start()) + 1
                    if (1 <= ln <= len(lines) and _dated.search(lines[ln - 1])) or ln in seen:
                        continue
                    seen.add(ln)
                    hits.append((ln, re.sub(r"\s+", " ", m.group(0)).strip()[:60]))
            return sorted(hits)
        # (a) the verification_ready/ chunk corpus  (b) the canonical defs via scan_files (not chunked)
        cand = []
        for ch in chunks:
            if ch.get("status") in ("retracted", "deprecated", "corrected"):
                continue
            if _doc_quotes_self(ch):
                continue
            h = _scan(ch.get("content", ""))
            if h:
                cand.append(f"{ch.get('vr_id')} «{h[0][1]}»")   # vr + matched span (the justification)
        cand = sorted(set(cand))
        file_cand = []
        for rel in args.get("scan_files", []):
            txt = _read_text(_rel(rel))
            if txt is not None:
                file_cand += [f"{rel}:{ln} «{span}»" for ln, span in _scan(txt)]
        file_cand = sorted(set(file_cand))
        total = cand + file_cand
        state = "unmet" if total else "met"
        evidence = (f"{len(total)} candidate(s) ⟂ {contradicts} — READ to certify (candidate, NOT a verdict)"
                    + (f": {'; '.join(total[:6])}" if total else "; none found"))

    elif dt == "completeness_claim":
        # Flag chunks making a CORPUS-LEVEL completeness claim from a NARROW phrase set
        # (corpus-clean / grep-clean / mislabel-clean / fully clean) — the "grep-0 ⟹ corpus-clean"
        # overclaim the AUDIT-215→217 arc kept hitting (feedback_grep0_not_concept_clean). Narrow
        # set only: the broad "all X fixed" matches ~70 VRs (alarm fatigue). Window-excludes the
        # negation/critique context so the corrective VRs that QUOTE the phrase while warning
        # against it (e.g. "this is NOT a corpus-clean claim") are not flagged. CANDIDATE-emitting:
        # lists VRs whose completeness claim should be labelled at its grounding; LOW, not a verdict.
        pat = re.compile(args.get("pattern", r"\b(?:corpus[- ]clean|grep[- ]clean|mislabel[- ]clean|fully clean)\b"), re.I)
        excl = [re.compile(p, re.I) for p in args.get("exclude", [])]
        win = args.get("window", 60)
        cand = []
        for ch in chunks:
            if not _active(ch):
                continue
            c = ch.get("content", "")
            if _doc_quotes_self(ch):
                continue
            for m in pat.finditer(c):
                w = c[max(0, m.start() - win): m.end() + win]
                if not any(e.search(w) for e in excl):
                    cand.append(ch.get("vr_id"))
                    break
        cand = sorted(set(cand))
        state = "unmet" if cand else "met"
        evidence = (f"{len(cand)} VR(s) make a narrow completeness claim (corpus-clean/grep-clean/…) "
                    f"— label at grounding (concept-coverage, not a string-0); READ to certify"
                    + (f": {', '.join(cand[:6])}" if cand else "; none"))

    return {**{k: mon.get(k) for k in ("id", "watch", "severity", "rationale")},
            "detector_type": dt, "state": state, "evidence": evidence}

# --------------------------------------------------------------------------
# Concept-LOCATE index (grep-to-LOCATE / read-to-CERTIFY — VR-1027, AUDIT-217)
# --------------------------------------------------------------------------

def locate_object(obj, chunks):
    """On-demand concept-LOCATE for ONE object: the chunks mentioning any of its corpus-safe,
    word-boundary-matched aliases. A pure ENUMERATOR — returns the regions to READ, makes NO
    truth/predicate verdict, so it cannot misfire on a correct usage (e.g. 'K₁ = stem₁ (root
    field)' is returned for reading, never flagged). The substrate for the discipline that
    completeness over an object is an entity query, not a hand-tuned grep that keeps missing a
    surface form (ASCII vs 'stemₖ', a table cell, a second hit in an edited file).

    Run at QUERY time (query.py `locate`), NOT in build(): one object × the corpus is ~0.4s,
    so concept-LOCATE adds zero rebuild cost. (A precomputed all-objects index needs ~15-20s
    of stdlib-re scanning — not worth paying every rebuild for an occasional lookup.) `obj`
    is a seed/objects.json record with id/primary/aliases; the (?<!alnum)…(?!alnum) boundaries
    keep a short alias from matching inside a longer token (E^5 ⊄ E^5033)."""
    al = match_aliases(obj)
    if not al:
        return []
    pat = "|".join(re.escape(a) for a in sorted(al, key=len, reverse=True))
    rx = re.compile(r"(?<![0-9A-Za-z])(" + pat + r")(?![0-9A-Za-z])")
    hits = []
    for ch in chunks:
        found = rx.findall(ch.get("content", ""))
        if found:
            hits.append({"chunk_id": ch.get("chunk_id"), "vr_id": ch.get("vr_id"),
                         "section": (ch.get("section") or "")[:80],
                         "status": ch.get("status"), "matched_aliases": sorted(set(found))})
    return hits

# --------------------------------------------------------------------------
# Build
# --------------------------------------------------------------------------

_SEV_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "INFO": 3}

def build():
    DATA_DIR.mkdir(parents=True, exist_ok=True)   # redirected RAG_DATA_DIR may not exist yet
    objects, properties, links_seed, monitors_seed = load_seeds()
    registry, supersession, claim_status = load_index_outputs()

    if not objects:
        for name in ("objects.json", "domain_links.json", "object_drift.json", "monitors.json"):
            with open(DATA_DIR / name, "w") as f:
                json.dump({"generated": _corpus_stamp(),
                           "note": "no canonical_objects.json seed present; ontology layer empty"}, f, indent=2)
        print("ontology: no seed present — wrote empty outputs.")
        return {"objects": 0, "links": 0, "monitors": 0, "drift_flags": 0}

    objects_by_id = {o["id"]: o for o in objects}
    exact, norm = build_alias_index(objects)

    # group seed properties by subject
    own_props = defaultdict(dict)   # object id -> {prop: record}
    pair_props = defaultdict(lambda: defaultdict(dict))  # curve id -> {field id -> {prop: record}}
    pairs = {}                       # "curve@field" -> {curve, field, properties}
    for pr in properties:
        rec = {k: pr.get(k) for k in ("prop", "value", "vr_id", "stratum", "source")}
        subj = pr["subject"]
        if "@" in subj:
            cid, fid = subj.split("@", 1)
            pair_props[cid][fid][pr["prop"]] = rec
            pp = pairs.setdefault(subj, {"curve": cid, "field": fid, "properties": {}})
            pp["properties"][pr["prop"]] = rec
        else:
            own_props[subj][pr["prop"]] = rec

    # supersession-aware: which VRs are LOSERS (got invalidated)? The edge direction
    # depends on the relation. Verb relations (X corrects Y) put the loser at TARGET;
    # self-applied bracket tags ([CORRECTED by W] in D's own metadata) put the loser at
    # SOURCE. Reading e["target"] uniformly (the old bug) tagged WINNERS as superseded
    # and missed source-side losers. Traced against index_vrs.extract_supersession.
    TARGET_IS_LOSER = {"corrects", "refutes", "retracts", "supersedes", "downgrades", "correction_of"}
    SOURCE_IS_LOSER = {"corrected_by", "corrected_by_audit", "superseded_by", "retracted",
                       "deprecated", "affected_by"}
    superseded_vrs = set()
    for e in supersession.get("edges", []):
        if e["relation"] in TARGET_IS_LOSER:
            superseded_vrs.add(e["target"])
        elif e["relation"] in SOURCE_IS_LOSER:
            superseded_vrs.add(e["source"])

    # resolve + tag links
    links = []
    for lk in links_seed:
        s = resolve(lk["source"], exact, norm) or lk["source"]
        t = resolve(lk["target"], exact, norm) or lk["target"]
        rec = {"source": s, "relation": lk["relation"], "target": t, "vr_id": lk.get("vr_id")}
        if lk.get("vr_id") in superseded_vrs:
            rec["superseded"] = True
        links.append(rec)
    links_out = defaultdict(list); links_in = defaultdict(list)
    for lk in links:
        links_out[lk["source"]].append(lk)
        links_in[lk["target"]].append(lk)

    # mention stats from entity_registry (exact alias-key join)
    def mention_stats(obj):
        total, first, last, contrib = 0, None, None, []
        for a in match_aliases(obj):
            if a in registry:
                d = registry[a]
                total += d.get("mention_count", 0)
                contrib.append({"alias": a, "mentions": d.get("mention_count", 0)})
                fs, ls = d.get("first_seen"), d.get("last_seen")
                if fs and (first is None or fs < first): first = fs
                if ls and (last is None or ls > last): last = ls
        contrib.sort(key=lambda x: -x["mentions"])
        return {"total_mentions": total, "first_seen": first, "last_seen": last, "by_alias": contrib}

    # claims about an object (from claim_status strata; match-alias substring).
    # Junk filter (per assessment §6 proposal-4 refinement): drop markdown table rows,
    # headers, and questions — these are the source of the false-PROVED fragments.
    _NEG_CUE = re.compile(r"\bnot a proof\b|\bnot proved\b|\bno verdict\b|\bconditional\b|\bfails?\b|\bwrong\b", re.I)
    def _is_junk_claim(txt, stratum):
        t = txt.strip()
        if (not t or len(t) < 25 or t.startswith("#") or t.startswith("|")
                or t.startswith("---") or "|" in t[:40] or t.rstrip().endswith("?")):
            return True
        # mis-stratified: text carries a negation cue but is tagged proved/verified
        if stratum in ("proved", "verified") and _NEG_CUE.search(t):
            return True
        return False
    def claims_for(obj):
        out, seen = [], set()
        ma = match_aliases(obj)
        for vr, cs in claim_status.items():
            for s in cs.get("strata", []):
                txt = s.get("claim", "")
                if _is_junk_claim(txt, s.get("stratum")) or not any(a in txt for a in ma):
                    continue
                key = (vr, txt[:60])
                if key in seen:
                    continue
                seen.add(key)
                out.append({"vr_id": vr, "stratum": s.get("stratum"), "claim": txt[:160]})
        rank = {"proved": 0, "verified": 1, "predicted": 2, "open": 3, "retracted": 4}
        out.sort(key=lambda c: rank.get(c["stratum"], 5))
        return out[:12]

    out_objects = {}
    for oid, obj in objects_by_id.items():
        op = dict(own_props.get(oid, {}))
        pp = {fid: dict(props) for fid, props in pair_props.get(oid, {}).items()}
        out_objects[oid] = {
            "id": oid, "type": obj["type"], "title": obj.get("title", oid),
            "primary": obj.get("primary"), "aliases": obj.get("aliases", []),
            "dropped": bool(obj.get("dropped")), "note": obj.get("note"),
            "interfaces": object_interfaces(obj, op, pp),
            "properties": op,
            "pairs": pp,                       # for curves: field id -> {prop: rec}
            "links_out": links_out.get(oid, []),
            "links_in": links_in.get(oid, []),
            "mentions": mention_stats(obj),
            "claims": claims_for(obj),
        }

    chunks = load_chunks()
    # P6 M4: detectors run only where a chunk's tier declares them. Single-tier
    # mode (_DET_MAP None) and unstamped chunks are unaffected — full participation.
    drift_chunks = [ch for ch in chunks
                    if tiers_mod.chunk_in_scope(ch, _DET_MAP, "drift")]
    monitor_chunks = [ch for ch in chunks
                      if tiers_mod.chunk_in_scope(ch, _DET_MAP, "monitors")]
    drift = compute_drift(properties, objects_by_id, exact, norm, drift_chunks)
    monitors = [evaluate_monitor(m, claim_status, monitor_chunks) for m in monitors_seed]
    monitors.sort(key=lambda m: (_SEV_ORDER.get(m.get("severity"), 9), m.get("state") != "unmet"))

    with open(DATA_DIR / "objects.json", "w") as f:
        json.dump({"generated": _corpus_stamp(),
                   "interfaces": INTERFACES,
                   "objects": out_objects, "pairs": pairs}, f, indent=2, default=str)
    with open(DATA_DIR / "domain_links.json", "w") as f:
        json.dump({"generated": _corpus_stamp(), "links": links}, f, indent=2)
    with open(DATA_DIR / "object_drift.json", "w") as f:
        json.dump(drift, f, indent=2)
    with open(DATA_DIR / "monitors.json", "w") as f:
        json.dump({"generated": _corpus_stamp(), "monitors": monitors}, f, indent=2)

    unmet = sum(1 for m in monitors if m["state"] == "unmet")
    print(f"Ontology: {len(out_objects)} objects, {len(pairs)} (curve,field) pairs, "
          f"{len(links)} links, {len(monitors)} monitors ({unmet} unmet), "
          f"{len(drift['flags'])} drift flags")
    return {"objects": len(out_objects), "pairs": len(pairs), "links": len(links),
            "monitors": len(monitors), "drift_flags": len(drift["flags"])}

if __name__ == "__main__":
    build()
