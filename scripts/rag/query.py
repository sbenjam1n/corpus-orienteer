#!/usr/bin/env python3
"""
RAG query interface for the VR/AUDIT corpus.

Three modes:
  python3 scripts/rag/query.py search "epsilon convergence k=3"
  python3 scripts/rag/query.py object "eps_k3"
  python3 scripts/rag/query.py related VR-534

Uses TF-IDF for text search (no external dependencies).
Entity registry and supersession graph are pre-built by index_vrs.py.
"""

import json, os, re, sys, math
from pathlib import Path
from collections import defaultdict, Counter

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("RAG_DATA_DIR", ROOT / "data" / "rag"))

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_chunks():
    chunks = []
    with open(DATA_DIR / "chunks.jsonl") as f:
        for line in f:
            if line.strip():
                chunks.append(json.loads(line))
    return chunks

def load_registry():
    with open(DATA_DIR / "entity_registry.json") as f:
        return json.load(f)

def load_supersession():
    with open(DATA_DIR / "supersession.json") as f:
        return json.load(f)

def load_meta():
    with open(DATA_DIR / "file_meta.json") as f:
        return json.load(f)

def load_json(name):
    with open(DATA_DIR / name) as f:
        return json.load(f)

def resolve_object(token, objdata):
    """Map a surface token to a canonical object id (exact alias, then normalized)."""
    objs = objdata.get("objects", {})
    if token in objs:
        return token
    for oid, o in objs.items():
        if token == o.get("primary") or token in o.get("aliases", []):
            return oid
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from ontology import normalize_token
    except Exception:
        return None
    ntok = normalize_token(token)
    for oid, o in objs.items():
        cands = [oid, o.get("primary", "")] + o.get("aliases", [])
        if any(normalize_token(c) == ntok for c in cands if c):
            return oid
    return None

# ---------------------------------------------------------------------------
# TF-IDF search (stdlib only)
# ---------------------------------------------------------------------------

def tokenize(text):
    return re.findall(r"[a-z0-9_]+(?:[-/][a-z0-9_]+)*", text.lower())

def build_tfidf(chunks):
    N = len(chunks)
    df = Counter()
    tfs = []
    for chunk in chunks:
        tokens = tokenize(chunk["content"])
        tf = Counter(tokens)
        tfs.append(tf)
        for token in set(tokens):
            df[token] += 1
    idfs = {t: math.log(N / (1 + c)) for t, c in df.items()}
    return tfs, idfs

STOPWORDS = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
             "have", "has", "had", "do", "does", "did", "will", "would",
             "could", "should", "may", "might", "shall", "can", "for",
             "and", "but", "or", "not", "no", "if", "then", "so", "as",
             "at", "by", "in", "on", "to", "of", "with", "from", "up",
             "out", "that", "this", "it", "its", "all", "each", "any",
             "s1", "s2", "s3", "s4", "s5", "s6", "s7", "version", "history",
             "plan", "analysis", "results", "significance", "verification",
             "section", "date", "status", "v1", "v2", "v3", "v4"}

import tiers as _tiers_mod  # noqa: E402  (P6 M5: authority weighting)
_TIER_AUTH = {t["id"]: t.get("authority")
              for t in (_tiers_mod.load() or [])}

def search_tfidf(query, chunks, tfs, idfs, top_k=15):
    query_tokens = [t for t in tokenize(query) if t not in STOPWORDS]
    scores = []
    for i, chunk in enumerate(chunks):
        score = 0.0
        tf = tfs[i]
        doc_len = sum(tf.values()) or 1
        matched_tokens = 0
        for qt in query_tokens:
            if qt in tf:
                tfidf = (tf[qt] / doc_len) * idfs.get(qt, 0)
                score += tfidf
                matched_tokens += 1
        if matched_tokens > 1:
            score *= (1 + 0.2 * matched_tokens)
        # P6 M5: tier authority weighting (single-tier/unstamped chunks unaffected).
        # authority 3 (receipts) → ×1.0; 2 (threads) → ×0.8; 1 → ×0.6; 0 → ×0.4.
        _tier = chunk.get("tier")
        if _tier is not None and _TIER_AUTH.get(_tier) is not None:
            score *= 0.4 + 0.2 * min(3, _TIER_AUTH[_tier])
        if chunk["status"] == "retracted":
            score *= 0.3
        elif chunk["status"] == "deprecated":
            score *= 0.5
        scores.append((score, i))
    scores.sort(reverse=True)
    return scores[:top_k]

# ---------------------------------------------------------------------------
# Object lookup
# ---------------------------------------------------------------------------

def lookup_object(name, registry):
    if name in registry:
        return {name: registry[name]}
    matches = {k: v for k, v in registry.items()
                if name.lower() in k.lower()}
    return matches

# ---------------------------------------------------------------------------
# Related VRs
# ---------------------------------------------------------------------------

def find_related(vr_id, chunks, registry, supersession):
    vr_entities = set()
    for chunk in chunks:
        if chunk["vr_id"] == vr_id:
            vr_entities.update(chunk["entities"])

    vr_entities -= {vr_id}

    vr_scores = Counter()
    for chunk in chunks:
        if chunk["vr_id"] == vr_id:
            continue
        overlap = vr_entities & set(chunk["entities"])
        if overlap:
            vr_scores[chunk["vr_id"]] += len(overlap)

    for edge in supersession.get("edges", []):
        if edge["source"] == vr_id:
            vr_scores[edge["target"]] += 5
        if edge["target"] == vr_id:
            vr_scores[edge["source"]] += 5

    return vr_scores.most_common(20)

# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def format_chunk(chunk, score=None):
    parts = [f"[{chunk['vr_id']}:{chunk['section']}]"]
    if chunk.get("status") != "active":
        parts.append(f"({chunk['status'].upper()})")
    if score is not None:
        parts.append(f"score={score:.4f}")
    if chunk.get("date"):
        parts.append(f"date={chunk['date']}")
    header = " ".join(parts)
    content = chunk["content"][:500]
    if len(chunk["content"]) > 500:
        content += "..."
    entities = ", ".join(chunk["entities"][:10])
    return f"{header}\n{content}\n  entities: [{entities}]\n"

def format_object(name, data):
    lines = [f"Entity: {name}"]
    lines.append(f"  First seen: {data['first_seen']}")
    lines.append(f"  Last seen:  {data['last_seen']}")
    lines.append(f"  Mentions:   {data['mention_count']}")

    if data.get("type"):
        valid_tag = "" if data.get("type_valid", True) else "  *** FAILS TYPE VALIDATOR"
        lines.insert(1, f"  Type:       {data['type']}{valid_tag}")
    if data.get("values"):
        vals = data["values"]
        distinct = sorted({v["value"] for v in vals}, key=lambda x: (len(x), x))
        lines.append(f"  Value history ({len(vals)} records, distinct: {', '.join(distinct)}):")
        for v in vals[-20:]:
            status_tag = f" [{v['status']}]" if v["status"] != "active" else ""
            lines.append(f"    {v['vr_id']} ({v.get('date','?')}): {v['value']}{status_tag}")
        if len(vals) > 20:
            lines.append(f"    ... ({len(vals)-20} earlier records)")

    lines.append("  Mention timeline:")
    for m in data["mentions"][-15:]:
        status_tag = f" [{m['status']}]" if m["status"] != "active" else ""
        lines.append(f"    {m['vr_id']} §{m['section']}{status_tag}")
    if len(data["mentions"]) > 15:
        lines.insert(-15, f"    ... ({len(data['mentions'])-15} earlier mentions)")
    return "\n".join(lines)

# ---------------------------------------------------------------------------
# Semantic search via ChromaDB (optional)
# ---------------------------------------------------------------------------

CHROMA_DIR = DATA_DIR / "chroma_db"

def _try_chroma_search(query, top_k=15):
    """Attempt semantic search via ChromaDB + ONNX embedder. Returns True if successful."""
    if not CHROMA_DIR.exists():
        return False
    try:
        import chromadb
    except ImportError:
        return False

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    try:
        collection = client.get_collection("vr_corpus")
    except Exception:
        return False

    model_dir = DATA_DIR / "model"
    if not model_dir.exists():
        return False
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from embed import OnnxEmbedder
        embedder = OnnxEmbedder(model_dir)
    except Exception:
        return False

    query_embedding = embedder.encode([query]).tolist()

    results = collection.query(
        query_embeddings=query_embedding,
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    print(f"\nSemantic search results for: {query}\n{'='*60}")
    for i in range(len(results["ids"][0])):
        doc = results["documents"][0][i]
        meta = results["metadatas"][0][i]
        dist = results["distances"][0][i]
        similarity = 1 - dist

        vr_id = meta.get("vr_id", "?")
        section = meta.get("section", "?")
        status = meta.get("status", "active")
        date = meta.get("date", "")

        parts = [f"[{vr_id}:{section}]"]
        if status != "active":
            parts.append(f"({status.upper()})")
        parts.append(f"sim={similarity:.4f}")
        if date:
            parts.append(f"date={date}")
        header = " ".join(parts)

        content = doc[:500]
        if len(doc) > 500:
            content += "..."
        entities = meta.get("entities", "")
        print(f"{header}\n{content}\n  entities: [{entities}]\n")
        print("-" * 60)

    return True

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print('  query.py search "epsilon convergence"')
        print('  query.py object "eps_k3"')
        print("  query.py related VR-534")
        print("  query.py timeline eps_k3")
        print("  query.py graph VR-550")
        print("  query.py arc VR-812")
        print("  query.py method descent_engine")
        print('  query.py stratum "Sha E^161"')
        print('  query.py concept "uniform false-zero"')
        print("  query.py type field            # entities of a declared type")
        print("  query.py type group --flagged  # only validation suspects")
        print("  query.py page E^161            # consolidated object record")
        print("  query.py links K_A4            # domain links for an object/relation")
        print("  query.py locate stem_k         # every chunk mentioning an object — regions to READ (concept-LOCATE)")
        print("  query.py drift                 # seed↔corpus property drift")
        print("  query.py monitors              # declared object monitors + state")
        print("  query.py interface Twistable   # objects implementing an interface")
        print("  query.py coverage              # is the tool still capturing the corpus language?")
        print("  query.py doctest               # re-run curated reproducers; do they still PRODUCE the cited value? (opt-in)")
        print("  query.py brief                 # warm-start audit brief: active arcs + distrusted methods + unmet monitors + drift")
        print("  query.py orient plan.md VR-42  # execution-context orientation: where the given docs stand in the state machine")
        print("  query.py viz links --html      # interactive d3 graph (open in browser)")
        print("  query.py viz graph VR-819 --text # draw graph in terminal (mmdflux; --ascii too)")
        print("  query.py viz links --png       # render image (--svg/--dot/--mmd too)")
        print("  query.py viz graph VR-558      # supersession neighbourhood of a VR")
        print("  query.py viz arc VR-812        # the correction graph of a VR's arc")
        print("  query.py contradict VR-408     # contradiction check (refutations, value changes)")
        print("  query.py deprecated")
        print("  query.py stats")
        sys.exit(1)

    KNOWN_MODES = {"search", "object", "related", "timeline", "graph", "arc", "method",
                   "stratum", "concept", "type", "page", "links", "locate", "drift", "monitor",
                   "monitors", "captures", "interface", "coverage", "viz", "deprecated", "contradict",
                   "doctest", "brief", "orient", "stats"}
    # A first word that is not a mode keyword is treated as a bare semantic-search query
    # (so `query.py BSD period correction` works, and the /rag skill can forward verbatim).
    if sys.argv[1] not in KNOWN_MODES:
        sys.argv = [sys.argv[0], "search"] + sys.argv[1:]

    mode = sys.argv[1]
    flagged_only = "--flagged" in sys.argv[2:]
    viz_fmt = ("html" if "--html" in sys.argv else "png" if "--png" in sys.argv
               else "svg" if "--svg" in sys.argv else "dot" if "--dot" in sys.argv
               else "ascii" if "--ascii" in sys.argv else "text" if "--text" in sys.argv else "mmd")
    arg = " ".join(a for a in sys.argv[2:] if not a.startswith("--")) if len(sys.argv) > 2 else ""

    if mode not in ("deprecated", "stats", "type", "drift", "monitor", "monitors", "captures", "coverage", "viz", "doctest", "brief") and not arg:
        print(f"Mode '{mode}' requires an argument.")
        sys.exit(1)

    if mode == "search":
        chroma_available = _try_chroma_search(arg)
        if not chroma_available:
            chunks = load_chunks()
            print(f"Building TF-IDF index over {len(chunks)} chunks...")
            tfs, idfs = build_tfidf(chunks)
            results = search_tfidf(arg, chunks, tfs, idfs)
            print(f"\nTop results for: {arg}\n{'='*60}")
            for score, idx in results:
                if score > 0:
                    print(format_chunk(chunks[idx], score))
                    print("-" * 60)

    elif mode == "object":
        registry = load_registry()
        matches = lookup_object(arg, registry)
        if matches:
            for name, data in matches.items():
                print(format_object(name, data))
                print()
        else:
            # Not a corpus-extracted registry entity — before giving up, try the ontology
            # canonical layer: central objects like stem_2 / Omega_k are SEEDED objects
            # (objects.json), not registry entities, so the bare registry lookup whiffs (the
            # F-i gap). Resolve via objects.json and redirect to the full `page` record.
            oid = None
            try:
                oid = resolve_object(arg, load_json("objects.json"))
            except FileNotFoundError:
                pass
            if oid:
                print(f"'{arg}' is not a corpus-extracted entity, but resolves to canonical object '{oid}'.")
                print(f"  -> query.py page {oid}     (full object record: properties, links, claims)")
                print(f"  -> query.py locate {oid}   (every chunk mentioning it — regions to read)")
            else:
                print(f"No entity matching '{arg}'")
                suggestions = [k for k in registry if arg.lower()[:3] in k.lower()][:5]
                if suggestions:
                    print(f"Did you mean: {', '.join(suggestions)}")

    elif mode == "related":
        chunks = load_chunks()
        registry = load_registry()
        supersession = load_supersession()
        related = find_related(arg, chunks, registry, supersession)
        if not related:
            print(f"No related VRs found for {arg}")
        else:
            print(f"VRs related to {arg} (by entity overlap + supersession):\n")
            for vr_id, score in related:
                status = "active"
                for c in chunks:
                    if c["vr_id"] == vr_id:
                        status = c["status"]
                        break
                tag = f" [{status}]" if status != "active" else ""
                print(f"  {vr_id}{tag}: overlap={score}")

    elif mode == "graph":
        supersession = load_supersession()
        edges = [e for e in supersession["edges"]
                 if arg in (e["source"], e["target"])]
        if not edges:
            print(f"No supersession edges involving {arg}")
        else:
            # Annotate each edge with its W3C-PROV term (axis-3 interop map from supersession.json);
            # a trailing ≈ marks where the local verb is richer than PROV can express exactly.
            prov = supersession.get("relation_prov", {})
            print(f"Supersession graph for {arg}  (·→ PROV interop term):\n")
            for e in edges:
                p = prov.get(e["relation"])
                ann = ""
                if p:
                    ann = f"   · {p['prov']}" + ("" if p.get("exact", True) else " ≈")
                print(f"  {e['source']} --[{e['relation']}]--> {e['target']}{ann}")

    elif mode == "timeline":
        registry = load_registry()
        chunks = load_chunks()
        meta = load_meta()
        title_map = {m["id"]: m.get("title", "") for m in meta if m.get("id")}
        matches = lookup_object(arg, registry)
        if not matches:
            print(f"No entity matching '{arg}'")
        else:
            for name, data in matches.items():
                print(f"Timeline for: {name}")
                print(f"  First: {data['first_seen']}  Last: {data['last_seen']}")
                print(f"  {data['mention_count']} mentions across VRs\n")
                seen_vrs = []
                for m in data["mentions"]:
                    if not seen_vrs or seen_vrs[-1] != m["vr_id"]:
                        seen_vrs.append(m["vr_id"])
                for vr_id in seen_vrs:
                    title = title_map.get(vr_id, "")
                    status = "active"
                    for c in chunks:
                        if c["vr_id"] == vr_id:
                            status = c["status"]
                            break
                    tag = f" [{status.upper()}]" if status != "active" else ""
                    title_snip = f" — {title[:80]}" if title else ""
                    print(f"  {vr_id}{tag}{title_snip}")
                print()

    elif mode == "deprecated":
        chunks = load_chunks()
        meta = load_meta()
        title_map = {m["id"]: m.get("title", "") for m in meta if m.get("id")}
        dep_vrs = set()
        for c in chunks:
            if c["status"] in ("deprecated", "retracted"):
                dep_vrs.add((c["vr_id"], c["status"]))
        for vr_id, status in sorted(dep_vrs):
            title = title_map.get(vr_id, "")[:70]
            print(f"  {vr_id} [{status.upper()}] {title}")

    elif mode == "stats":
        try:
            with open(DATA_DIR / "index_stats.json") as f:
                stats = json.load(f)
            print(json.dumps(stats, indent=2))
        except FileNotFoundError:
            print("No stats found. Run index_vrs.py first.")

    elif mode == "arc":
        try:
            with open(DATA_DIR / "arcs.json") as f:
                arcs = json.load(f)
        except FileNotFoundError:
            print("No arcs.json found. Run index_vrs.py first.")
            sys.exit(1)

        matched = [a for a in arcs if arg in a.get("members", [])]
        if not matched:
            matched = [a for a in arcs if arg.lower() in json.dumps(a).lower()]
        if not matched:
            print(f"No arc containing {arg}")
            print(f"Available arcs ({len(arcs)}):")
            for a in arcs[:10]:
                print(f"  {a['members'][0]}..{a['members'][-1]} ({a['size']} VRs, {a['state']})")
        else:
            for arc in matched:
                print(f"Arc: {arc['members'][0]} -> {arc['members'][-1]}")
                print(f"  State: {arc['state'].upper()}")
                print(f"  Size: {arc['size']} VRs")
                print(f"  Error density: {arc['error_density']:.1%}")
                if arc.get("median_latency") is not None:
                    print(f"  Median correction latency: {arc['median_latency']} VRs")
                if arc.get("dates"):
                    print(f"  Span: {arc['dates'].get('first','')} -> {arc['dates'].get('last','')}")
                print(f"\n  Members ({arc['size']}):")
                corr_targets = {e["target"] for e in arc.get("correction_edges", [])}
                for member in arc["members"]:
                    tag = " *** CORRECTED" if member in corr_targets else ""
                    print(f"    {member}{tag}")
                if arc.get("correction_edges"):
                    print(f"\n  Correction edges ({arc['corrections']}):")
                    for e in arc["correction_edges"]:
                        print(f"    {e['source']} --[{e['relation']}]--> {e['target']}")
                if arc.get("key_entities"):
                    print(f"\n  Key entities:")
                    for ke in arc["key_entities"][:10]:
                        print(f"    {ke['entity']}: {ke['count']} mentions")
                print()

    elif mode == "method":
        try:
            with open(DATA_DIR / "method_registry.json") as f:
                methods = json.load(f)
        except FileNotFoundError:
            print("No method_registry.json found. Run index_vrs.py first.")
            sys.exit(1)

        if arg in methods:
            matches = {arg: methods[arg]}
        else:
            matches = {k: v for k, v in methods.items() if arg.lower() in k.lower()}
        if not matches:
            print(f"No method matching '{arg}'")
            print(f"Available methods: {', '.join(sorted(methods.keys()))}")
        else:
            for mid, data in matches.items():
                print(f"Method: {mid}")
                print(f"  Current state: {data['current_state']}")
                print(f"  Has produced wrong answer: {data['has_produced_wrong_answer']}")
                print(f"  Events: {data['event_count']}")
                print(f"  Defining VRs: {', '.join(data['defining_vrs'][:15])}")
                print(f"\n  Lifecycle:")
                for ev in data["events"]:
                    print(f"    {ev['vr_id']} ({ev.get('date','?')}): {ev['state']}")
                print()

    elif mode == "stratum":
        try:
            with open(DATA_DIR / "claim_status.json") as f:
                claim_status_data = json.load(f)
        except FileNotFoundError:
            print("No claim_status.json found. Run index_vrs.py first.")
            sys.exit(1)

        def _normalize_for_stratum(s):
            s = re.sub(r"[|{}()^\\]", "", s)
            s = re.sub(r"[_]", " ", s)
            s = re.sub(r"\s+", " ", s)
            return s.lower().strip()

        norm_arg = _normalize_for_stratum(arg)
        arg_words = norm_arg.split()

        print(f"Stratum history for claims matching: {arg}\n{'='*60}")
        found = False
        for vr_id in sorted(claim_status_data.keys(), key=lambda v: int(re.search(r"\d+", v).group()) if re.search(r"\d+", v) else 0):
            cs = claim_status_data[vr_id]
            strata = cs.get("strata", [])
            for s in strata:
                norm_claim = _normalize_for_stratum(s["claim"])
                if norm_arg in norm_claim or all(w in norm_claim for w in arg_words):
                    found = True
                    print(f"  [{vr_id}] {s['stratum'].upper()}: {s['claim'][:120]}")
        if not found:
            print(f"  No claims matching '{arg}' with stratum markers found.")
            print("  Try broader terms: Sha, rank, dim, eps_k")

    elif mode == "concept":
        try:
            with open(DATA_DIR / "concepts.json") as f:
                concepts = json.load(f)
        except FileNotFoundError:
            print("No concepts.json found. Run index_vrs.py first.")
            sys.exit(1)

        matched = [c for c in concepts if arg.lower() in c["term"].lower()]
        if not matched:
            print(f"No concept matching '{arg}'")
            print(f"Top concepts by propagation:")
            for c in concepts[:15]:
                print(f"  \"{c['term']}\" -- {c['propagation_count']} VRs, {c['continuity']}, intro: {c['introduced_in']}")
        else:
            for c in matched:
                print(f"Concept: \"{c['term']}\"")
                print(f"  Introduced in: {c['introduced_in']} ({c.get('introduction_date', '?')})")
                print(f"  Propagation: {c['propagation_count']} VRs")
                print(f"  Continuity: {c['continuity']}")
                print(f"  VR trail: {', '.join(c['vrs'])}")
                print()

    elif mode == "contradict":
        chunks = load_chunks()
        registry = load_registry()
        supersession = load_supersession()
        meta = load_meta()
        title_map = {m["id"]: m.get("title", "") for m in meta if m.get("id")}
        # Authoritative self-referential status (classify_status): distinguishes a VR that
        # IS retracted from one that merely DISCUSSES a dead/superseded object. has_retraction
        # (any DEAD/SUPERSEDED body text) over-flags VERIFIED/PROVED entries — AUDIT-210 F2.
        status_by_vr = {m["id"]: m.get("status_classified", "active") for m in meta if m.get("id")}
        RETRACTED_STATES = ("retracted", "deprecated", "corrected")

        claim_status = {}
        try:
            with open(DATA_DIR / "claim_status.json") as f:
                claim_status = json.load(f)
        except FileNotFoundError:
            pass

        print(f"Contradiction check for {arg}\n{'='*50}")

        cs = claim_status.get(arg, {})
        self_status = status_by_vr.get(arg, "active")
        if cs:
            print(f"Claim status: {cs.get('primary', '?')}  (entry status: {self_status})")
            if cs.get("body_signals"):
                print(f"  Body signals: {', '.join(cs['body_signals'])}")
            if self_status in RETRACTED_STATES:
                print(f"  *** THIS VR IS {self_status.upper()} ***")
            elif cs.get("has_retraction"):
                print(f"  (contains retraction/dead discussion markers; this VR's own status is {self_status})")
            print()

        edges = [e for e in supersession.get("edges", [])
                 if arg in (e["source"], e["target"])]
        if edges:
            print("Supersession edges:")
            for e in edges:
                direction = "→" if e["source"] == arg else "←"
                other = e["target"] if e["source"] == arg else e["source"]
                relation = e["relation"]
                if relation in ("refutes", "corrects", "retracts", "downgrades") and e["target"] == arg:
                    print(f"  *** {other} --[{relation}]--> {arg} (THIS VR CORRECTED/REFUTED)")
                else:
                    print(f"  {e['source']} --[{relation}]--> {e['target']}")
            print()

        vr_entities = set()
        for chunk in chunks:
            if chunk["vr_id"] == arg:
                vr_entities.update(chunk["entities"])
        vr_entities -= {arg}

        value_changes = []
        for entity in sorted(vr_entities):
            if entity in registry and registry[entity].get("values"):
                vals = registry[entity]["values"]
                unique_vals = set(v["value"] for v in vals)
                if len(unique_vals) > 1:
                    history = "; ".join(f'{v["value"]} ({v["vr_id"]}, {v["status"]})' for v in vals[:5])
                    value_changes.append(f"  {entity}: {history}")

        if value_changes:
            print("Entities with value changes:")
            for vc in value_changes[:10]:
                print(vc)
            print()

        # A referenced VR is "retracted/corrected" iff its OWN classified status says so —
        # NOT merely because it discusses a dead object (AUDIT-210 F2 fix). Uses the same
        # self-referential determination classify_status makes for the entry itself.
        retracted_refs = set()
        for entity in vr_entities:
            sys.path.insert(0, str(Path(__file__).parent)); import domain_ids
            if entity.startswith((domain_ids.PRIMARY + "-", domain_ids.AUDIT + "-")) and status_by_vr.get(entity) in RETRACTED_STATES:
                retracted_refs.add(entity)
        if retracted_refs:
            print(f"References to retracted/corrected VRs: {', '.join(sorted(retracted_refs))}")

        if not edges and not value_changes and not retracted_refs and self_status not in RETRACTED_STATES:
            print("No contradictions found.")

    elif mode == "type":
        try:
            with open(DATA_DIR / "type_registry.json") as f:
                type_reg = json.load(f)["types"]
        except FileNotFoundError:
            print("No type_registry.json found. Run index_vrs.py first.")
            sys.exit(1)

        if not arg:
            print(f"Declared entity types:\n{'='*60}")
            for tid, b in sorted(type_reg.items(), key=lambda kv: -kv[1]["count"]):
                if tid == "_untyped":
                    continue
                flag = f", {b['flagged']} flagged" if b["flagged"] else ""
                print(f"  {tid:<12} {b['count']:>5}  ({b['display']}{flag})")
            ut = type_reg.get("_untyped", {})
            if ut.get("count"):
                print(f"  {'_untyped':<12} {ut['count']:>5}  (no declared type; e.g. {', '.join(ut['examples'][:5])})")
            print("\nUse: query.py type <id>   |   query.py type <id> --flagged")
        else:
            registry = load_registry()
            members = [(k, v) for k, v in registry.items() if v.get("type") == arg]
            if not members:
                print(f"No entities of type '{arg}'. Known types: {', '.join(t for t in type_reg if t != '_untyped')}")
            else:
                if flagged_only:
                    members = [(k, v) for k, v in members if v.get("type_valid") is False]
                    print(f"Type '{arg}' — validation suspects ({len(members)}):\n{'='*60}")
                else:
                    print(f"Type '{arg}' — {len(members)} entities "
                          f"(sorted by mentions; * = fails validator):\n{'='*60}")
                for k, v in sorted(members, key=lambda kv: -kv[1].get("mention_count", 0)):
                    star = " *" if v.get("type_valid") is False else ""
                    print(f"  {k}{star}  ({v.get('mention_count',0)} mentions)")

    elif mode == "page":
        try:
            objdata = load_json("objects.json")
        except FileNotFoundError:
            print("No objects.json. Run ontology.py (or rebuild.sh) first.")
            sys.exit(1)
        oid = resolve_object(arg, objdata)
        if not oid:
            print(f"No object resolves from '{arg}'.")
            sample = list(objdata.get("objects", {}).keys())[:20]
            print(f"Known objects ({len(objdata.get('objects', {}))}): {', '.join(sample)} ...")
            sys.exit(0)
        o = objdata["objects"][oid]
        drift_idx = {}
        try:
            for fl in load_json("object_drift.json").get("flags", []):
                drift_idx[(fl["subject"], fl["prop"])] = fl
        except FileNotFoundError:
            pass
        dropped = "  *** DROPPED" if o.get("dropped") else ""
        print(f"{'='*64}\nOBJECT: {oid}  [{o['type']}]{dropped}\n{'='*64}")
        print(f"  {o.get('title','')}")
        if o.get("note"):
            print(f"  note: {o['note']}")
        print(f"  aliases: {', '.join(o.get('aliases', []))}")
        print(f"  interfaces: {', '.join(o.get('interfaces', []))}")

        def _show_props(props, subj, indent="    "):
            for prop, r in props.items():
                tags = []
                if r.get("stratum"): tags.append(r["stratum"])
                if r.get("vr_id"): tags.append(r["vr_id"])
                tag = f"  [{', '.join(tags)}]" if tags else ""
                d = drift_idx.get((subj, prop))
                dflag = (f"  ⚠ DRIFT vs corpus {d['corpus_value']} ({d.get('corpus_vr_count','?')} VRs)"
                         if d else "")
                print(f"{indent}{prop} = {r['value']}{tag}{dflag}")

        if o.get("properties"):
            print("\n  Properties:")
            _show_props(o["properties"], oid)
        if o.get("pairs"):
            print("\n  Per-field (curve,field) facts:")
            for fid, props in o["pairs"].items():
                print(f"    over {fid}:")
                _show_props(props, f"{oid}@{fid}", indent="      ")
        if o.get("links_out") or o.get("links_in"):
            print("\n  Links:")
            for lk in o.get("links_out", []):
                s = "  [SUPERSEDED]" if lk.get("superseded") else ""
                vr = f" ({lk['vr_id']})" if lk.get("vr_id") else ""
                print(f"    {oid} --[{lk['relation']}]--> {lk['target']}{vr}{s}")
            for lk in o.get("links_in", []):
                s = "  [SUPERSEDED]" if lk.get("superseded") else ""
                print(f"    {lk['source']} --[{lk['relation']}]--> {oid}")
        m = o.get("mentions", {})
        if m.get("total_mentions"):
            print(f"\n  Corpus: {m['total_mentions']} mentions "
                  f"({m.get('first_seen')}..{m.get('last_seen')})")
        if o.get("claims"):
            print("\n  Claims (top, by commitment):")
            for c in o["claims"][:8]:
                print(f"    [{c['vr_id']}] {(c.get('stratum') or '?').upper()}: {c['claim']}")

    elif mode == "links":
        objdata = load_json("objects.json")
        linkdata = load_json("domain_links.json")
        relations = {lk["relation"] for lk in linkdata.get("links", [])}
        if arg in relations:
            print(f"All '{arg}' links:\n{'='*50}")
            for lk in linkdata["links"]:
                if lk["relation"] == arg:
                    s = "  [SUPERSEDED]" if lk.get("superseded") else ""
                    print(f"  {lk['source']} --> {lk['target']}{s}")
        else:
            oid = resolve_object(arg, objdata)
            if not oid:
                print(f"No object or relation '{arg}'. Relations: {', '.join(sorted(relations))}")
                sys.exit(0)
            o = objdata["objects"][oid]
            print(f"Links for {oid}:\n{'='*50}")
            for lk in o.get("links_out", []):
                s = "  [SUPERSEDED]" if lk.get("superseded") else ""
                print(f"  {oid} --[{lk['relation']}]--> {lk['target']}{s}")
            for lk in o.get("links_in", []):
                print(f"  {lk['source']} --[{lk['relation']}]--> {oid}")

    elif mode == "drift":
        try:
            d = load_json("object_drift.json")
        except FileNotFoundError:
            print("No object_drift.json. Run ontology.py first.")
            sys.exit(1)
        st = d.get("stats", {})
        print(f"Seed↔corpus drift  (confirmed={st.get('confirmed',0)} "
              f"unconfirmed={st.get('unconfirmed',0)} unverified={st.get('unverified',0)} "
              f"no_detector={st.get('no_detector',0)} FLAGGED={st.get('flagged',0)})\n{'='*60}")
        for fl in d.get("flags", []):
            print(f"  ⚠ {fl['subject']} . {fl['prop']}: seed={fl['seed_value']} "
                  f"vs corpus={fl['corpus_value']} (in {fl['corpus_vr_count']} VRs)")
        if not d.get("flags"):
            print("  No high-precision drift flags "
                  f"({st.get('confirmed',0)} seed values confirmed against the corpus).")

    elif mode in ("monitor", "monitors"):
        try:
            md = load_json("monitors.json")
        except FileNotFoundError:
            print("No monitors.json. Run ontology.py first.")
            sys.exit(1)
        print(f"Object monitors ({len(md.get('monitors',[]))}):\n{'='*60}")
        for m in md.get("monitors", []):
            mark = "✗ UNMET" if m["state"] == "unmet" else ("✓ met" if m["state"] == "met" else m["state"])
            print(f"  [{m.get('severity','?')}] {mark}  {m['id']}")
            print(f"      watch: {m.get('watch','')}")
            print(f"      {m.get('evidence','')}")

    elif mode == "captures":
        # P6 M3: the cross-tier capture ledger (tiered deployments with thread tiers)
        try:
            cl = load_json("capture_ledger.json")
        except FileNotFoundError:
            print("No capture_ledger.json — no thread tiers declared (or single-tier mode).")
            sys.exit(0)
        print(f"Capture ledger  (threads: {len(cl.get('threads',[]))} · "
              f"captures: {len(cl.get('captures',[]))} · "
              f"unreconciled rounds: {len(cl.get('unreconciled_rounds',[]))} · "
              f"receipt candidates: {len(cl.get('receipt_candidates',[]))})\n" + "=" * 60)
        for e in cl.get("captures", []):
            rnd = f" R{e['round']}" if e.get("round") else " (whole thread)"
            print(f"  ✓ {e['vr']} captures {e['thread']}{rnd}")
        for u in cl.get("unreconciled_rounds", []):
            print(f"  ✗ UNRECONCILED {u['thread']} R{u['round']}  ({u['path']})")
        for c in cl.get("receipt_candidates", []):
            print(f"  ⚠ RECEIPT-CANDIDATE {c['vr']} cites {c['thread']} R{c['round']} — "
                  f"READ to certify (candidate, NOT a verdict): «{c['span']}»")

    elif mode == "viz":
        sys.path.insert(0, str(Path(__file__).parent))
        import viz as vizmod
        parts = arg.split()
        target = parts[0] if parts else "links"
        tgt_arg = parts[1] if len(parts) > 1 else None
        path, err = vizmod.make(target, tgt_arg, fmt=viz_fmt)
        if err:
            print(err)
        if path:
            if viz_fmt in ("text", "ascii"):
                # rendered terminal diagram via mmdflux
                print(path.read_text())
            elif viz_fmt in ("mmd", "dot"):
                # present the source in the terminal (paste into GitHub markdown / mermaid.live)
                print(path.read_text())
                tag = "Mermaid" if viz_fmt == "mmd" else "Graphviz DOT"
                print(f"\n# ↑ {tag} — also written to {path}"
                      + ("  (renders in GitHub markdown / mermaid.live; --text/--ascii to draw in terminal, "
                         "--png/--svg for an image, --dot for Graphviz)"
                         if viz_fmt == "mmd" else "  (render: dot -Tpng)"))
            else:
                print(f"wrote {path}")
                if viz_fmt == "html":
                    print(f"  (interactive d3 graph — open in a browser:  open {path} )")

    elif mode == "coverage":
        try:
            c = load_json("coverage_report.json")
        except FileNotFoundError:
            print("No coverage_report.json. Run coverage.py (or rebuild.sh) first.")
            sys.exit(1)
        s = c.get("summary", {})
        print(f"Self-coverage audit — is the tool still capturing the program's language?\n{'='*64}")
        print(f"  uncaptured recurring tokens: {s.get('uncaptured_tokens',0)}   "
              f"unknown relation verbs: {s.get('uncaptured_relations',0)}   "
              f"unseeded objects: {s.get('unseeded_objects',0)}   "
              f"alias drift: {s.get('alias_drift',0)}")
        print("\n  Top uncaptured notation (recurring, not matched by any entity pattern/seed):")
        for t in c.get("uncaptured_tokens", [])[:12]:
            print(f"    {t['token']}  ({t['vrs']} VRs; e.g. {', '.join(t['examples'])})")
        print("\n  Unknown relation verbs adjacent to VR refs (candidate new relations):")
        for v in c.get("uncaptured_relations", [])[:10]:
            print(f"    {v['verb']}  ({v['count']}×; e.g. {v['example']})")
        print("\n  Object-shaped entities NOT in the ontology seed (the seed is behind the corpus):")
        for o in c.get("unseeded_objects", [])[:12]:
            print(f"    {o['entity']}  ({o['mentions']} mentions, type={o['type']})")
        if c.get("alias_drift"):
            ad = c["alias_drift"]
            # GENUINE = the dominant surface form does NOT resolve to its object (a real missing
            # alias / collision). Keyed on resolve(), NOT normalize() — AUDIT-222 F-aliases: the
            # normalization key falsely tagged already-resolving non-folding aliases (e.g. '64a1'
            # for E) as "GENUINE — add", producing standing false prompts. (resolves absent ⟹ treat
            # as genuine so a pre-fix report still surfaces, not hides.)
            genuine = [d for d in ad if not d.get("resolves", False)]
            print(f"\n  Alias drift (corpus's dominant recent form ≠ seed primary) — "
                  f"{len(genuine)} GENUINE, {len(ad) - len(genuine)} cosmetic:")
            if genuine:
                print("  ⚠ GENUINE drift does NOT resolve() to its object — a sweep keyed on the "
                      "seed form WOULD MISS the corpus form (the AUDIT-217 failure). Add it as an alias.")
            for d in ad[:12]:
                tag = ("  [cosmetic — already resolves]" if d.get("resolves", False)
                       else "  [GENUINE — add as alias]")
                print(f"    {d['object']}: seed='{d['seed_primary']}' vs corpus='{d['recent_dominant']}'{tag}")

    elif mode == "interface":
        objdata = load_json("objects.json")
        ifaces = objdata.get("interfaces", {})
        if arg not in ifaces:
            print(f"Unknown interface '{arg}'. Known: {', '.join(ifaces)}")
            sys.exit(0)
        members = [oid for oid, o in objdata["objects"].items() if arg in o.get("interfaces", [])]
        print(f"Interface '{arg}' — {ifaces[arg]}\n{'='*60}\n  {len(members)} objects:")
        for oid in members:
            print(f"    {oid} [{objdata['objects'][oid]['type']}]")

    elif mode == "locate":
        try:
            objdata = load_json("objects.json")
        except FileNotFoundError:
            print("No objects.json. Run ontology.py (or rebuild.sh) first.")
            sys.exit(1)
        oid = resolve_object(arg, objdata)
        if not oid:
            print(f"No object resolves from '{arg}'.")
            sample = list(objdata.get("objects", {}).keys())[:20]
            print(f"Known objects ({len(objdata.get('objects', {}))}): {', '.join(sample)} ...")
            sys.exit(0)
        o = objdata["objects"][oid]
        sys.path.insert(0, str(Path(__file__).parent))
        from ontology import locate_object
        hits = locate_object(o, load_chunks())   # on-demand: one object × corpus, ~0.4s
        active = [h for h in hits if h.get("status") not in ("retracted", "deprecated")]
        print(f"{'='*64}\nLOCATE: {oid}  [{o.get('type','?')}] — {len(hits)} chunk(s) to READ ({len(active)} active)\n{'='*64}")
        print("  concept-LOCATE: regions mentioning this object. An ENUMERATOR, NOT a verdict —")
        print("  read each to CERTIFY (grep-0 ≠ concept-clean; VR-1027). Scope = verification_ready/.")
        for h in hits:
            cid = h.get("chunk_id") or "?"
            st = f" [{h['status']}]" if h.get("status") in ("retracted", "deprecated", "corrected") else ""
            al = f"  ⟨{', '.join(h.get('matched_aliases', []))}⟩" if h.get("matched_aliases") else ""
            print(f"    {cid:<22} {(h.get('section') or '')[:46]}{st}{al}")
        if not hits:
            print("  (no chunks mention this object in the verification_ready/ corpus)")

    elif mode == "doctest":
        sys.path.insert(0, str(Path(__file__).parent))
        import doctest_grounding
        sys.exit(doctest_grounding.run())

    elif mode == "brief":
        # Warm-start audit brief — regenerate from the current graph so the digest is always
        # fresh, write it to data/rag/audit_brief.md, and print it.
        sys.path.insert(0, str(Path(__file__).parent))
        import synthesize_brief
        synthesize_brief.main()
        print()
        print((synthesize_brief.OUT).read_text())

    elif mode == "orient":
        # Execution-context orientation — plan-scoped sibling of brief: compile where the
        # given documents (plan / planning message / VR ids) stand in the state machine.
        sys.path.insert(0, str(Path(__file__).parent))
        import orient
        sys.exit(orient.main(sys.argv[2:]))

    else:
        print(f"Unknown mode: {mode}. Use: search, object, related, graph, timeline, arc, method, stratum, concept, type, page, links, locate, drift, monitor, interface, coverage, viz, deprecated, contradict, doctest, brief, stats")

if __name__ == "__main__":
    main()
