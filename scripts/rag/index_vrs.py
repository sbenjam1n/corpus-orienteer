#!/usr/bin/env python3
"""
RAG indexer for the VR/AUDIT corpus.

Two-layer output:
  1. data/rag/entity_registry.json  — named objects with history chains
  2. data/rag/chunks.jsonl          — section-level chunks with metadata
  3. data/rag/supersession.json     — correction/deprecation graph

Run:  python3 scripts/rag/index_vrs.py
"""

import json, os, re, hashlib, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tiers as tiers_mod  # noqa: E402  (P6 M1: optional corpus tiers)
import domain_ids  # doc-id scheme (PRIMARY/AUDIT prefixes), config-driven
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[2]
# Standalone/porting overrides (Plans/rag_standalone_extraction_execution.md Stage 1):
# RAG_CORPUS_DIR / RAG_DATA_DIR / RAG_SEED_DIR redirect the corpus, outputs, and
# domain-config+seeds. Defaults preserve the in-repo deployment exactly.
VR_DIR = Path(os.environ.get("RAG_CORPUS_DIR", ROOT / "verification_ready"))
DATA_DIR = Path(os.environ.get("RAG_DATA_DIR", ROOT / "data" / "rag"))
SEED_DIR = Path(os.environ.get("RAG_SEED_DIR", Path(__file__).resolve().parent))
_TIERS = tiers_mod.load()   # None ⟹ single-tier compatibility mode (P6 C1 invariant)

# ---------------------------------------------------------------------------
# 1. VR/AUDIT file discovery
# ---------------------------------------------------------------------------

def discover_files():
    """Find all VR-*.md and AUDIT-*.md files, sorted by numeric ID.

    Tiered mode (tiers.json present — P6 M1): files under `indexed: false` tiers are
    excluded (derived artifacts are never sources), and additional contract='vr' tier
    roots are walked with the same patterns. Without tiers.json this is byte-identical
    to the single-tier behavior."""
    roots = [VR_DIR]
    if _TIERS:
        roots += [p for _tid, p in tiers_mod.contract_vr_roots(_TIERS, VR_DIR)]
    files, seen = [], set()
    for root in roots:
        for pattern, kind in [(f"{domain_ids.PRIMARY}-*.md", "vr"),
                              (f"{domain_ids.AUDIT}-*.md", "audit")]:
            for p in sorted(root.glob(pattern)):
                if _TIERS and tiers_mod.excluded(p, _TIERS):
                    continue
                m = domain_ids.STEM_RE.match(p.stem)
                if m and str(p) not in seen:
                    seen.add(str(p))
                    files.append((kind, int(m.group(2)), p))
    files.sort(key=lambda x: (x[0], x[1]))
    return files

# ---------------------------------------------------------------------------
# 2. Header parser — handles all three format variants
# ---------------------------------------------------------------------------

def parse_header(text, filepath):
    """Extract structured metadata from VR/AUDIT header."""
    meta = {
        "file": filepath.name,
        "id": None,
        "title": None,
        "date": None,
        "status": None,
        "version": None,
        "iter": None,
        "paper_version": None,
        "author": None,
        "outline_xref": None,
    }

    m = domain_ids.STEM_RE.match(filepath.stem)
    if m:
        meta["id"] = f"{m.group(1)}-{m.group(2)}"

    title_m = domain_ids.TITLE_RE.search(text)
    if title_m:
        meta["title"] = title_m.group(1).strip()

    date_m = re.search(r"\*\*Date:\*\*\s*(\d{4}-\d{2}-\d{2})", text)
    if date_m:
        meta["date"] = date_m.group(1)

    status_m = re.search(r"\*\*Status:\*\*\s*(.+?)(?:\s{2,}|\n)", text)
    if status_m:
        meta["status"] = status_m.group(1).strip()

    version_m = re.search(r"\*\*Version:\*\*\s*(\S+)", text)
    if version_m:
        meta["version"] = version_m.group(1)

    iter_m = re.search(r"(?:iter|Iter)\s+(\d+)", text[:500])
    if iter_m:
        meta["iter"] = int(iter_m.group(1))

    ep_m = re.search(r"EDIT-PROTOCOL:.*?paper_outline_v[\d_]+\.md\s+(v[\d.]+)", text[:500])
    if ep_m:
        meta["paper_version"] = ep_m.group(1)

    author_m = re.search(r"\*\*Author:\*\*\s*(.+?)(?:\s{2,}|\n)", text)
    if author_m:
        meta["author"] = author_m.group(1).strip()

    xref_m = re.search(r"\*\*Outline cross-reference:\*\*\s*(.+?)(?:\n\n|\n\*\*)", text, re.S)
    if xref_m:
        meta["outline_xref"] = xref_m.group(1).strip()

    oid_m = re.search(r"\*\*Outline ID\(s\):\*\*\s*(.+?)(?:\s{2,}|\n)", text)
    if oid_m:
        meta["outline_ids"] = oid_m.group(1).strip()

    return meta

# ---------------------------------------------------------------------------
# 3. Section splitter
# ---------------------------------------------------------------------------

def split_sections(text):
    """Split markdown into sections by ## headers. Returns list of (header, body)."""
    parts = re.split(r"(?=^##\s)", text, flags=re.M)
    sections = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        lines = part.split("\n", 1)
        header = lines[0].strip().lstrip("#").strip()
        body = lines[1].strip() if len(lines) > 1 else ""
        sections.append((header, body))
    return sections

# ---------------------------------------------------------------------------
# 4. Entity extraction
# ---------------------------------------------------------------------------

ENTITY_PATTERNS = [
    # VR/AUDIT cross-references
    (r"\bVR-(\d+)\b", lambda m: f"VR-{m.group(1)}"),
    (r"\bAUDIT-(\d+)\b", lambda m: f"AUDIT-{m.group(1)}"),
    # Groups
    (r"\b(S[_₃₄₅₆]|A[_₃₄₅₆]|G[_₁₂₃₄₅₆ₖ]|D[_₄₆₈])\b", lambda m: m.group(1)),
    (r"\b(S_\d+|A_\d+|G_\d+|D_\d+)\b", lambda m: m.group(1)),
    # Class/irr IDs
    (r"\b(cl\d+|irr\[\d+\]|irr_?\d+)\b", lambda m: m.group(1)),
    # Theorems
    (r"\b(T\d{1,2})\b", lambda m: m.group(1)),
    # Key values with assignments
    (r"\b(eps_k\d)\s*=\s*(\d+)", lambda m: f"{m.group(1)}={m.group(2)}"),
    (r"\b(rank)\s*=\s*(\d+)", lambda m: f"rank={m.group(2)}"),
    (r"\|?[Ss]ha\|?\s*=\s*(\d+)", lambda m: f"sha={m.group(1)}"),
    # Curves
    (r"\b(\d+a\d+)\b", lambda m: m.group(1)),
    # Fields
    (r"\b(stem_\d+|K[_₁₂₃₄₅₆])\b", lambda m: m.group(1)),
    (r"\b(K_[A-Z]\d+|K_[SD]\d+|M_cubic)\b", lambda m: m.group(1)),
    # Paper sections
    (r"§(\d+(?:\.\d+)*[a-z]?)", lambda m: f"§{m.group(1)}"),
    # Lean modules
    (r"\b(proofs/\w+(?:/\w+)*\.lean)\b", lambda m: m.group(1)),
    # Scripts
    (r"\b(scripts/[\w/]+\.(?:gp|py|g|c|gap))\b", lambda m: m.group(1)),
]

def extract_entities(text):
    """Extract named entities from text. Returns set of entity strings."""
    entities = set()
    for pattern, extractor in ENTITY_PATTERNS:
        for m in re.finditer(pattern, text):
            entities.add(extractor(m))
    return entities

# ---------------------------------------------------------------------------
# 4b. Declared entity-type schema + validator  (Palantir "object type" analog)
#
# An entity's kind was previously implicit in WHICH regex family matched it;
# registry entries carried no type field. This declares a type vocabulary and,
# per type, two patterns:
#   match  — LOOSE: mirrors the extraction family, so even malformed tokens get a
#            type (e.g. truncation garbage "G_" is still typed `group`).
#   valid  — TIGHT: what a well-formed key of that type must fullmatch.
# A key that carries a type but FAILS its `valid` pattern is an extraction
# SUSPECT, emitted to type_violations.json for the grounding/audit loop to review
# (this is what turns a cosmetic type label into a noise-detection instrument).
# Order matters: classify_type returns the first family whose `match` fullmatches.
# ---------------------------------------------------------------------------

TYPE_SCHEMA = {
    "vr_ref":      {"display": "VR cross-reference",      "match": r"VR-\d+",  "valid": r"VR-\d+"},
    "audit_ref":   {"display": "AUDIT cross-reference",   "match": r"AUDIT-\d+", "valid": r"AUDIT-\d+"},
    "parameter":   {"display": "tracked quantity/value",  "match": r"(?:rank|sha|eps_k\d)(?:=-?\d+)?",
                                                          "valid": r"(?:rank|sha|eps_k\d)(?:=-?\d+)?"},
    "theorem":     {"display": "theorem label",           "match": r"T\d{1,2}", "valid": r"T\d{1,2}"},
    "irrep_class": {"display": "conjugacy class / irrep",  "match": r"cl\d+|irr\[?_?\d+\]?",
                                                          "valid": r"cl\d+|irr\[\d+\]|irr_?\d+"},
    "field":       {"display": "number field",            "match": r"stem_\d+|K[_₁₂₃₄₅₆]|K_[A-Z]\d+|K_[SD]\d+|M_cubic",
                                                          "valid": r"stem_\d+|K[₁₂₃₄₅₆]|K_[A-Z]\d+|K_[SD]\d+|M_cubic"},
    "curve":       {"display": "elliptic curve (Cremona)", "match": r"\d+a\d+", "valid": r"\d{1,4}a\d{1,2}"},
    "group":       {"display": "Galois/symmetry group",   "match": r"[SAGD](?:_\d*|[₀₁₂₃₄₅₆₇₈₉ₖ])",
                                                          "valid": r"[SAGD](?:_\d+|[₀₁₂₃₄₅₆₇₈₉ₖ])"},
    "section":     {"display": "paper section",           "match": r"§\d+(?:\.\d+)*[a-z]?", "valid": r"§\d+(?:\.\d+)*[a-z]?"},
    "lean_module": {"display": "Lean module",             "match": r"proofs/[\w/]+\.lean", "valid": r"proofs/[\w/]+\.lean"},
    "script":      {"display": "compute script",          "match": r"scripts/[\w/]+\.(?:gp|py|g|c|gap)",
                                                          "valid": r"scripts/[\w/]+\.(?:gp|py|g|c|gap)"},
}

_TYPE_MATCH = [(tid, re.compile(spec["match"])) for tid, spec in TYPE_SCHEMA.items()]
_TYPE_VALID = {tid: re.compile(spec["valid"]) for tid, spec in TYPE_SCHEMA.items()}

def classify_type(entity):
    """Return the declared type id for an entity string (loose), or None."""
    for tid, rx in _TYPE_MATCH:
        if rx.fullmatch(entity):
            return tid
    return None

def is_valid_for_type(entity, tid):
    """True if entity is a well-formed key for its declared type (tight validator)."""
    rx = _TYPE_VALID.get(tid)
    return bool(rx and rx.fullmatch(entity))

def build_type_registry(registry):
    """Stamp each registry entry with a type; collect a per-type summary and the
    list of typed-but-malformed keys (validation suspects)."""
    type_summary = {tid: {"display": spec["display"], "valid_pattern": spec["valid"],
                          "count": 0, "flagged": 0, "examples": []}
                    for tid, spec in TYPE_SCHEMA.items()}
    type_summary["_untyped"] = {"display": "no declared type", "valid_pattern": None,
                                "count": 0, "flagged": 0, "examples": []}
    violations = []
    for entity, data in registry.items():
        tid = classify_type(entity)
        data["type"] = tid
        bucket = type_summary.get(tid or "_untyped")
        bucket["count"] += 1
        if tid is None:
            if len(bucket["examples"]) < 10:
                bucket["examples"].append(entity)
            continue
        if is_valid_for_type(entity, tid):
            if len(bucket["examples"]) < 10:
                bucket["examples"].append(entity)
        else:
            bucket["flagged"] += 1
            data["type_valid"] = False
            violations.append({"entity": entity, "type": tid,
                               "mention_count": data.get("mention_count", 0)})
    violations.sort(key=lambda v: -v["mention_count"])
    return type_summary, violations

# ---------------------------------------------------------------------------
# 5. Supersession graph extraction
# ---------------------------------------------------------------------------

SUPERSESSION_PATTERNS = [
    (r"\[CORRECTED\s+(?:by\s+)?VR-(\d+)\]", "corrected_by"),
    (r"\[CORRECTED\s+(?:by\s+)?AUDIT-(\d+)\]", "corrected_by_audit"),
    (r"\[DEPRECATED(?:\s+(?:as of\s+)?(?:v[\d.]+|VR-(\d+)))?\]", "deprecated"),
    (r"\[RETRACTED(?:\s+(?:by\s+)?VR-(\d+))?\]", "retracted"),
    (r"\[SUPERSEDED\s+(?:by\s+)?VR-(\d+)\]", "superseded_by"),
    (r"\[AFFECTED\s+(?:by\s+)?VR-(\d+)\]", "affected_by"),
    (r"\bcorrects?\s+VR-(\d+)\b", "corrects"),
    (r"\bsupersedes?\s+VR-(\d+)\b", "supersedes"),
    (r"\badvances?\s+VR-(\d+)\b", "supersedes"),
    (r"\bretract(?:s|ed)\s+VR-(\d+)\b", "retracts"),
    (r"\bfrom\s+VR-(\d+)\b", "references"),
    (r"\bper\s+VR-(\d+)\b", "references"),
    (r"\bVR-(\d+)\s+(?:period\s+)?correction\b", "correction_of"),
    (r"\bmissing\s+from\s+VR-(\d+)", "correction_of"),
    (r"\bVR-(\d+)\+?\s+scripts?\b", "script_ref"),
    (r"\brefutes?\s+VR-(\d+)\b", "refutes"),
    (r"\bfalsif(?:y|ies|ied)\s+VR-(\d+)\b", "refutes"),
    (r"\bcontradicts?\s+VR-(\d+)\b", "refutes"),
    (r"\boverturns?\s+VR-(\d+)\b", "refutes"),
    (r"\bVR-(\d+)(?:'s|s)?\s+(?:claim|thesis|conclusion)?\s*(?:is\s+)?(?:REFUTED|FALSIFIED|RETRACTED|WRONG|DEAD)", "refutes"),
    (r"\bREOPEN(?:S|ED)\s+VR-(\d+)\b", "reopens"),
    (r"\bVR-(\d+)\s+(?:REOPENED|reopened)\b", "reopens"),
    (r"\bamend(?:s|ed|ing)?\s+VR-(\d+)\b", "amends"),
    (r"\bresolves?\s+(?:the\s+)?(?:open\s+)?(?:ask\s+)?(?:in\s+)?VR-(\d+)\b", "corrects"),
    (r"\bcorrecting\s+VR-(\d+)\b", "corrects"),
    (r"\bdowngrade(?:s|d)?\s+VR-(\d+)\b", "downgrades"),
    (r"\bVR-(\d+)(?:/\d+)*(?:'s|s)?\s+[^.]{0,80}?\bDOWNGRADED\b", "downgrades"),
    (r"\bsoftens?\s+VR-(\d+)\b", "downgrades"),
    (r"\[SOFTENED\s+(?:by\s+)?VR-(\d+)\]", "corrected_by"),
]

_MULTI_VR_RE = domain_ids.MULTI_PRIMARY_RE

# Reference-class relations are benign (they describe a pointer, not a correction) and are
# scanned in the FULL text. Every OTHER relation is "correction-class": for a VR file it is
# extracted ONLY from the metadata fields (title / Status / Supersession), because descriptive
# body prose that merely DESCRIBES another VR's correction ("the wrong-object (VR-826) issue",
# a "[CORRECTED by VR-837]" annotation describing a fix applied elsewhere, etc.) otherwise
# creates a spurious correction-class edge FROM this VR (AUDIT-137: 66% of correction-class
# edges were such body-prose over-matches). AUDIT files keep full-text scanning — their bodies
# legitimately discuss corrections (AUDIT-137 fix recommendation).
REFERENCE_RELATIONS = {"references", "script_ref"}

# Negation guard (AUDIT-171 F4 / AUDIT-173 F1, fixed VR-999): a correction-class verb that is
# NEGATED in the immediately preceding text ("Does not supersede VR-N", "did not correct VR-N",
# "no longer refutes VR-N") must NOT generate a correction edge. The extractor previously matched
# "supersede VR-N" inside "Does not supersede VR-N" verbatim, fabricating false edges (e.g.
# VR-997→VR-996, VR-998→VR-997) that polluted the arc graph (66.7% phantom error density). We look
# back a short window before each correction-class match for a negation cue.
_NEG_WINDOW = 18
_NEG_CUE_RE = re.compile(r"\b(?:not|never|cannot|no\s+longer)\b|n't", re.I)

_META_TITLE_RE = re.compile(r"^#\s+.+$", re.M)
_META_STATUS_RE = re.compile(r"\*\*Status:\*\*[^\n]*")
_META_SUPERSESSION_RE = re.compile(r"\*\*Supersession:\*\*[^\n]*")

def _metadata_text(text):
    """Title + Status + Supersession lines of a VR — where correction-class edges are
    legitimately DECLARED (vs merely described in body prose)."""
    parts = []
    for rx in (_META_TITLE_RE, _META_STATUS_RE, _META_SUPERSESSION_RE):
        m = rx.search(text)
        if m:
            parts.append(m.group(0))
    return "\n".join(parts)

def extract_supersession(vr_id, text):
    """Extract supersession edges. Correction-class edges from a VR are taken ONLY from its
    metadata fields (title/Status/Supersession), avoiding spurious edges from descriptive body
    prose (AUDIT-137); reference-class edges and all AUDIT-file edges use the full text."""
    edges = []
    is_audit = domain_ids.is_audit(vr_id)
    meta_text = _metadata_text(text)
    for pattern, relation in SUPERSESSION_PATTERNS:
        # Reference-class edges scan full text for both VR and AUDIT files.
        # Correction-class edges scan metadata-only for both — AUDIT files discuss
        # corrections in body prose but never PERFORM them (AUDIT-159 fix: was giving
        # AUDIT files full-text scan for all patterns, causing recursive false-positives
        # when audit body text mentioning "supersedes VR-N" generated AUDIT→VR edges).
        scan_text = text if relation in REFERENCE_RELATIONS else meta_text
        for m in re.finditer(pattern, scan_text, re.I):
            # Negation guard: skip correction-class verbs negated in the preceding window
            # ("Does not supersede VR-N"). Reference-class pointers are benign, not guarded.
            if relation not in REFERENCE_RELATIONS:
                pre = scan_text[max(0, m.start() - _NEG_WINDOW):m.start()]
                if _NEG_CUE_RE.search(pre):
                    continue
            target = m.group(1) if m.lastindex and m.group(1) else None
            if target:
                full_span = m.group(0)
                all_vrs = _MULTI_VR_RE.findall(full_span)
                if len(all_vrs) > 1:
                    for vr_num in all_vrs:
                        edges.append((relation, f"{domain_ids.PRIMARY}-{vr_num}"))
                else:
                    # Namespace-aware target: a pattern that matched "<AUDIT>-N" (e.g.
                    # "closes AUDIT-3", "[CORRECTED by AUDIT-3]") targets the AUDIT
                    # namespace — minting PRIMARY-N here fabricated an edge to an
                    # unrelated primary doc that happened to share the number.
                    ns = domain_ids.AUDIT if f"{domain_ids.AUDIT}-{target}" in full_span \
                        else domain_ids.PRIMARY
                    edges.append((relation, f"{ns}-{target}"))
            elif relation == "deprecated":
                edges.append(("self_deprecated", vr_id))
    return edges

# ---------------------------------------------------------------------------
# 6. Status classification
# ---------------------------------------------------------------------------

def classify_status(meta, text):
    """Classify VR status: active, deprecated, retracted, corrected.

    Distinguishes between a VR that IS retracted vs one that RETRACTS something else.
    """
    vr_id = meta.get("id") or ""
    title = (meta.get("title") or "").lower()
    status_field = (meta.get("status") or "").lower()

    if re.search(r"\[retracted\b", status_field, re.I):
        return "retracted"
    if "deprecat" in status_field:
        return "deprecated"

    if "retracted" in title:
        if "correction" in title or "corrects" in title or "corrected" in title:
            return "active"
        return "retracted"

    bracket_retracted = re.findall(r"\[RETRACTED\b", text, re.I)
    if bracket_retracted:
        self_retracted = any(
            re.search(rf"(?:this\s+VR|{re.escape(vr_id)})\s+.*retracted", line, re.I)
            for line in text.split("\n")
            if "[retracted" in line.lower()
        )
        if self_retracted:
            return "retracted"

    dep_count = len(re.findall(r"\[deprecated", text, re.I))
    rest_count = len(re.findall(r"\[restored", text, re.I))
    if dep_count > 0 and dep_count > rest_count:
        self_deprecated = any(
            re.search(rf"(?:this\s+VR|{re.escape(vr_id)})\s+.*deprecated", line, re.I)
            for line in text.split("\n")
            if "[deprecated" in line.lower()
        )
        if self_deprecated or re.search(r"^##\s.*deprecated", text, re.I | re.M):
            return "deprecated"

    if "correct" in status_field and "audit" in status_field:
        return "corrected"
    return "active"

# ---------------------------------------------------------------------------
# 6b. Claim consequentiality extraction (DRIFT-inspired)
# ---------------------------------------------------------------------------

CLAIM_PATTERNS = [
    (r"\[V\]", "VERIFIED"),
    (r"\[P\]", "PROVED"),
    (r"\[C\]", "CONJECTURED"),
    (r"\[O\]", "OPEN"),
]

BODY_SIGNAL_PATTERNS = [
    (r"\bTHEOREM\b", "FINALIZED"),
    (r"\bPROVED\b", "FINALIZED"),
    (r"\bSETTLED\b", "FINALIZED"),
    (r"\bRETRACTED\b", "SUPERSEDED"),
    (r"\bDEPRECATED\b", "SUPERSEDED"),
    (r"\bCORRECTED\b", "SUPERSEDED"),
    (r"\bREFUTED\b", "DEAD"),
    (r"\bFALSIFIED\b", "DEAD"),
    (r"\bWRONG\b", "DEAD"),
    (r"\bhypothesis\b", "TENTATIVE"),
    (r"\bconjecture[d]?\b", "TENTATIVE"),
    (r"\bpattern\b", "TENTATIVE"),
    (r"\bobservation\b", "TENTATIVE"),
]

def extract_claim_status(meta, text):
    """Classify VR claim commitment level (DRIFT Claim Keeper analog)."""
    status_line = meta.get("status") or ""
    primary = "UNKNOWN"
    for pattern, label in CLAIM_PATTERNS:
        if re.search(pattern, status_line):
            primary = label
            break

    body_signals = set()
    for pattern, label in BODY_SIGNAL_PATTERNS:
        if re.search(pattern, text):
            body_signals.add(label)

    if "DEAD" in body_signals and "FINALIZED" in body_signals:
        body_signals.discard("DEAD")
    if "SUPERSEDED" in body_signals and primary in ("VERIFIED", "PROVED"):
        pass

    return {
        "primary": primary,
        "body_signals": sorted(body_signals),
        "has_retraction": "SUPERSEDED" in body_signals or "DEAD" in body_signals,
    }

# ---------------------------------------------------------------------------
# 7. Chunk builder
# ---------------------------------------------------------------------------

def build_chunks(meta, sections, text, status):
    """Build section-level chunks with metadata."""
    chunks = []
    vr_id = meta["id"]
    all_entities = extract_entities(text)
    supersession = extract_supersession(vr_id, text)

    for i, (header, body) in enumerate(sections):
        if not body.strip():
            continue
        content = f"## {header}\n\n{body}"
        if len(content) > 4000:
            sub_parts = re.split(r"(?=^###\s)", content, flags=re.M)
            for j, sp in enumerate(sub_parts):
                if sp.strip():
                    chunk_id = f"{vr_id}:s{i}:p{j}"
                    chunks.append(_make_chunk(chunk_id, vr_id, meta, header, sp.strip(),
                                              status, supersession, extract_entities(sp)))
        else:
            chunk_id = f"{vr_id}:s{i}"
            chunks.append(_make_chunk(chunk_id, vr_id, meta, header, content,
                                      status, supersession, extract_entities(content)))

    if not chunks and text.strip():
        chunks.append(_make_chunk(f"{vr_id}:full", vr_id, meta, "full", text[:4000],
                                  status, supersession, all_entities))
    return chunks

def _make_chunk(chunk_id, vr_id, meta, section, content, status, supersession, entities):
    content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
    return {
        "chunk_id": chunk_id,
        "vr_id": vr_id,
        "section": section,
        "content": content,
        "date": meta.get("date"),
        "iter": meta.get("iter"),
        "status": status,
        "supersession": supersession,
        "entities": sorted(entities),
        "content_hash": content_hash,
    }

# ---------------------------------------------------------------------------
# 8. Entity registry builder
# ---------------------------------------------------------------------------

def build_entity_registry(all_chunks):
    """Build entity registry: each named object → history chain of VRs that mention it."""
    registry = defaultdict(lambda: {
        "mentions": [],
        "values": [],
        "first_seen": None,
        "last_seen": None,
    })

    for chunk in all_chunks:
        vr_id = chunk["vr_id"]
        date = chunk.get("date")
        status = chunk["status"]
        for entity in chunk["entities"]:
            if entity.startswith("VR-") or entity.startswith("AUDIT-"):
                continue
            entry = registry[entity]
            mention = {"vr_id": vr_id, "date": date, "status": status,
                       "section": chunk["section"]}
            entry["mentions"].append(mention)
            if entry["first_seen"] is None or (date and (entry["first_seen"] is None or date < entry["first_seen"])):
                entry["first_seen"] = date
            if entry["last_seen"] is None or (date and date > (entry["last_seen"] or "")):
                entry["last_seen"] = date

    # Quantity value-history. ENTITY_PATTERNS keys the registry by the assignment STRING
    # ("rank=4"), so the bare quantity name ("rank") is the registry key under which each
    # quantity's value HISTORY accumulates (fix for the empty-values[] bug). The quantities,
    # their key/value capture groups, and their plausibility bounds come from QUANTITIES
    # (domain_config.json, with embedded fallback) — a different program declares its own
    # quantities without editing this code. The bound only drops stray integers (rank=22,
    # sha=0); empirically the literal rank=/sha= tokens are clean (rank 0..9; |Sha| orders).
    def _quantity_value_ok(q, val):
        try:
            n = int(val)
        except (TypeError, ValueError):
            return False
        lo, hi = q.get("min"), q.get("max")
        return (lo is None or n >= lo) and (hi is None or n <= hi)
    for chunk in all_chunks:
        for qname, q in QUANTITIES.items():
            for m in re.finditer(q["pattern"], chunk["content"]):
                key = q["key_literal"] if q.get("key_literal") else m.group(q["key_group"])
                val = m.group(q["val_group"])
                if not _quantity_value_ok(q, val):
                    continue
                entry = registry[key]  # bare-name quantity bucket (created on demand)
                v_rec = {
                    "value": val,
                    "vr_id": chunk["vr_id"],
                    "date": chunk.get("date"),
                    "status": chunk["status"],
                }
                if chunk.get("party"):
                    v_rec["party"] = chunk["party"]   # P6 M4: cross-party attribution
                entry["values"].append(v_rec)
                m_rec = {"vr_id": chunk["vr_id"], "date": chunk.get("date"),
                         "status": chunk["status"], "section": chunk["section"]}
                if chunk.get("party"):
                    m_rec["party"] = chunk["party"]   # P6 M4: cross-party attribution
                entry["mentions"].append(m_rec)
                d = chunk.get("date")
                if d and (entry["first_seen"] is None or d < entry["first_seen"]):
                    entry["first_seen"] = d
                if d and d > (entry["last_seen"] or ""):
                    entry["last_seen"] = d

    deduped = {}
    for entity, data in registry.items():
        seen = set()
        unique_mentions = []
        for mention in data["mentions"]:
            key = (mention["vr_id"], mention["section"])
            if key not in seen:
                seen.add(key)
                unique_mentions.append(mention)
        data["mentions"] = unique_mentions
        data["mention_count"] = len(unique_mentions)
        if data["values"]:  # collapse within-VR repeats; keep one per (vr_id, value)
            vseen, uvals = set(), []
            for v in data["values"]:
                vk = (v["vr_id"], v["value"])
                if vk not in vseen:
                    vseen.add(vk)
                    uvals.append(v)
            data["values"] = uvals
        deduped[entity] = data

    return dict(sorted(deduped.items()))

# ---------------------------------------------------------------------------
# 9. Supersession graph builder
# ---------------------------------------------------------------------------

# PROV / nanopub vocabulary alignment for the supersession relation taxonomy (axis-3 borrow,
# docs/CONCEPT_COVERAGE_IMPLEMENTATION_INDEX §3). The local taxonomy is RICHER than W3C PROV /
# nanopub `npx:` (it distinguishes amends / downgrades / reopens that the standard vocabularies
# collapse), so this is an interop MAP, not a replacement: every relation → its nearest PROV term
# + nanopub term, with `exact=False` where the local verb carries a distinction the standard
# vocab cannot express (so a consumer translating to PROV is TOLD where fidelity is lost rather
# than silently flattened). Emitted into supersession.json so it travels with the graph.
RELATION_PROV_MAP = {
    # revision class — a later assertion revises / replaces an earlier one
    "corrects":           {"prov": "prov:wasRevisionOf",   "nanopub": "npx:supersedes", "exact": True},
    "corrected_by":       {"prov": "prov:wasRevisionOf",   "nanopub": "npx:supersedes", "exact": True},
    "corrected_by_audit": {"prov": "prov:wasRevisionOf",   "nanopub": "npx:supersedes", "exact": True},
    "correction_of":      {"prov": "prov:wasRevisionOf",   "nanopub": "npx:supersedes", "exact": True},
    "supersedes":         {"prov": "prov:wasRevisionOf",   "nanopub": "npx:supersedes", "exact": True},
    "superseded_by":      {"prov": "prov:wasRevisionOf",   "nanopub": "npx:supersedes", "exact": True},
    "amends":             {"prov": "prov:wasRevisionOf",   "nanopub": "npx:supersedes", "exact": False},  # partial revision, not full replace
    "downgrades":         {"prov": "prov:wasRevisionOf",   "nanopub": "npx:supersedes", "exact": False},  # weakens strength — no exact PROV verb
    # invalidation class — an assertion is killed
    "refutes":            {"prov": "prov:wasInvalidatedBy", "nanopub": "npx:retracts",   "exact": True},
    "retracts":           {"prov": "prov:wasInvalidatedBy", "nanopub": "npx:retracts",   "exact": True},
    "retracted":          {"prov": "prov:wasInvalidatedBy", "nanopub": "npx:retracts",   "exact": True},
    "deprecated":         {"prov": "prov:wasInvalidatedBy", "nanopub": "npx:retracts",   "exact": False}, # soft retraction
    "self_deprecated":    {"prov": "prov:wasInvalidatedBy", "nanopub": "npx:retracts",   "exact": False},
    # influence class — neither replace nor kill, but a dependency the standard vocab barely covers
    "reopens":            {"prov": "prov:wasInfluencedBy",  "nanopub": None,             "exact": False}, # richer than PROV — no analogue
    "affected_by":        {"prov": "prov:wasInfluencedBy",  "nanopub": None,             "exact": True},
    "corroborates":       {"prov": "prov:wasInfluencedBy",  "nanopub": None,             "exact": False}, # POSITIVE support (scite "supporting") — PROV/nanopub have no confirm verb
    "closes":             {"prov": "prov:wasInfluencedBy",  "nanopub": None,             "exact": False}, # resolves an open item — no exact PROV verb
    "closes_audit":       {"prov": "prov:wasInfluencedBy",  "nanopub": None,             "exact": False},
    # derivation / citation class — benign pointer (REFERENCE_RELATIONS)
    "references":         {"prov": "prov:wasDerivedFrom",   "nanopub": None,             "exact": True},
    "script_ref":         {"prov": "prov:used",             "nanopub": None,             "exact": True},
}

def build_supersession_graph(all_chunks):
    """Build directed supersession graph from all chunks."""
    edges = []
    seen = set()
    for chunk in all_chunks:
        vr_id = chunk["vr_id"]
        for relation, target in chunk["supersession"]:
            edge = (vr_id, relation, target)
            if edge not in seen:
                seen.add(edge)
                edges.append({"source": vr_id, "relation": relation, "target": target})
    return edges

# ---------------------------------------------------------------------------
# 10. Arc detection
# ---------------------------------------------------------------------------

CORRECTION_RELATIONS = {
    "corrects", "refutes", "retracts", "downgrades", "supersedes",
    "amends", "correction_of", "corrected_by", "corrected_by_audit",
}

# Quantity value-history config (embedded fallback; overridden by domain_config.json).
QUANTITIES = {
    "eps_k": {"pattern": r"(eps_k\d)=(\d+)", "key_group": 1, "key_literal": None, "val_group": 2, "min": None, "max": None},
    "rank":  {"pattern": r"(rank)=(\d+)",    "key_group": None, "key_literal": "rank", "val_group": 2, "min": 0, "max": 9},
    "sha":   {"pattern": r"sha=(\d+)",       "key_group": None, "key_literal": "sha",  "val_group": 1, "min": 1, "max": 4096},
}

# ---------------------------------------------------------------------------
# Domain-config override (PORTABILITY). The constants above (ENTITY_PATTERNS,
# SUPERSESSION_PATTERNS, REFERENCE/CORRECTION_RELATIONS, TYPE_SCHEMA, QUANTITIES)
# are the program's DOMAIN vocabulary. If scripts/rag/domain_config.json exists they
# are rebuilt from it, so porting the engine to another research program is "swap the
# config + the ontology seeds", not "edit the engine". The embedded values are a
# self-contained fallback so the tool runs with no config. {n} in an entity template =
# regex group n.
# ---------------------------------------------------------------------------

def _render_template(tmpl):
    def extract(m):
        out = tmpl
        for i in range(1, (m.re.groups or 0) + 1):
            g = m.group(i)
            out = out.replace("{%d}" % i, g if g is not None else "")
        return out
    return extract

def _apply_domain_config():
    global ENTITY_PATTERNS, SUPERSESSION_PATTERNS, REFERENCE_RELATIONS
    global CORRECTION_RELATIONS, TYPE_SCHEMA, _TYPE_MATCH, _TYPE_VALID, QUANTITIES
    global METHOD_INDICATORS, METHOD_LIFECYCLE
    cfg_path = SEED_DIR / "domain_config.json"
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return  # keep embedded defaults
    if cfg.get("entity_families"):
        ENTITY_PATTERNS = [(e["pattern"], _render_template(e["template"])) for e in cfg["entity_families"]]
    if cfg.get("supersession_patterns"):
        SUPERSESSION_PATTERNS = [(s["pattern"], s["relation"]) for s in cfg["supersession_patterns"]]
    if cfg.get("reference_relations"):
        REFERENCE_RELATIONS = set(cfg["reference_relations"])
    if cfg.get("correction_relations"):
        CORRECTION_RELATIONS = set(cfg["correction_relations"])
    if cfg.get("type_schema"):
        TYPE_SCHEMA = cfg["type_schema"]
        _TYPE_MATCH = [(tid, re.compile(spec["match"])) for tid, spec in TYPE_SCHEMA.items()]
        _TYPE_VALID = {tid: re.compile(spec["valid"]) for tid, spec in TYPE_SCHEMA.items()}
    if cfg.get("method_indicators"):
        METHOD_INDICATORS = [(m["pattern"], m["id"]) for m in cfg["method_indicators"]]
    if cfg.get("method_lifecycle"):
        METHOD_LIFECYCLE = [(m["pattern"], m["state"]) for m in cfg["method_lifecycle"]]
    if cfg.get("quantities"):
        QUANTITIES = {q["name"]: {"pattern": q["value_pattern"], "key_group": q.get("key_group"),
                                  "key_literal": q.get("key_literal"), "val_group": q["val_group"],
                                  "min": (q["bound"][0] if q.get("bound") else None),
                                  "max": (q["bound"][1] if q.get("bound") else None)}
                      for q in cfg["quantities"]}

# (invoked below, after ALL overridable vocabulary constants are defined)

def _vr_number(vr_id):
    """Extract numeric ID from PRIMARY-N or AUDIT-N, or None."""
    return domain_ids.doc_number(vr_id)

def build_arcs(graph_edges, all_meta, all_chunks):
    """Detect research arcs: groups of VRs connected by correction edges + entity overlap.

    v2 (AUDIT-139 Fix A): entity-overlap expansion uses RARE entities only
    (doc_freq < 20) to prevent mega-arcs. Large components (>80 VRs) are split
    at temporal gaps (>20 VR-numbers between consecutive members). Outline-ID
    adjacency extends arc boundaries by ±5 VRs.
    """
    corr_edges = [e for e in graph_edges if e["relation"] in CORRECTION_RELATIONS]

    adj = defaultdict(set)
    for e in corr_edges:
        adj[e["source"]].add(e["target"])
        adj[e["target"]].add(e["source"])

    visited = set()
    components = []
    for node in adj:
        if node in visited:
            continue
        comp = set()
        queue = [node]
        while queue:
            n = queue.pop()
            if n in visited:
                continue
            visited.add(n)
            comp.add(n)
            for nb in adj[n]:
                if nb not in visited:
                    queue.append(nb)
        if len(comp) >= 2:
            components.append(comp)

    vr_entities = defaultdict(set)
    for chunk in all_chunks:
        vid = chunk["vr_id"]
        for ent in chunk.get("entities", []):
            if not ent.startswith("VR-") and not ent.startswith("AUDIT-") and not ent.startswith("§"):
                vr_entities[vid].add(ent)

    entity_doc_freq = defaultdict(int)
    for vid, ents in vr_entities.items():
        for ent in ents:
            entity_doc_freq[ent] += 1

    outline_map = {}
    for m in all_meta:
        mid = m.get("id", "")
        outline_ids = m.get("outline_ids", "") or ""
        if outline_ids:
            outline_map[mid] = set(re.findall(r"§[\d.]+", outline_ids))

    expanded = []
    for comp in components:
        comp_nums = [_vr_number(v) for v in comp if _vr_number(v) is not None]
        if not comp_nums:
            expanded.append(comp)
            continue

        for _round in range(3):
            added = False
            lo = min(_vr_number(v) for v in comp if _vr_number(v) is not None)
            hi = max(_vr_number(v) for v in comp if _vr_number(v) is not None)

            comp_rare_entities = set()
            for vid in comp:
                for ent in vr_entities.get(vid, set()):
                    if entity_doc_freq[ent] < 20:
                        comp_rare_entities.add(ent)
            comp_outlines = set()
            for vid in comp:
                comp_outlines |= outline_map.get(vid, set())

            for vid, ents in vr_entities.items():
                if vid in comp:
                    continue
                vn = _vr_number(vid)
                if vn is None:
                    continue
                if not (lo - 30 <= vn <= hi + 30):
                    continue
                rare_overlap = sum(1 for e in ents if e in comp_rare_entities and entity_doc_freq[e] < 20)
                if rare_overlap >= 3:
                    comp.add(vid)
                    added = True
                    continue
                vid_outlines = outline_map.get(vid, set())
                if vid_outlines & comp_outlines and (abs(vn - hi) <= 3 or abs(vn - lo) <= 3):
                    comp.add(vid)
                    added = True
            if not added:
                break

        expanded.append(comp)

    split_expanded = []
    for comp in expanded:
        if len(comp) <= 50:
            split_expanded.append(comp)
            continue
        members = sorted(comp, key=lambda v: (_vr_number(v) or 0, v))  # id tie-break: byte-deterministic under hash randomization
        sub = {members[0]}
        for i in range(1, len(members)):
            prev_n = _vr_number(members[i-1]) or 0
            curr_n = _vr_number(members[i]) or 0
            if curr_n - prev_n > 20:
                if len(sub) >= 2:
                    split_expanded.append(sub)
                sub = set()
            sub.add(members[i])
        if len(sub) >= 2:
            split_expanded.append(sub)

    expanded = split_expanded

    title_map = {}
    date_map = {}
    for m in all_meta:
        mid = m.get("id", "")
        title_map[mid] = m.get("title", "")
        date_map[mid] = m.get("date", "")

    arcs = []
    for comp in expanded:
        members = sorted(comp, key=lambda v: (_vr_number(v) or 0, v))  # id tie-break: byte-deterministic under hash randomization
        nums = [_vr_number(v) for v in members if _vr_number(v) is not None]
        if not nums:
            continue

        arc_corr = [e for e in corr_edges
                     if e["source"] in comp and e["target"] in comp]
        n_corrections = len(arc_corr)
        size = len(members)
        error_density = n_corrections / size if size else 0

        latencies = []
        for e in arc_corr:
            sn = _vr_number(e["source"])
            tn = _vr_number(e["target"])
            if sn and tn and sn > tn:
                latencies.append(sn - tn)

        entity_counts = defaultdict(int)
        for vid in comp:
            for ent in vr_entities.get(vid, set()):
                entity_counts[ent] += 1
        # stable tie-break by entity name so rebuilds are byte-deterministic (equal-count
        # entities were ordered by set/dict iteration under hash randomization otherwise)
        key_entities = sorted(entity_counts.items(), key=lambda x: (-x[1], x[0]))[:10]

        state = _classify_arc_state(members, arc_corr, graph_edges, all_meta)

        arcs.append({
            "id": f"arc-{min(nums)}-{max(nums)}",
            "span": f"{members[0]}..{members[-1]}",
            "members": members,
            "size": size,
            "corrections": n_corrections,
            "correction_edges": arc_corr,
            "error_density": round(error_density, 3),
            "median_latency": sorted(latencies)[len(latencies)//2] if latencies else None,
            "state": state,
            "key_entities": [{"entity": e, "count": c} for e, c in key_entities],
            "dates": {"first": date_map.get(members[0], ""), "last": date_map.get(members[-1], "")},
        })

    arcs.sort(key=lambda a: -a["size"])
    return arcs


def _classify_arc_state(members, arc_corr, all_edges, all_meta):
    """Classify arc state: converged, oscillating, diagnosed, stalled, exploring."""
    if len(members) < 5:
        return "exploring"

    title_map = {m.get("id", ""): ((m.get("title") or "") + " " + (m.get("status") or "")).lower()
                 for m in all_meta}

    tail = members[-5:] if len(members) >= 5 else members
    for m in reversed(tail):
        m_text = title_map.get(m, "")
        if any(kw in m_text for kw in ("wrong object", "diagnosed", "downgrade", "rebuild")):
            return "diagnosed"

    from collections import Counter as _Counter
    targets = [e["target"] for e in arc_corr]
    target_counts = _Counter(targets)
    multi_corrected = [t for t, c in target_counts.items() if c >= 3]
    if multi_corrected:
        return "oscillating"

    recent = members[-3:] if len(members) >= 3 else members
    recent_corrected = any(e["target"] in recent for e in arc_corr)
    if not recent_corrected:
        return "converged"

    if len(members) > 10:
        return "stalled"

    return "exploring"


# ---------------------------------------------------------------------------
# 11. Method registry
# ---------------------------------------------------------------------------

METHOD_INDICATORS = [
    (r"\b(descent\s+engine|evaluator|Θ[₂₃₄]\s+evaluator)\b", "descent_engine"),
    (r"\b(analytic\s+(?:\|?Sha\|?|BSD)|analytic_sha)\b", "analytic_bsd"),
    (r"\bMC-free\s+(?:bound|≥|isogeny|class\s+ratio|ratio)\b", "mc_free_bound"),
    (r"\b(Lean\s+formal|lake\s+build|lean4)\b", "lean_formalization"),
    (r"\b(CT\s+pairing|Cassels.Tate\s+pairing)\b", "ct_pairing"),
    (r"\b(conic_param|build_c2|constructor)\b", "covering_constructor"),
    (r"(cm_phi_selmer|\bphi.selmer\b|φ.Selmer|φ.selmer|phisel[gG]?\b)", "phi_selmer"),
    (r"\b(F-evaluator|pushout\s+closure)\b", "f_evaluator"),
    (r"\b(gate\s+discipline|PROVISIONAL.*HOLD)\b", "gate_discipline"),
    (r"\b(Im\s*α\s*=\s*ker\s*Θ|dimension.sequence)\b", "dim_sequence_route"),
]

METHOD_LIFECYCLE = [
    (r"\bproposed\b|\bkickoff\b|\blaunched\b", "proposed"),
    (r"\bimplemented\b|\bbuilt\b|\bassembled\b|\bported\b", "implemented"),
    (r"\bcalibrat(?:ed|ion)\b|\bvalidat(?:ed|ion)\b", "calibrated"),
    (r"\bconfirmed\b|\bverified\b|\bpassed\b|\breproduced\b", "validated"),
    (r"\bfailed\b|\bwrong\b|\bbug\b|\bbroken\b|\brefuted\b", "failed"),
    (r"\bdiagnosed\b|\broot.cause\b|\bwrong.object\b", "diagnosed"),
    (r"\brebuilt\b", "rebuild_specified"),  # narrowed (VR-1002, AUDIT-178 F1): dropped \brebuild\b
    # ("RAG rebuild"/"rebuild.sh" = script, not a method transition) and \bfix(?:ed)?\b ("gap fixed",
    # "extractor fixed" = generic English). Only past-tense "was rebuilt" is a genuine lifecycle event.
    (r"\bretracted\b|\bdowngraded?\b", "retracted"),
]

_apply_domain_config()   # must run AFTER every overridable constant above is defined


def extract_methods(all_meta, all_chunks):
    """Extract method/instrument lifecycle from VR corpus.

    v2 (AUDIT-139 Fix B): lifecycle keywords matched only within ±200 chars
    of the method indicator (proximity window), preventing cross-method
    contamination. has_produced_wrong_answer uses metadata-only extraction
    (title + status lines) to avoid body-text over-match.
    """
    method_events = defaultdict(list)

    vr_texts = defaultdict(str)
    for chunk in all_chunks:
        vr_texts[chunk["vr_id"]] += " " + chunk.get("content", "")

    date_map = {m.get("id", ""): m.get("date", "") for m in all_meta}
    title_map = {m.get("id", ""): m.get("title", "") for m in all_meta}
    status_map = {m.get("id", ""): m.get("status", "") for m in all_meta}

    for vr_id, text in vr_texts.items():
        # AUDIT files DESCRIBE method lifecycle states (assessment), they do not PERFORM
        # the work that advances them. Indexing their descriptive prose as lifecycle events
        # fabricates phantom states (AUDIT-171 F5 / AUDIT-173 F4 / AUDIT-175 F4: AUDIT-165's
        # text "mc_free_bound ... stuck at rebuild_specified" was re-indexed as a NEW
        # rebuild_specified event, masking the true calibrated/validated state from VR-990/993).
        # Lifecycle events come from VRs only (fixed VR-1001). [analogous to the supersession
        # negation guard, VR-999]
        if vr_id.startswith("AUDIT"):
            continue
        title = title_map.get(vr_id) or ""
        full_text = (title + " " + text)

        for pattern, method_id in METHOD_INDICATORS:
            matches = list(re.finditer(pattern, full_text, re.I))
            if not matches:
                continue

            for match in matches:
                start = max(0, match.start() - 200)
                end = min(len(full_text), match.end() + 200)
                context = full_text[start:end].lower()

                for lc_pattern, lc_state in METHOD_LIFECYCLE:
                    if re.search(lc_pattern, context, re.I):
                        method_events[method_id].append({
                            "vr_id": vr_id,
                            "state": lc_state,
                            "date": date_map.get(vr_id, ""),
                        })

    META_METHODS = {"gate_discipline"}
    method_metadata_failed = defaultdict(bool)
    fail_re = re.compile(r"\bfailed\b|\bwrong\b|\bretracted\b|\bwrong.object\b|\bbug\b", re.I)
    for vr_id in vr_texts:
        metadata_text = ((title_map.get(vr_id) or "") + " " + (status_map.get(vr_id) or "")).lower()
        for pattern, method_id in METHOD_INDICATORS:
            if method_id in META_METHODS:
                continue
            match = re.search(pattern, metadata_text, re.I)
            if match:
                start = max(0, match.start() - 120)
                end = min(len(metadata_text), match.end() + 120)
                nearby = metadata_text[start:end]
                if fail_re.search(nearby):
                    method_metadata_failed[method_id] = True

    registry = {}
    for method_id, events in method_events.items():
        events.sort(key=lambda e: (_vr_number(e["vr_id"]) or 0))
        current_state = events[-1]["state"] if events else "unknown"

        unique_events = []
        seen = set()
        for e in events:
            key = (e["vr_id"], e["state"])
            if key not in seen:
                seen.add(key)
                unique_events.append(e)

        registry[method_id] = {
            "id": method_id,
            "current_state": current_state,
            "has_produced_wrong_answer": method_metadata_failed.get(method_id, False),
            "events": unique_events,
            "defining_vrs": list(dict.fromkeys(e["vr_id"] for e in unique_events)),
            "event_count": len(unique_events),
        }

    return registry


# ---------------------------------------------------------------------------
# 12. Per-claim epistemic stratum
# ---------------------------------------------------------------------------

STRATUM_MARKERS = [
    (r"\bPROVED\b|\bRIGOROUS\b|\bMC-free\b|\btheorem\b|\bLean\b", "proved"),
    (r"\bVERIFIED\b|\breproduced\b|\bconfirmed\b|\b57\s+digits\b|\bvalidated\b", "verified"),
    (r"\bPREDICT(?:ED|ION)\b|\banalytic\s+BSD\b|\bnot\s+a\s+proof\b|\bpredicts\b", "predicted"),
    (r"\bOPEN\b|\bunproven\b|\bnot\s+(?:MC-free-)?proved\b|\bSTILL\s+OPEN\b", "open"),
    (r"\bRETRACTED\b|\bWRONG\b|\bfalse.zero\b|\bwrong\s+object\b|\bgarbage\b", "retracted"),
]

CLAIM_ASSERTION_RE = re.compile(
    r"[^.]*(?:\|Sha\||dim\s+S|rank|≥|≤|=\s*\d|eps_k|ε)[^.]*\.",
    re.I
)

def extract_claim_strata(text):
    """Extract per-claim epistemic strata from text. Returns list of {claim, stratum}."""
    strata = []
    sentences = re.split(r"(?<=[.!])\s+", text)

    for sent in sentences:
        if not CLAIM_ASSERTION_RE.search(sent):
            continue

        best_stratum = None
        best_priority = 99
        priorities = {"retracted": 0, "open": 1, "predicted": 2, "verified": 3, "proved": 4}

        for pattern, stratum in STRATUM_MARKERS:
            if re.search(pattern, sent):
                p = priorities.get(stratum, 5)
                if p < best_priority:
                    best_priority = p
                    best_stratum = stratum

        if best_stratum:
            claim_text = sent.strip()[:200]
            strata.append({"claim": claim_text, "stratum": best_stratum})

    return strata


# ---------------------------------------------------------------------------
# 13. Concept emergence
# ---------------------------------------------------------------------------

CONCEPT_RE = re.compile(
    r"\*\*([A-Za-z][A-Za-z0-9 _-]{3,40})\*\*"
    r"|"
    r'"([A-Za-z][A-Za-z0-9 _-]{3,40})"'
    r"|"
    r"'([A-Za-z][A-Za-z0-9 _-]{3,40})'"
    r"|"
    r"\b([A-Z]{2,}(?:[ _-][A-Z]{2,})+)\b"
)

BASE_VOCABULARY = {
    "the", "and", "for", "not", "but", "with", "this", "that", "from",
    "edit protocol", "version history", "open work", "significance",
    "plan", "result", "analysis", "date", "status", "source",
    "what this audit does not do", "what this does not do",
    "reproducer", "lean", "supersession", "outline id",
    "grounding", "version", "changes", "finding",
    "this vr", "key finding", "key result", "key identity",
    "all three", "in progress", "root cause", "honest assessment",
    "self-correction", "gap vr", "note vr", "proved vr", "pari vr",
    "critical finding", "critical correction", "paper update",
    "paper outline update", "annotated audit", "edit-protocol",
    "audit pending", "audit-pending", "partially resolved",
    "partially refuted", "partially verified", "independently verified",
    "queue agent", "slb message", "slb add", "corrects vr",
    "refutes vr", "ruled out", "stack overflow", "gb gcp", "gb ram",
    "block 2", "block 3", "block 4", "gcp vm", "track a", "track b",
    "track c", "cloud lfun computation", "pari computation",
    "gap computation", "gap all", "period correction vr",
    "explicit user approval", "paper gate", "leaning infinite",
    "structurally dry", "exact match",
    "does not", "this iteration", "and vr", "finding c", "finding b",
    "finding a", "finding d", "finding e", "finding f", "all four",
    "exactly one", "corrected by", "rank 1", "rank 2", "rank 0",
    "dim 1", "dim 2", "dim 3", "dim 4", "dim 0", "block 1",
    "root number", "root numbers", "not a", "not the",
    "see vr", "per vr", "via vr", "from vr", "the vr",
    "is the", "is not", "is a", "is an", "has a", "has the",
    "and the", "and a", "for the", "for a", "in the", "in a",
    "of the", "of a", "on the", "at the", "to the", "by the",
    "with the", "with a", "not yet", "so far", "at least",
    "as the", "as a", "if the", "if a", "or the", "or a",
    "one of", "all of", "each of", "two of", "three of",
    "none of", "both of", "most of", "some of",
}

def _normalize_concept(term):
    """Normalize concept surface forms: lowercase, strip hyphens, collapse whitespace."""
    t = term.lower().strip()
    t = re.sub(r"[-_]", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t


def extract_concepts(all_chunks, all_meta):
    """Track concept emergence: when terms first appear and how they propagate.

    v2 (AUDIT-139 Fix C): expanded stop-list (generic audit/VR phrases),
    surface-form normalization (hyphens→spaces), and a second pass that
    counts plain-text occurrences of established concepts (≥2 bold/quoted
    mentions) to fix the undercounting problem.
    """
    concept_vrs = defaultdict(list)

    for chunk in all_chunks:
        vr_id = chunk["vr_id"]
        text = chunk.get("content", "")

        for m in CONCEPT_RE.finditer(text):
            term = (m.group(1) or m.group(2) or m.group(3) or m.group(4) or "").strip().lower()
            term = _normalize_concept(term)

            if term in BASE_VOCABULARY:
                continue
            if len(term) < 5 or (len(term.split()) < 2 and "-" not in term):
                continue
            if re.match(r"^(vr|audit)\s*\d+", term):
                continue

            concept_vrs[term].append(vr_id)

    initial_concepts = {term for term, vrs in concept_vrs.items()
                        if len(set(vrs)) >= 2}

    vr_texts = defaultdict(str)
    for chunk in all_chunks:
        vr_texts[chunk["vr_id"]] += " " + chunk.get("content", "").lower()

    for term in initial_concepts:
        pattern = re.compile(re.escape(term), re.I)
        for vr_id, text in vr_texts.items():
            if vr_id not in concept_vrs[term] and pattern.search(text):
                concept_vrs[term].append(vr_id)

    date_map = {m.get("id", ""): m.get("date", "") for m in all_meta}

    concepts = []
    for term, vr_list in concept_vrs.items():
        unique_vrs = list(dict.fromkeys(vr_list))
        if len(unique_vrs) < 2:
            continue

        unique_vrs.sort(key=lambda v: (_vr_number(v) or 0))
        intro_vr = unique_vrs[0]
        propagation = len(unique_vrs)

        recent_vrs = [v for v in unique_vrs if (_vr_number(v) or 0) > 750]
        if propagation >= 5 and recent_vrs:
            continuity = "established"
        elif propagation <= 3:
            continuity = "ephemeral"
        else:
            continuity = "emerging"

        concepts.append({
            "term": term,
            "introduced_in": intro_vr,
            "introduction_date": date_map.get(intro_vr, ""),
            "propagation_count": propagation,
            "continuity": continuity,
            "vrs": unique_vrs[:20],
        })

    concepts.sort(key=lambda c: -c["propagation_count"])
    return concepts


# ---------------------------------------------------------------------------
# 14. Main pipeline
# ---------------------------------------------------------------------------

def run():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    files = discover_files()
    print(f"Discovered {len(files)} files ({sum(1 for f in files if f[0]=='vr')} VR, "
          f"{sum(1 for f in files if f[0]=='audit')} AUDIT)")

    all_chunks = []
    all_meta = []
    errors = []

    for kind, num, filepath in files:
        try:
            text = filepath.read_text(encoding="utf-8")
            meta = parse_header(text, filepath)
            status = classify_status(meta, text)
            meta["status_classified"] = status
            meta["claim_status"] = extract_claim_status(meta, text)
            sections = split_sections(text)
            chunks = build_chunks(meta, sections, text, status)
            if _TIERS:
                t = tiers_mod.tier_of(filepath, _TIERS)
                tid = t["id"] if t else "corpus"
                for ch in chunks:
                    ch["tier"] = tid
                meta["tier"] = tid
            all_chunks.extend(chunks)
            all_meta.append(meta)
        except Exception as e:
            errors.append({"file": filepath.name, "error": str(e)})

    if _TIERS:
        tchunks = tiers_mod.build_thread_chunks(_TIERS, extract_entities)
        if tchunks:
            all_chunks.extend(tchunks)
            print(f"  + {len(tchunks)} thread-round chunks "
                  f"({len({c['vr_id'] for c in tchunks})} threads)")

    print(f"Parsed {len(all_meta)} files → {len(all_chunks)} chunks")
    if errors:
        print(f"  {len(errors)} errors: {errors[:3]}")

    # Deterministic as-of stamp derived from the CORPUS, not the wall clock: rebuilding the
    # same corpus twice must produce byte-identical outputs (a clean `git status` after a
    # rebuild, and a testable invariant — scripts/rag/tests/determinism_check.sh).
    _dates = [str(m.get("date")) for m in all_meta if m.get("date")]
    corpus_stamp = f"{max(_dates) if _dates else 'unknown'}+{len(all_meta)}docs"

    # P6 M2: version-number supersession synthesis for versioned tiers (tiered mode
    # only — no tiers.json, no new output file, byte-identical single-tier behavior).
    if _TIERS:
        vdocs = tiers_mod.build_versioned_docs(_TIERS)
        with open(DATA_DIR / "versioned_docs.json", "w") as f:
            json.dump({"generated": corpus_stamp, "docs": vdocs}, f, indent=1)
        n_sup = sum(1 for d in vdocs if d["status"] == "superseded")
        if vdocs:
            print(f"  versioned_docs.json     ({len(vdocs)} docs, {n_sup} superseded)")
        ledger = tiers_mod.build_capture_ledger(
            _TIERS, all_meta, all_chunks,
            lambda meta: " ".join(str(meta.get(k) or "") for k in
                                  ("title", "status", "supersession")))
        if ledger is not None:
            ledger["generated"] = corpus_stamp
            with open(DATA_DIR / "capture_ledger.json", "w") as f:
                json.dump(ledger, f, indent=1)
            print(f"  capture_ledger.json     ({len(ledger['captures'])} captures, "
                  f"{len(ledger['unreconciled_rounds'])} unreconciled rounds, "
                  f"{len(ledger['receipt_candidates'])} receipt candidates)")

    DATA_DIR.mkdir(parents=True, exist_ok=True)   # redirected RAG_DATA_DIR may not exist yet

    registry = build_entity_registry(all_chunks)
    print(f"Entity registry: {len(registry)} entities")

    type_summary, type_violations = build_type_registry(registry)
    typed = sum(b["count"] for tid, b in type_summary.items() if tid != "_untyped")
    print(f"Type registry: {typed} typed entities, "
          f"{type_summary['_untyped']['count']} untyped, {len(type_violations)} validation suspects")
    with open(DATA_DIR / "type_registry.json", "w") as f:
        json.dump({"generated": corpus_stamp, "types": type_summary}, f, indent=2)
    with open(DATA_DIR / "type_violations.json", "w") as f:
        json.dump({"generated": corpus_stamp,
                   "count": len(type_violations), "violations": type_violations}, f, indent=2)

    graph = build_supersession_graph(all_chunks)
    print(f"Supersession graph: {len(graph)} edges")

    top_entities = sorted(registry.items(), key=lambda x: -x[1]["mention_count"])[:20]
    print("\nTop 20 entities by mention count:")
    for name, data in top_entities:
        print(f"  {name}: {data['mention_count']} mentions, "
              f"first={data['first_seen']}, last={data['last_seen']}")

    with open(DATA_DIR / "chunks.jsonl", "w") as f:
        for chunk in all_chunks:
            f.write(json.dumps(chunk, default=str) + "\n")

    with open(DATA_DIR / "entity_registry.json", "w") as f:
        json.dump(registry, f, indent=2, default=str)

    with open(DATA_DIR / "supersession.json", "w") as f:
        json.dump({"edges": graph, "relation_prov": RELATION_PROV_MAP,
                   "generated": corpus_stamp}, f, indent=2)

    with open(DATA_DIR / "file_meta.json", "w") as f:
        json.dump(all_meta, f, indent=2, default=str)

    claim_status_map = {}
    for m in all_meta:
        if m.get("id") and m.get("claim_status"):
            claim_status_map[m["id"]] = m["claim_status"]
    with open(DATA_DIR / "claim_status.json", "w") as f:
        json.dump(claim_status_map, f, indent=2)
    print(f"  claim_status.json    ({len(claim_status_map)} VRs)")

    # --- Phase 2: arc detection, method registry, claim strata, concepts ---

    # P6 M4: arcs are a vr-contract structure — thread-round chunks must not pull
    # thread ids into correction components via entity overlap (different tier, no
    # correction semantics). vr-doc chunks are those whose doc is in all_meta.
    _meta_ids = {m.get("id") for m in all_meta}
    arc_chunks = [ch for ch in all_chunks if ch.get("vr_id") in _meta_ids]
    arcs = build_arcs(graph, all_meta, arc_chunks)
    print(f"Arc detection: {len(arcs)} arcs")
    with open(DATA_DIR / "arcs.json", "w") as f:
        json.dump(arcs, f, indent=2, default=str)

    method_reg = extract_methods(all_meta, all_chunks)
    print(f"Method registry: {len(method_reg)} methods")
    with open(DATA_DIR / "method_registry.json", "w") as f:
        json.dump(method_reg, f, indent=2, default=str)

    for m in all_meta:
        vr_id = m.get("id", "")
        if not vr_id:
            continue
        text = ""
        for chunk in all_chunks:
            if chunk["vr_id"] == vr_id:
                text += " " + chunk.get("content", "")
        strata = extract_claim_strata(text)
        if strata and vr_id in claim_status_map:
            claim_status_map[vr_id]["strata"] = strata
    with open(DATA_DIR / "claim_status.json", "w") as f:
        json.dump(claim_status_map, f, indent=2)
    print(f"  claim_status.json    ({len(claim_status_map)} VRs, with strata)")

    concepts = extract_concepts(all_chunks, all_meta)
    print(f"Concept emergence: {len(concepts)} concepts tracked")
    with open(DATA_DIR / "concepts.json", "w") as f:
        json.dump(concepts, f, indent=2, default=str)

    stats = {
        "generated": corpus_stamp,
        "files_processed": len(all_meta),
        "chunks": len(all_chunks),
        "entities": len(registry),
        "typed_entities": typed,
        "untyped_entities": type_summary["_untyped"]["count"],
        "type_violations": len(type_violations),
        "entities_with_values": sum(1 for d in registry.values() if d.get("values")),
        "supersession_edges": len(graph),
        "arcs": len(arcs),
        "methods": len(method_reg),
        "concepts": len(concepts),
        "errors": len(errors),
        "error_details": errors,
    }
    with open(DATA_DIR / "index_stats.json", "w") as f:
        json.dump(stats, f, indent=2)

    print(f"\nOutputs written to {DATA_DIR}/")
    print(f"  chunks.jsonl         ({len(all_chunks)} chunks)")
    print(f"  entity_registry.json ({len(registry)} entities)")
    print(f"  type_registry.json   ({typed} typed, {len(type_violations)} suspects)")
    print(f"  type_violations.json ({len(type_violations)} suspects)")
    print(f"  supersession.json    ({len(graph)} edges)")
    print(f"  file_meta.json       ({len(all_meta)} files)")
    print(f"  arcs.json            ({len(arcs)} arcs)")
    print(f"  method_registry.json ({len(method_reg)} methods)")
    print(f"  concepts.json        ({len(concepts)} concepts)")
    print(f"  index_stats.json")

if __name__ == "__main__":
    run()
