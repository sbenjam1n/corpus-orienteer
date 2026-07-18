#!/usr/bin/env bash
# RAG rebuild — run at each audit cycle to refresh the index.
# Usage: bash scripts/rag/rebuild.sh [--embed] [--doctest]   (flags order-independent)
#
# Core (always): index -> ontology -> coverage -> brief  (stdlib-only, fast ~5-10s)
#   --embed   : also rebuild vector embeddings (~60s)
#   --doctest : also re-run curated reproducers + write doctest_results.json (needs gp/PARI; heavy).
#               OPT-IN by design — a default rebuild stays fast and hermetic (no PARI shell-outs).
#
# Each stage is timed and a per-stage breakdown is printed at the end, so a creeping
# bottleneck (the compute_drift O(n*m) class) is visible the build it appears, not weeks later.

set -e
cd "$(dirname "$0")/../.."

# Order-independent optional flags.
DO_EMBED=0; DO_DOCTEST=0
for a in "$@"; do
    case "$a" in
        --embed) DO_EMBED=1 ;;
        --doctest) DO_DOCTEST=1 ;;
    esac
done

STAGE_NAMES=(); STAGE_SECS=()
run_stage() {  # run_stage <name> <cmd...>
    local name="$1"; shift
    local t0=$SECONDS
    "$@"
    STAGE_NAMES+=("$name"); STAGE_SECS+=($((SECONDS - t0)))
}

echo "=== RAG Rebuild ==="
echo "Corpus: ${RAG_CORPUS_DIR:-verification_ready/}"
echo ""

echo "[1/4] Indexing VRs..."
run_stage index python3 scripts/rag/index_vrs.py
echo ""

echo "[2/4] Building ontology layer (objects, links, drift, monitors)..."
run_stage ontology python3 scripts/rag/ontology.py
echo ""

echo "[3/4] Self-coverage audit (does the tool still capture the corpus language?)..."
run_stage coverage python3 scripts/rag/coverage.py
echo ""

echo "[4/4] Synthesizing warm-start audit brief (active arcs, distrusted methods, unmet monitors, drift)..."
run_stage brief python3 scripts/rag/synthesize_brief.py
# Roll the file_meta snapshot AFTER the brief has diffed against it, so the next pass's
# "changed since last pass" delta (P4) is computed vs this rebuild. Kept here (not in the
# generator) so repeated `query.py brief` runs stay byte-deterministic.
DATA_DIR="${RAG_DATA_DIR:-data/rag}"
cp "$DATA_DIR/file_meta.json" "$DATA_DIR/file_meta_prev.json" 2>/dev/null || true
echo ""

if [[ $DO_EMBED -eq 1 ]]; then
    echo "(optional) Embedding chunks..."
    run_stage embed python3 scripts/rag/embed.py
    echo ""
fi

if [[ $DO_DOCTEST -eq 1 ]]; then
    echo "(optional) Doctest grounding — re-run curated reproducers (heavy; needs gp)..."
    # A failing reproducer is a finding recorded in doctest_results.json, not a rebuild error,
    # so don't let it abort the build under `set -e`.
    run_stage doctest bash -c 'python3 scripts/rag/doctest_grounding.py --json || true'
    echo ""
fi

echo ""
echo "=== RAG Rebuild Complete ==="
cat "${RAG_DATA_DIR:-data/rag}/index_stats.json" | python3 -c "
import json, sys
s = json.load(sys.stdin)
print(f\"  Files: {s['files_processed']}\")
print(f\"  Chunks: {s['chunks']}\")
print(f\"  Entities: {s['entities']}\")
print(f\"  Supersession edges: {s['supersession_edges']}\")
print(f\"  Errors: {s['errors']}\")
"
TOTAL=0; for s in "${STAGE_SECS[@]}"; do TOTAL=$((TOTAL + s)); done
TIMING="  Stage timings:"
for i in "${!STAGE_NAMES[@]}"; do TIMING+=" ${STAGE_NAMES[$i]} ${STAGE_SECS[$i]}s ·"; done
echo "${TIMING% ·}  (total ${TOTAL}s)"
