#!/usr/bin/env python3
"""
scope-guard checker. Every active skill calls this BEFORE touching a target.

Usage:
    python3 check.py --engagement acme-2026-04 --target https://api.acme.test/v2/users
    python3 check.py --engagement acme-2026-04 --target 203.0.113.15 --action nmap
    python3 check.py --engagement acme-2026-04 --forbidden sqlmap_risk_3_plus

Exit codes:
    0 = allowed (stdout: JSON with "allowed": true)
    0 = denied  (stdout: JSON with "allowed": false and "reason")
    2 = configuration error (missing file, malformed scope, etc.)

Never exits nonzero for deny — calling skills check the JSON, not the exit code.
"""

import argparse
import ipaddress
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

try:
    import yaml
except ImportError:
    print(json.dumps({
        "allowed": False,
        "reason": "config_error",
        "detail": "PyYAML not installed. Run: pip3 install pyyaml"
    }))
    sys.exit(2)

SKILL_DIR = Path(__file__).resolve().parent
WORKSPACE = SKILL_DIR.parent.parent
ENGAGEMENTS_DIR = WORKSPACE / "engagements"


def load_scope(engagement_id: str) -> dict:
    scope_path = ENGAGEMENTS_DIR / engagement_id / "scope.yaml"
    if not scope_path.exists():
        raise FileNotFoundError(f"no scope.yaml at {scope_path}")
    with open(scope_path) as f:
        return yaml.safe_load(f)


def check_window(scope: dict) -> tuple[bool, str]:
    window = scope.get("window", {})
    start = window.get("start")
    end = window.get("end")
    if not start or not end:
        return False, "scope missing window.start or window.end"
    now = datetime.now(timezone.utc)
    start_dt = start if isinstance(start, datetime) else datetime.fromisoformat(str(start).replace("Z", "+00:00"))
    end_dt = end if isinstance(end, datetime) else datetime.fromisoformat(str(end).replace("Z", "+00:00"))
    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=timezone.utc)
    if end_dt.tzinfo is None:
        end_dt = end_dt.replace(tzinfo=timezone.utc)
    if now < start_dt:
        return False, f"engagement starts at {start_dt.isoformat()}"
    if now > end_dt:
        return False, f"engagement ended at {end_dt.isoformat()}"
    return True, "within window"


def domain_matches(target: str, pattern: str) -> bool:
    """Match a hostname against a pattern with optional leading wildcard."""
    target = target.lower().strip(".")
    pattern = pattern.lower().strip(".")
    if pattern.startswith("*."):
        suffix = pattern[2:]
        return target == suffix or target.endswith("." + suffix)
    return target == pattern


def is_ip(s: str) -> bool:
    try:
        ipaddress.ip_address(s)
        return True
    except ValueError:
        return False


def ip_in_cidrs(ip_str: str, cidrs: list) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    for cidr in cidrs or []:
        try:
            if ip in ipaddress.ip_network(cidr, strict=False):
                return True
        except ValueError:
            continue
    return False


def extract_host_and_path(target: str) -> tuple[str, str]:
    """Return (host, path) from a URL or bare host."""
    if "://" in target:
        parsed = urlparse(target)
        return parsed.hostname or "", parsed.path or ""
    # Bare host or host:port
    host = target.split(":")[0].split("/")[0]
    return host, ""


def check_target(scope: dict, target: str) -> tuple[bool, str]:
    in_scope = scope.get("in_scope", {}) or {}
    out_of_scope = scope.get("out_of_scope", {}) or {}
    host, path = extract_host_and_path(target)

    # Out-of-scope wins. Check it first.
    if host and any(domain_matches(host, p) for p in out_of_scope.get("domains", []) or []):
        return False, f"{host} is explicitly out of scope"
    if is_ip(host) and ip_in_cidrs(host, out_of_scope.get("ips", [])):
        return False, f"{host} is in out-of-scope IP range"
    for forbidden_path in out_of_scope.get("paths", []) or []:
        if path.startswith(forbidden_path):
            return False, f"path {path} is out of scope"

    # In-scope check. At least one must match.
    domain_match = host and any(domain_matches(host, p) for p in in_scope.get("domains", []) or [])
    ip_match = is_ip(host) and ip_in_cidrs(host, in_scope.get("ips", []))
    url_match = any(target.startswith(u) for u in in_scope.get("urls_prefix", []) or [])

    if domain_match or ip_match or url_match:
        return True, f"{host or target} is in scope"

    return False, f"{host or target} is not in any in-scope entry"


def check_forbidden(scope: dict, action: str) -> tuple[bool, str]:
    forbidden = scope.get("forbidden_actions", []) or []
    if action in forbidden:
        return False, f"action '{action}' is forbidden for this engagement"
    return True, f"action '{action}' is allowed"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--engagement", required=True)
    p.add_argument("--target", help="URL, hostname, or IP to check")
    p.add_argument("--action", help="Named action to check against forbidden_actions")
    args = p.parse_args()

    try:
        scope = load_scope(args.engagement)
    except FileNotFoundError as e:
        print(json.dumps({"allowed": False, "reason": "config_error", "detail": str(e)}))
        sys.exit(2)
    except yaml.YAMLError as e:
        print(json.dumps({"allowed": False, "reason": "config_error", "detail": f"malformed scope.yaml: {e}"}))
        sys.exit(2)

    # Window check first — if engagement is over, nothing is allowed
    window_ok, window_reason = check_window(scope)
    if not window_ok:
        print(json.dumps({
            "allowed": False,
            "reason": "outside_window",
            "detail": window_reason,
            "engagement": args.engagement
        }))
        return

    checks = []

    if args.target:
        target_ok, target_reason = check_target(scope, args.target)
        checks.append(("target", target_ok, target_reason))
        if not target_ok:
            print(json.dumps({
                "allowed": False,
                "reason": "target_out_of_scope",
                "detail": target_reason,
                "target": args.target,
                "engagement": args.engagement
            }))
            return

    if args.action:
        action_ok, action_reason = check_forbidden(scope, args.action)
        checks.append(("action", action_ok, action_reason))
        if not action_ok:
            print(json.dumps({
                "allowed": False,
                "reason": "action_forbidden",
                "detail": action_reason,
                "action": args.action,
                "engagement": args.engagement
            }))
            return

    if not checks:
        print(json.dumps({"allowed": False, "reason": "no_check_requested", "detail": "pass --target or --action"}))
        return

    print(json.dumps({
        "allowed": True,
        "engagement": args.engagement,
        "checks": [{"type": t, "detail": d} for t, _, d in checks],
        "rate_limits": scope.get("rate_limits", {})
    }))


if __name__ == "__main__":
    main()