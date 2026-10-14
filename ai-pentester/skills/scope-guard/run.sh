#!/usr/bin/env bash
# scope-guard skill entrypoint.
#
# Usage:
#   ./run.sh check <engagement_id> <target> [action]
#   ./run.sh list
#   ./run.sh show <engagement_id>

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHECK="$SKILL_DIR/check.py"
WORKSPACE="$(cd "$SKILL_DIR/../.." && pwd)"
ENGAGEMENTS="$WORKSPACE/engagements"

cmd="${1:-}"

case "$cmd" in
  check)
    engagement="${2:-}"
    target="${3:-}"
    action="${4:-}"
    if [[ -z "$engagement" || ( -z "$target" && -z "$action" ) ]]; then
      echo '{"allowed":false,"reason":"usage","detail":"check <engagement> <target> [action]"}'
      exit 0
    fi
    args=(--engagement "$engagement")
    [[ -n "$target" ]] && args+=(--target "$target")
    [[ -n "$action" ]] && args+=(--action "$action")
    python3 "$CHECK" "${args[@]}" 2>/dev/null || \
      echo '{"allowed":false,"reason":"checker_error","detail":"see logs"}'
    ;;

  list)
    if [[ ! -d "$ENGAGEMENTS" ]]; then
      echo '{"engagements":[]}'
      exit 0
    fi
    engagements=$(ls -1 "$ENGAGEMENTS" 2>/dev/null | grep -v '^\.' | jq -R . | jq -s . 2>/dev/null || echo '[]')
    echo "{\"engagements\":$engagements}"
    ;;

  show)
    engagement="${2:-}"
    scope_file="$ENGAGEMENTS/$engagement/scope.yaml"
    if [[ ! -f "$scope_file" ]]; then
      echo "{\"error\":\"no scope.yaml for $engagement\"}"
      exit 0
    fi
    python3 -c "import yaml, json, sys; print(json.dumps(yaml.safe_load(open('$scope_file'))))"
    ;;

  *)
    echo '{"error":"unknown command","usage":"check|list|show"}'
    exit 0
    ;;
esac