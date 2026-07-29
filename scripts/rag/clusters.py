#!/usr/bin/env python3
"""
Deterministic cluster harvest + corpus sweep for a scope (steps 2-3 of orient-scope).

Replaces the free-association half of a "concept clusters, then harder search" pass
(the ZILBER_PINK_RESEARCH_INDEX §1-§2 workflow) with derived-or-pinned vocabulary and
a mechanical sweep. Two halves, split by where the vocabulary lives:

  INTERNAL (derived, zero-LLM): concepts.json entries whose VR trail intersects the
  scope's own + cited doc ids, unioned with the scope's touched canonical objects
  (orient.py's detector). Corpus-grounded by construction.

  EXTERNAL (seeded, pinned): cluster_seed.json — vocabulary a corpus sweep cannot
  derive (0-hit neighborhoods). LLM-curated ONCE (the canonical_objects.json
  gather+validate precedent), committed, provenance-tagged CORPUS|MEMORY. Generation
  is a curation event; every re-run is deterministic against the pinned seed.

The sweep then runs every head/term through (a) a literal scan over the corpus dirs
— case/dash/accent-folded, word-bounded; the exact-count upgrade of the ZP §2 "~68"
hand table — and (b) TF-IDF adjacency via query.py's stdlib tier (retracted
down-weighted; PINNED for claims — chroma is exploratory augmentation, never the
recorded tier). Literal-vs-adjacency is reported split, never conflated: 0 literal
hits ≠ absent (read the ADJACENT-ONLY rows); adjacency ≠ presence.

Usage:
  python3 scripts/rag/clusters.py <scope docs/ids...> --out <slug>
      [--seed-scope <name>] [--dirs d1 d2 ...] [--top N (derived-concept sweep cap, 30)]

Sweep-dir default is DOMAIN vocabulary (the porting surface): domain_config.json
"sweep_dirs" if declared (r14 declares docs/verification_ready/papers/Plans), else the
corpus dir itself (RAG_CORPUS_DIR). --dirs overrides both.

Outputs (data/rag/, gitignored, derived — never re-ingested):
  clusters_<slug>.json   the pinned sweep plan (derived + seed-selected, provenance-tagged)
  sweep_<slug>.md        the literal/adjacency table — an ENUMERATOR, not a verdict
                         (grep-to-LOCATE, read-to-CERTIFY; a detector's zero is not
                         a certification — VR-1027 discipline)

Deterministic given (corpus files, data/rag build, seed): no wall clock — stamped with
the index build id. Stdlib only. Run AFTER rebuild.sh (needs chunks.jsonl + concepts.json
+ objects.json + file_meta.json).
"""

import json, os, re, sys, unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("RAG_DATA_DIR", ROOT / "data" / "rag"))
SEED_DIR = Path(os.environ.get("RAG_SEED_DIR", Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from query import load_chunks, build_tfidf, search_tfidf  # noqa: E402 — import-safe (main-guarded)
from orient import resolve_inputs, cited_docs, touched_objects, _stamp  # noqa: E402
from ontology import match_aliases  # noqa: E402

SWEEP_OBJECT_CAP = 20   # sweep the top-N touched objects; the rest stay listed in the JSON

def _default_dirs():
    """Sweep-dir default comes from the porting surface, never a hardcode: domain_config
    "sweep_dirs" wins; fallback is the corpus dir itself (a ported domain sweeps its own
    corpus with zero config)."""
    try:
        d = json.loads((SEED_DIR / "domain_config.json").read_text()).get("sweep_dirs")
        if d:
            return list(d)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return [os.environ.get("RAG_CORPUS_DIR", str(ROOT / "verification_ready"))]

# --------------------------------------------------------------------------
# Normalization — the fold that made the ZP hand-sweep need two spellings
# (en-dash "Zilber–Pink" vs hyphen; "André"/"Wüstholz" accents; case)
# --------------------------------------------------------------------------

_DASHES = {ord(c): "-" for c in "‐‑‒–—―−"}
# Stroke letters have NO NFKD decomposition (Ł is not L+combining) — fold the ones the
# corpus actually uses ("Łoś engine", ø in refs) so seed terms can stay ASCII.
_STROKES = {ord("ł"): "l", ord("Ł"): "L", ord("ø"): "o", ord("Ø"): "O", ord("đ"): "d", ord("Đ"): "D"}

def fold(s):
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.translate(_STROKES).translate(_DASHES).casefold()
    return re.sub(r"\s+", " ", s)

def term_rx(term):
    # Word-bounded so "abc" does not count "abcd..." — stricter than the raw grep the
    # hand sweep used; counts may sit below the old "~N" figures, and that is the point.
    return re.compile(r"(?<!\w)" + re.escape(fold(term)) + r"(?!\w)")

# --------------------------------------------------------------------------
# Corpus loading for the literal scan (read once, scan per term)
# --------------------------------------------------------------------------

def load_corpus_texts(dirs):
    """[(relpath, folded_text)] for every non-binary file under the given dirs, sorted."""
    out = []
    for d in dirs:
        base = Path(d) if Path(d).is_absolute() else ROOT / d   # dispatcher may export absolute
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*")):
            if not p.is_file() or p.stat().st_size > 5_000_000:
                continue
            try:
                head = p.open("rb").read(8192)
            except OSError:
                continue
            if b"\x00" in head:
                continue   # binary
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            rel = str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)
            out.append((rel, fold(text)))
    return out

def literal_scan(term, corpus_texts):
    """(files_hit, total_occurrences, top3 [(relpath, n)]) — deterministic."""
    rx = term_rx(term)
    per = []
    for rel, text in corpus_texts:
        n = len(rx.findall(text))
        if n:
            per.append((rel, n))
    per.sort(key=lambda x: (-x[1], x[0]))
    return len(per), sum(n for _r, n in per), per[:3]

def tfidf_top(term, chunks, tfs, idfs, k=3):
    """Top-k DISTINCT docs (vr_id, best score>0) — query.py's pinned stdlib tier.
    Dedup matters: one doc's chunks otherwise fill all k slots."""
    hits, seen = [], set()
    for score, i in search_tfidf(term, chunks, tfs, idfs, top_k=5 * k):
        vid = chunks[i]["vr_id"]
        if score > 0 and vid not in seen:
            seen.add(vid)
            hits.append((vid, round(score, 4)))
        if len(hits) == k:
            break
    return hits

# --------------------------------------------------------------------------
# Harvest
# --------------------------------------------------------------------------

def derive_concepts(scope_ids, concepts):
    """concepts.json entries whose VR trail intersects the scope, ranked
    (overlap desc, propagation desc, term). Zero-LLM."""
    out = []
    for c in concepts:
        ov = len(scope_ids & set(c.get("vrs", [])))
        if ov:
            out.append({"term": c["term"], "overlap": ov,
                        "propagation": c.get("propagation_count", 0),
                        "introduced_in": c.get("introduced_in", "?")})
    out.sort(key=lambda c: (-c["overlap"], -c["propagation"], c["term"]))
    return out

def select_seed(slug, seed_scope):
    try:
        seed = json.loads((SEED_DIR / "cluster_seed.json").read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    want = {seed_scope or slug, "global"}
    return [c for c in seed.get("clusters", []) if c.get("scope") in want]

# --------------------------------------------------------------------------
# Instrument slice — scope-filtered drift/coverage (the 4th dream attachment)
# --------------------------------------------------------------------------

def instrument_slice(touched_ids, scope_ids, scope_folded, drift, coverage):
    """Scope-filter the program's self-model doubt: drift flags on touched objects,
    coverage candidates visible from the scope. Pure function (testable); returns
    {section: rows}. Where the program's instruments disagree with its corpus is
    prime dream terrain — but only the SCOPE's slice, never the whole-program
    tables (center-of-mass anchoring; see the dreams README)."""
    out = {}
    out["drift_flags"] = [f for f in drift.get("flags", [])
                          if f.get("object") in touched_ids]
    out["alias_drift"] = [a for a in coverage.get("alias_drift", [])
                          if a.get("object") in touched_ids]
    out["uncaptured_tokens"] = [t for t in coverage.get("uncaptured_tokens", [])
                                if set(t.get("examples", [])) & scope_ids
                                or term_rx(t.get("token", "\x00")).search(scope_folded)]
    out["unseeded_objects"] = [o for o in coverage.get("unseeded_objects", [])
                               if o.get("entity") and fold(o["entity"]) in scope_folded]
    return out

def write_instrument(slug, sl, drift, coverage):
    L = [f"# Instrument slice — {slug}", "",
         f"Scope-filtered drift/coverage (whole-program tables deliberately excluded). "
         f"Index build: {_stamp()} · whole-corpus baseline: drift flags "
         f"{len(drift.get('flags', []))}, uncaptured tokens "
         f"{len(coverage.get('uncaptured_tokens', []))}, unseeded objects "
         f"{len(coverage.get('unseeded_objects', []))}, alias drift "
         f"{len(coverage.get('alias_drift', []))}.",
         "Discipline: rows are candidates to READ, never verdicts; an empty section "
         "means the DETECTOR found nothing in scope — a detector's zero is not a "
         "certification.", ""]
    def sec(title, rows, fmt):
        L.append(f"## {title} ({len(rows)})")
        L.extend(fmt(r) for r in rows) if rows else L.append("_0 in scope_")
        L.append("")
    sec("Seed↔corpus drift flags on touched objects", sl["drift_flags"],
        lambda f: f"- `{json.dumps(f, ensure_ascii=False)}`")
    sec("Alias drift on touched objects", sl["alias_drift"],
        lambda a: f"- **{a.get('object')}**: seed primary `{a.get('seed_primary')}` vs "
                  f"recent dominant `{a.get('recent_dominant')}` "
                  f"(resolves: {a.get('resolves')})")
    sec("Uncaptured tokens visible from scope (candidate new notation)",
        sl["uncaptured_tokens"],
        lambda t: f"- `{t.get('token')}` — {t.get('vrs')} VRs, e.g. "
                  f"{', '.join(t.get('examples', [])[:3])}")
    sec("Unseeded object-shaped entities in scope text", sl["unseeded_objects"],
        lambda o: f"- `{o.get('entity')}` [{o.get('type')}] — "
                  f"{o.get('mentions')} mentions corpus-wide")
    out = DATA_DIR / f"instrument_{slug}.md"
    out.write_text("\n".join(L) + "\n")
    return out

# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------

def _row(label, tag, files, occ, top, adj):
    lit = f"{files} files / {occ}" if files else "0"
    a = "; ".join(f"{v} ({s})" for v, s in adj) or "-"
    where = "; ".join(f"{r}×{n}" for r, n in top) or "-"
    mark = "" if files else ("  **ADJACENT-ONLY**" if adj else "  **ABSENT**")
    return f"| {label} | {tag} | {lit} | {where} | {a}{mark} |"

def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    def _opt(name, n=1, default=None):
        if name in argv:
            i = argv.index(name)
            vals = argv[i + 1:i + 1 + n]
            del argv[i:i + 1 + n]
            return vals if n > 1 else (vals[0] if vals else default)
        return default
    slug = _opt("--out")
    seed_scope = _opt("--seed-scope")
    top_n = int(_opt("--top", default="30"))
    dirs = _default_dirs()
    if "--dirs" in argv:
        i = argv.index("--dirs")
        dirs = [a for a in argv[i + 1:] if not a.startswith("--")]
        argv = argv[:i]
    if not argv or not slug:
        print("Usage: clusters.py <scope docs/ids...> --out <slug> "
              "[--seed-scope name] [--dirs d1 d2 ...] [--top N]")
        return 1
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", slug)[:60]
    if not (DATA_DIR / "concepts.json").exists():
        print("data/rag not built — run: bash scripts/rag/rebuild.sh")
        return 1

    fm = json.loads((DATA_DIR / "file_meta.json").read_text())
    fm_by_id = {m["id"]: m for m in fm if m.get("id")}
    inputs, self_ids, errors = resolve_inputs(argv, fm_by_id)
    for e in errors:
        print(f"error: {e}")
    if not inputs:
        return 1
    scope_ids = set(self_ids) | set(cited_docs(inputs, self_ids))

    concepts = json.loads((DATA_DIR / "concepts.json").read_text())
    objdata = json.loads((DATA_DIR / "objects.json").read_text())
    derived = derive_concepts(scope_ids, concepts)
    touched = touched_objects(inputs, objdata.get("objects", {}))
    seed_clusters = select_seed(slug, seed_scope)

    plan = {
        "slug": slug, "scope_args": argv, "index_build": _stamp(),
        "scope_ids": sorted(scope_ids), "dirs": dirs, "sweep_top": top_n,
        "derived_concepts": derived,
        "derived_objects": [{"id": o["id"], "mentions": n} for o, n in touched],
        "seed_clusters": seed_clusters,
    }
    (DATA_DIR / f"clusters_{slug}.json").write_text(
        json.dumps(plan, indent=1, ensure_ascii=False) + "\n")

    # ---- sweep ----
    corpus_texts = load_corpus_texts(dirs)
    chunks = load_chunks()
    tfs, idfs = build_tfidf(chunks)

    L = [f"# Cluster sweep — {slug}",
         "",
         f"Scope: {', '.join(argv)} · scope ids: {len(scope_ids)} · index build: {_stamp()}",
         f"Literal scan: {len(corpus_texts)} files under {'/'.join(dirs)} "
         "(case/dash/accent-folded, word-bounded). Adjacency: TF-IDF stdlib tier, "
         "retracted down-weighted (PINNED for claims; chroma = exploration only).",
         "Deterministic given (corpus, index build, seed). ENUMERATOR, not verdict: "
         "grep-to-LOCATE, read-to-CERTIFY; 0 literal ≠ absent — read ADJACENT-ONLY rows; "
         "adjacency ≠ presence.",
         "",
         "| term | source | literal (files/occ) | top files | tfidf adjacency |",
         "|---|---|---|---|---|"]

    def sweep_term(label, tag):
        files, occ, top = literal_scan(label, corpus_texts)
        adj = tfidf_top(label, chunks, tfs, idfs)
        L.append(_row(label, tag, files, occ, top, adj))

    for cl in seed_clusters:
        L.append(f"| **{cl['head']}** | SEED·{cl.get('provenance', '?')} "
                 f"(curated {cl.get('curated', '?')}) | | | |")
        for t in cl.get("terms", []):
            sweep_term(t, "seed")
    for c in derived[:top_n]:
        sweep_term(c["term"], f"derived·concept (ov={c['overlap']})")
    if len(derived) > top_n:
        L.append(f"| _…{len(derived) - top_n} more derived concepts NOT swept "
                 f"(--top {top_n}); full list in clusters_{slug}.json_ | | | | |")
    for o, n in touched[:SWEEP_OBJECT_CAP]:
        files = occ = 0
        agg = {}
        for a in sorted(set(match_aliases(o))):
            f_, o_, tp = literal_scan(a, corpus_texts)
            occ += o_
            for r, k in tp:
                agg[r] = agg.get(r, 0) + k
        top = sorted(agg.items(), key=lambda x: (-x[1], x[0]))[:3]
        adj = tfidf_top(o.get("primary", o["id"]), chunks, tfs, idfs)
        L.append(_row(o["id"], f"derived·object (scope×{n})", len(agg), occ, top, adj))
    if len(touched) > SWEEP_OBJECT_CAP:
        L.append(f"| _…{len(touched) - SWEEP_OBJECT_CAP} more touched objects NOT swept; "
                 f"full list in clusters_{slug}.json_ | | | | |")

    out = DATA_DIR / f"sweep_{slug}.md"
    out.write_text("\n".join(L) + "\n")
    print("\n".join(L))

    # ---- instrument slice (4th dream attachment; degrade gracefully if absent) ----
    inst_note = ""
    try:
        drift = json.loads((DATA_DIR / "object_drift.json").read_text())
        coverage = json.loads((DATA_DIR / "coverage_report.json").read_text())
        touched_ids = {o["id"] for o, _n in touched}
        scope_folded = fold("\n".join(t for _l, t in inputs))
        sl = instrument_slice(touched_ids, scope_ids, scope_folded, drift, coverage)
        ipath = write_instrument(slug, sl, drift, coverage)
        inst_note = f" + {ipath.name}"
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[clusters: instrument slice skipped — {e.__class__.__name__}]")

    print(f"\n[clusters: wrote {out.relative_to(ROOT)} + clusters_{slug}.json{inst_note}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
