#!/usr/bin/env bash
# Byte-determinism check: rebuild the RAG graph twice over the same corpus and require
# every core output in data/rag/ to be byte-identical (the "if your input is
# deterministic, your pipeline should be too" invariant — no wall-clock stamps, no
# ordering nondeterminism). Also verifies the tracked index_stats.json is not dirtied,
# so a routine rebuild leaves `git status` clean.
#
# Usage (from repo root):  bash scripts/rag/tests/determinism_check.sh
# ~2x rebuild time (core stages only, no --embed). Exits nonzero on any divergence.
set -e
cd "$(dirname "$0")/../../.."

SNAP=$(mktemp -d)
trap 'rm -rf "$SNAP"' EXIT
# file_meta_prev.json is a rolling snapshot rebuild.sh rotates AFTER the brief diffs
# against it — it legitimately differs between runs 1 and 2, so it is excluded.
hash_outputs() {
    (cd data/rag && find . -maxdepth 1 -type f \( -name '*.json' -o -name '*.jsonl' -o -name '*.md' \) \
        ! -name 'file_meta_prev.json' ! -name 'audit_sessions.jsonl' -print0 \
        | sort -z | xargs -0 sha256sum)
}

echo "[determinism 1/2] first rebuild..."
bash scripts/rag/rebuild.sh > "$SNAP/build1.log" 2>&1
hash_outputs > "$SNAP/hashes1.txt"

echo "[determinism 2/2] second rebuild..."
bash scripts/rag/rebuild.sh > "$SNAP/build2.log" 2>&1
hash_outputs > "$SNAP/hashes2.txt"

if ! diff -u "$SNAP/hashes1.txt" "$SNAP/hashes2.txt"; then
    echo "FAIL: data/rag outputs differ between two rebuilds of the same corpus." >&2
    exit 1
fi

if ! git diff --quiet -- data/rag/index_stats.json; then
    echo "FAIL: rebuild dirtied the tracked data/rag/index_stats.json:" >&2
    git --no-pager diff -- data/rag/index_stats.json >&2
    exit 1
fi

N=$(wc -l < "$SNAP/hashes1.txt")
echo "OK: $N data/rag outputs byte-identical across two rebuilds; tracked index_stats.json clean."
