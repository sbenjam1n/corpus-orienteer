#!/usr/bin/env python3
"""
Evidence grounding check for the VR/AUDIT corpus (DRIFT Support Seeker analog).

Four checks:
  (a) Reproducer existence: /tmp scripts, missing scripts (the **Reproducer:** line)
  (b) Cross-reference validity: dangling VR-N AND AUDIT-N references
  (c) Retraction propagation: superseded VRs without correction tags
  (d) File-reference grounding (lychee + leanblueprint-checkdecls borrow, axis-5 of
      docs/CONCEPT_COVERAGE_IMPLEMENTATION_INDEX): backtick-quoted repo-relative file
      citations ANYWHERE in the body — not just the Reproducer line — that no longer
      resolve on disk. lychee = dead-link detection; checkdecls = resolve the reference
      against the source tree (here: .lean citations are resolved against proofs/, so a
      module cited without its proofs/ prefix is NOT a false positive, while a genuinely
      removed/renamed module IS flagged). Superseded paper-outline versions are split off
      as INFO (expected version churn), not LOW findings, to avoid alarm fatigue.

Run:  python3 scripts/rag/grounding_check.py
Requires: data/rag/file_meta.json and data/rag/supersession.json (run index_vrs.py first)
"""

import json, os, re, glob, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import domain_ids

ROOT = Path(__file__).resolve().parents[2]
VR_DIR = Path(os.environ.get("RAG_CORPUS_DIR", ROOT / "verification_ready"))
# Formal-source root for resolving bare module citations (e.g. `Foo/Defs.lean` -> proofs/).
# Config: domain_config.json {"grounding": {"source_root": "proofs"}}. The paper-outline
# checks below are r14-deployment heuristics; they no-op when papers/ is absent.
try:
    _gcfg = json.loads((domain_ids.SEED_DIR / "domain_config.json").read_text()).get("grounding", {}) or {}
except (FileNotFoundError, json.JSONDecodeError):
    _gcfg = {}
PROOFS_DIR = ROOT / _gcfg.get("source_root", "proofs")
DATA_DIR = Path(os.environ.get("RAG_DATA_DIR", ROOT / "data" / "rag"))

def load_meta():
    with open(DATA_DIR / "file_meta.json") as f:
        return json.load(f)

def load_supersession():
    with open(DATA_DIR / "supersession.json") as f:
        return json.load(f)

def extract_paths(reproducer_text):
    return re.findall(r'(?:scripts/[\w/.-]+\.(?:gp|py|gap|g|c|sh)|/tmp/[\w/.-]+\.(?:gp|py|gap|g))', reproducer_text)

def check_reproducers(meta_list):
    findings = []
    for m in meta_list:
        vr_id = m.get("id", "?")
        filepath = VR_DIR / m.get("file", "")
        if not filepath.exists():
            continue
        text = filepath.read_text(encoding="utf-8")
        reproducer_match = re.search(r"\*\*Reproducer:\*\*\s*(.+?)(?:\n|$)", text)
        if not reproducer_match:
            continue
        reproducer = reproducer_match.group(1).strip()
        if reproducer.lower().startswith("n/a") or reproducer.lower().startswith("(pending") or reproducer == "—":
            continue
        paths = extract_paths(reproducer)
        for p in paths:
            if p.startswith("/tmp/"):
                findings.append({"type": "TMP_SCRIPT", "vr_id": vr_id, "detail": p, "severity": "LOW"})
            elif not (ROOT / p).exists():
                findings.append({"type": "MISSING_SCRIPT", "vr_id": vr_id, "detail": p, "severity": "MEDIUM"})
    return findings

def check_crossrefs(meta_list):
    findings = []
    existing_vrs = {p.stem.split("_")[0] for p in VR_DIR.glob(f"{domain_ids.PRIMARY}-*.md")}
    existing_audits = {p.stem.split("_")[0] for p in VR_DIR.glob(f"{domain_ids.AUDIT}-*.md")}
    all_existing = existing_vrs | existing_audits

    for m in meta_list:
        vr_id = m.get("id", "?")
        filepath = VR_DIR / m.get("file", "")
        if not filepath.exists():
            continue
        text = filepath.read_text(encoding="utf-8")
        seen = set()
        # Both namespaces — AUDIT-N is the auditor's own namespace and was previously unchecked,
        # so a dangling AUDIT-N (e.g. content that lives under a VR-* filename, or a pre-rename
        # reference) slipped through. Dedupe per file so a ref cited N times is one finding.
        for ref_match in domain_ids.DOC_ID_RE.finditer(text):
            ref = ref_match.group(1)
            if ref not in all_existing and ref not in seen:
                seen.add(ref)
                findings.append({"type": "DANGLING_REF", "vr_id": vr_id, "detail": ref, "severity": "LOW"})
    return findings

def check_retraction_propagation(supersession):
    findings = []
    refutation_targets = set()
    for edge in supersession.get("edges", []):
        if edge["relation"] in ("refutes", "corrects", "retracts"):
            refutation_targets.add(edge["target"])

    for target in refutation_targets:
        matches = list(VR_DIR.glob(f"{target}_*.md"))
        if not matches:
            continue
        text = matches[0].read_text(encoding="utf-8")
        has_tag = bool(re.search(r"\[RETRACTED|\[CORRECTED|\[DEPRECATED|\[AFFECTED", text, re.I))
        if not has_tag:
            findings.append({
                "type": "UNACKNOWLEDGED_CORRECTION",
                "vr_id": target,
                "detail": f"{target} has been corrected/refuted but has no inline correction tag",
                "severity": "MEDIUM",
            })
    return findings

_FILE_EXT = (".gp", ".py", ".gap", ".c", ".sh", ".json", ".md", ".lean", ".jl", ".g")
_BAD_PATH_CHARS = set("*<>{}[],")
_BACKTICK = re.compile(r"`([^`]+)`")
_OUTLINE_VER = re.compile(r"paper_outline_v2_\d+\.md$")

def _looks_like_repo_path(s):
    """A backtick token that is a concrete repo-relative file citation — not prose, not a /tmp
    reproducer (those are check (a)'s TMP_SCRIPT), not a shell shorthand. The char/whitespace
    guards reject brace-expansions (`{sec1,sec2}_v1.md`), globs, and line-wrapped tokens, all of
    which calibration showed are notation, not real single files."""
    return (s.endswith(_FILE_EXT) and "/" in s and not s.startswith("/tmp/")
            and not any(c in _BAD_PATH_CHARS for c in s)
            and not any(c.isspace() for c in s) and "..." not in s)

def _path_resolves(s):
    """lychee: resolve repo-relative (against the repo root and verification_ready/). checkdecls:
    a .lean citation is resolved against the proofs/ source tree too — modules are routinely cited
    without their proofs/ prefix (BrauerBlocks/Defs.lean), and basename-anywhere covers a moved
    module — so only a genuinely absent declaration file is flagged, not a prefix omission."""
    if (ROOT / s).exists() or (VR_DIR / s).exists():
        return True
    if s.endswith(".lean"):
        if (PROOFS_DIR / s).exists():
            return True
        return any(True for _ in PROOFS_DIR.rglob(Path(s).name))
    return False

def check_file_refs(meta_list):
    findings = []
    has_outline = bool(list((ROOT / "papers").glob("paper_outline_v2_*.md")))
    for m in meta_list:
        vr_id = m.get("id", "?")
        filepath = VR_DIR / m.get("file", "")
        if not filepath.exists():
            continue
        text = filepath.read_text(encoding="utf-8")
        seen = set()
        for mm in _BACKTICK.finditer(text):
            s = mm.group(1).strip()
            if not _looks_like_repo_path(s) or s in seen:
                continue
            seen.add(s)
            if _path_resolves(s):
                continue
            # A reference to a SUPERSEDED outline version (current one present) is expected churn,
            # not a grounding failure — INFO, like TMP_SCRIPT, so it does not drown the real misses.
            if has_outline and _OUTLINE_VER.search(s):
                findings.append({"type": "SUPERSEDED_OUTLINE_REF", "vr_id": vr_id, "detail": s, "severity": "INFO"})
            else:
                findings.append({"type": "DANGLING_FILE_REF", "vr_id": vr_id, "detail": s, "severity": "LOW"})
    return findings

def run():
    meta = load_meta()
    supersession = load_supersession()

    print("=== Evidence Grounding Check ===\n")

    f1 = check_reproducers(meta)
    f2 = check_crossrefs(meta)
    f3 = check_retraction_propagation(supersession)
    f4 = check_file_refs(meta)

    all_findings = f1 + f2 + f3 + f4

    by_type = {}
    for f in all_findings:
        by_type.setdefault(f["type"], []).append(f)

    for ftype, items in sorted(by_type.items()):
        print(f"{ftype}: {len(items)}")
        for item in items[:5]:
            print(f"  {item['vr_id']}: {item['detail']}")
        if len(items) > 5:
            print(f"  ... and {len(items)-5} more")

    print(f"\nTotal findings: {len(all_findings)}")

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with open(DATA_DIR / "grounding_report.json", "w") as f:
        json.dump({"findings": all_findings, "summary": {k: len(v) for k, v in by_type.items()}}, f, indent=2)

    print(f"Report written to {DATA_DIR}/grounding_report.json")

if __name__ == "__main__":
    run()
