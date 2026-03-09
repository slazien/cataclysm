#!/usr/bin/env bash
# Wrapper around dmypy that auto-recovers from daemon crashes/hangs.
# Usage: scripts/dmypy-check.sh [mypy args...]
# Default: checks cataclysm/ backend/

if [[ $# -eq 0 ]]; then
  set -- cataclysm/ backend/
fi

TIMEOUT=120  # seconds

run_check() {
  timeout "$TIMEOUT" dmypy run -- "$@" 2>&1
}

output=$(run_check "$@")
rc=$?

# rc=124 = timeout killed it; also check for crash messages
if [[ $rc -ne 0 ]] && { echo "$output" | grep -qE "Daemon crashed|timed out|Connection refused"; } || [[ $rc -eq 124 ]]; then
  echo "dmypy failed (rc=$rc) — restarting daemon and retrying..." >&2
  dmypy kill 2>/dev/null || true
  sleep 1
  dmypy start 2>/dev/null
  output=$(run_check "$@")
  rc=$?
fi

echo "$output"
exit "$rc"
