#!/usr/bin/env python3
"""Document-id scheme, config-driven (Stage 2 of
Plans/rag_standalone_extraction_execution.md).

The engine tracks two document namespaces: PRIMARY (substantive results; "VR" in the
r14 deployment) and AUDIT (findings about existing documents). Both were previously
hardcoded at every call site; this module is the single source, overridable via an
optional `doc_id` key in domain_config.json:

    "doc_id": {"primary": "VR", "audit": "AUDIT"}

A corpus whose documents are RFC-N / REVIEW-N ports by setting this key — no engine
edits. Prefixes are treated as literals (regex-escaped). The filename shape stays
`<PREFIX>-<N>_<slug>.md`; see docs/rag_corpus_format.md for the full contract.
"""
import json
import os
import re
from pathlib import Path

SEED_DIR = Path(os.environ.get("RAG_SEED_DIR", Path(__file__).resolve().parent))

_cfg = {}
try:
    _cfg = json.loads((SEED_DIR / "domain_config.json").read_text()).get("doc_id", {}) or {}
except (FileNotFoundError, json.JSONDecodeError):
    pass

PRIMARY = _cfg.get("primary", "VR")
AUDIT = _cfg.get("audit", "AUDIT")

_P, _A = re.escape(PRIMARY), re.escape(AUDIT)
DOC_ID_RE = re.compile(rf"\b((?:{_P}|{_A})-\d+)\b")     # any doc ref in running text
STEM_RE = re.compile(rf"({_P}|{_A})-(\d+)")             # id/stem parser (anchored via .match)
TITLE_RE = re.compile(rf"^#\s+(?:{_P}|{_A})-\d+[^:]*:\s*(.+)$", re.M)
MULTI_PRIMARY_RE = re.compile(rf"{_P}-(\d+)")           # every primary ref inside one span


def is_audit(doc_id):
    return doc_id.startswith(AUDIT + "-")


def doc_number(doc_id):
    """Numeric part of PRIMARY-N / AUDIT-N, or None."""
    m = STEM_RE.match(doc_id or "")
    return int(m.group(2)) if m else None
