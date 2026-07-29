#!/usr/bin/env python3
"""PreToolUse fence for the dreams channel (correspondence/dreams/).

Design (2026-07-29, operator-approved hardening): enforce the channel's IMMUTABILITY
contract mechanically, with rules that are correct for EVERY caller — no agent-identity
discriminator needed, so the fence is safe to arm uncalibrated:

  W1  in/DREAM-*/  is write-once: any Write/Edit targeting an EXISTING file under
      correspondence/dreams/in/ is blocked (landed dream artifacts are immutable).
  W2  out/DREAM-*/ freezes at handoff: once a packet dir contains PACKET.md, any
      Write/Edit into that dir is blocked (immutable-once-handed-off; creating
      PACKET.md itself is the freeze event and is allowed).

Also a SCHEMA LOGGER: every invocation appends its full stdin JSON to
.claude/hooks/fence_log.jsonl (gitignored) — the discovery instrument for the
pending dreamer read-scope fence (needs an agent-identity field; arm only after
the log shows one; see the dreams README hardening note).

Known limitation, stated: this fences the Write/Edit TOOL surface. Bash-mediated
writes bypass it — acceptable because the dreamer agent type has NO Bash tool
(its writes are fully fenced), while the main session is trusted-but-audited.
Escape hatch: touch .claude/hooks/fence_override to allow (logged), remove after.

Exit 0 = allow; exit 2 = block (stderr shown to the caller). Fail-OPEN on any
internal error: a broken fence must never brick the session.
"""
import json, os, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOG = Path(__file__).resolve().parent / "fence_log.jsonl"
OVERRIDE = Path(__file__).resolve().parent / "fence_override"

def main():
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        return 0  # unparseable input: fail open
    # schema logger — always, before any decision
    try:
        with open(LOG, "a") as f:
            f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "stdin": data}) + "\n")
    except Exception:
        pass
    try:
        tool = data.get("tool_name", "")
        if tool not in ("Write", "Edit", "NotebookEdit"):
            return 0
        ti = data.get("tool_input", {}) or {}
        p = ti.get("file_path") or ti.get("notebook_path") or ""
        if not p:
            return 0
        path = Path(p)
        if not path.is_absolute():
            path = ROOT / p
        try:
            rel = path.resolve().relative_to(ROOT)
        except ValueError:
            return 0  # outside repo: not this fence's business
        parts = rel.parts
        if len(parts) < 3 or parts[0] != "correspondence" or parts[1] != "dreams":
            return 0
        if OVERRIDE.exists():
            return 0  # operator escape hatch (invocation already logged)
        sub = parts[2]
        if sub == "in":
            # W1: landed artifacts are write-once
            if path.exists():
                print(f"dream-fence W1: {rel} is a LANDED dream artifact (in/ is "
                      "write-once). Corrections are new documents; to override "
                      "deliberately: touch .claude/hooks/fence_override", file=sys.stderr)
                return 2
            return 0
        if sub == "out" and len(parts) >= 4:
            packet_dir = ROOT / Path(*parts[:4])
            target_is_packet = (len(parts) == 5 and parts[4] == "PACKET.md")
            if (packet_dir / "PACKET.md").exists() and not (target_is_packet and not path.exists()):
                print(f"dream-fence W2: {Path(*parts[:4])} is FROZEN (PACKET.md "
                      "present = handed off). Compose a new DREAM-N dir instead; "
                      "to override deliberately: touch .claude/hooks/fence_override",
                      file=sys.stderr)
                return 2
            return 0
        return 0
    except Exception:
        return 0  # fail open

if __name__ == "__main__":
    sys.exit(main())
