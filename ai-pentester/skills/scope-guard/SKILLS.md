---
name: scope-guard
description: MANDATORY pre-flight check for any active probing, scanning,
  or exploitation action. Validates target against signed engagement scope
  (in-scope/out-of-scope domains, IPs, paths), enforces engagement time
  window, and checks forbidden-action list. Every other active skill MUST
  call scope-guard before touching a target. Never skip. Never cache.
  No target ever leaves this agent without passing this check.
---

# scope-guard

## When to invoke

Before EVERY active network action. Every time. No exceptions.

- Before calling any scanning skill (nmap, nuclei, httpx, ffuf, etc.)
- Before browser tool navigates to a target URL
- Before exec tool runs any command containing a target hostname or IP
- Before sending any crafted request to a target

Passive-only actions using already-collected data (parsing scan output,
writing reports, reading local corpus) do NOT need scope-guard. Anything
that generates a packet toward a target does.

## How to use

Call: `./run.sh check <engagement> <target> [action]`

Parse the JSON response. If `allowed: false`, STOP. Report to the operator
with the `reason` and `detail` fields. Do not retry, do not reformulate,
do not try a different tool against the same target.

If `allowed: true`, respect the `rate_limits` in the response when
configuring the downstream tool.

## Rules the agent must follow

1. The scope.yaml file is authoritative. If it says no, the answer is no.
2. Never modify scope.yaml. It represents a signed legal agreement.
3. If no engagement is active, no active actions are permitted. Ask the
   operator to create one.
4. If scope-guard returns a config_error, STOP all active work and tell
   the operator. Do not guess.
5. When in doubt about whether an action needs scope-guard, call it.
   Overcalling is free. Undercalling is a legal problem.

## Testing

```bash
./run.sh check acme-2026-04 https://api.acme.test/v2/users
./run.sh check acme-2026-04 admin.acme.test          # should deny
./run.sh check acme-2026-04 203.0.113.15              # should allow
./run.sh check acme-2026-04 8.8.8.8                   # should deny
./run.sh check acme-2026-04 api.acme.test sqlmap_risk_3_plus  # deny (forbidden)
```