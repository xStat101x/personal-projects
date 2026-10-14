#!/usr/bin/env bash
# vuln-knowledge skill entrypoint.
# Invoked by the orchestrator via the exec tool.
#
# Usage:
#   ./run.sh lookup "ssrf aws metadata" [k]
#   ./run.sh lookup "CVE-2024-3094" 3
#   ./run.sh reindex
#   ./run.sh status

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOOKUP="$SKILL_DIR/lookup.py"
INDEX="$SKILL_DIR/index.db"

cmd="${1:-}"

case "$cmd" in
  lookup)
    query="${2:-}"
    k="${3:-5}"
    if [[ -z "$query" ]]; then
      echo '{"error":"missing query","results":[],"confidence":0.0}'
      exit 0
    fi
    if [[ ! -f "$INDEX" ]]; then
      echo '{"error":"index not built; run: vuln-knowledge reindex","results":[],"confidence":0.0}'
      exit 0
    fi
    python3 "$LOOKUP" --query "$query" --k "$k" 2>/dev/null || \
      echo '{"error":"lookup failed","results":[],"confidence":0.0}'
    ;;

  reindex)
    python3 "$LOOKUP" --rebuild-index --verbose 1>&2
    echo '{"status":"ok","action":"reindex"}'
    ;;

  status)
    if [[ ! -f "$INDEX" ]]; then
      echo '{"status":"missing","index":null}'
      exit 0
    fi
    age_seconds=$(( $(date +%s) - $(stat -f %m "$INDEX" 2>/dev/null || stat -c %Y "$INDEX") ))
    age_days=$(( age_seconds / 86400 ))
    echo "{\"status\":\"ok\",\"index_age_days\":$age_days,\"stale\":$([ $age_days -gt 14 ] && echo true || echo false)}"
    ;;

  *)
    echo '{"error":"unknown command","usage":"lookup <query> [k] | reindex | status"}'
    exit 0
    ;;
esac