# `scope.yaml` Schema (DRAFT v0.4)

The single source of truth for what an engagement is allowed to do. Read once at engagement start by the orchestrator. Validated by the `scope-validator` skill before any active action. **Never modified by any agent.**

This doc is the contract `scope-validator`, `engagement-init`, and `scope-guard` all implement against. If you change the schema, update all three skills.

---

## 1. File location

```
/Users/openclaw/ai-pentester/engagements/<engagement-id>/scope.yaml
```

`<engagement-id>` is the slug used everywhere else in the workspace (path component, audit log entries, finding ID prefix). Convention: `YYYYMMDD-<short-name>` (e.g., `20260515-acme-staging`). The `engagement-init` skill generates this from the operator's chosen short name.

---

## 2. Required top-level fields

| Field | Type | Notes |
|---|---|---|
| `engagement_id` | string | Slug. Must match the parent directory name. Lowercase, alphanumeric + hyphens. |
| `mode` | enum | `production` \| `ctf`. Drives the hard-rule overlays in `SYSTEM_PROMPT.md §10`. |
| `time_window` | object | `start` (ISO 8601 UTC), `end` (ISO 8601 UTC). The engagement window closes hard at `end` — every active sub-agent stops. |
| `in_scope` | list | List of scope entries (see §4). At least one entry required. |
| `out_of_scope` | list | List of scope entries that explicitly exclude paths/hosts even if `in_scope` glob would include them. May be empty list. |
| `contact_tree` | object | `primary` (name, email-or-discord), `escalation` (same). Used by `notification-discord` to route alerts. |

## 3. Optional top-level fields

| Field | Type | Notes |
|---|---|---|
| `parent_engagement_id` | string | Slug of the prior engagement this run continues. Enables `diff-watcher`. Set when the operator declares a repeat run. |
| `dev` | bool | `true` enables the `dev` logging overlay (`logs/reasoning.jsonl`, `logs/dispatch.jsonl`). Composable with both `production` and `ctf`. |
| `rate_limit` | object | `requests_per_second` (number), `burst` (number). Applied by `exploit-runner` and any scanner. Default: 10 rps, burst 20. |
| `signature` | object | `signed_by` (string), `signed_at` (ISO 8601), `sig` (base64 detached signature over a canonical form of the file). Required when `mode: production`. The orchestrator refuses to start a `production` run without a verified signature. |
| `flag_format` | regex string | CTF mode only. Compiled and handed to `ctf-flag-detector`. Example: `HTB\{[a-f0-9]{32}\}`. |
| `target_type` | enum | CTF mode only. `htb` \| `thm` \| `local_vm` \| `other`. Used for run tagging, no behavior change. |
| `focus_areas` | list of strings | Free-form hints passed to `vuln-agent` (e.g., `["auth", "bola", "ssrf"]`). Advisory only. |
| `post_exploit_authorized` | bool | Default `false`. When `true`, `exploit-agent` may demonstrate post-exploitation impact (lateral movement, data exfil proof) beyond the smallest payload that proves the bug. Should only be `true` for engagements where the customer has explicitly contracted post-exploit impact demonstration. |
| `notes` | string | Free-form. Anything the operator wants the orchestrator to remember at boot. |

---

## 4. Scope entry format (`in_scope` / `out_of_scope`)

Each entry is one of:

**Hostname / URL entry:**

```yaml
- kind: http
  pattern: "*.acme.test"                # glob match against scheme+host+path
  allowed_methods: [GET, POST, PUT, DELETE, PATCH, OPTIONS]
  allowed_ports: [80, 443, 8080]
  notes: "main customer surface"
```

**Network entry:**

```yaml
- kind: net
  pattern: "10.4.0.0/16"                # CIDR
  allowed_ports: [22, 80, 443, 3306]
  protocols: [tcp]
  notes: "VPN-reachable internal lab"
```

**Cloud entry:**

```yaml
- kind: cloud
  provider: aws
  account_id: "123456789012"
  pattern: "s3://acme-public-*"
  notes: "public buckets only"
```

**Code / repo entry (for gray-box engagements):**

```yaml
- kind: code
  pattern: "git@github.com:acme/web-app.git"
  branch: "main"
  notes: "operator-cloned to engagements/<id>/source/ at start of run"
```

**Out-of-scope entries** use the same kinds but their presence subtracts from the in-scope union. Conflict resolution: `out_of_scope` always wins, even if a more-specific `in_scope` glob would include the asset. `scope-validator` warns on conflicts at engagement start.

---

## 5. Example — production engagement

```yaml
engagement_id: 20260515-acme-staging
mode: production
dev: false
time_window:
  start: "2026-05-20T14:00:00Z"
  end:   "2026-05-23T22:00:00Z"
rate_limit:
  requests_per_second: 8
  burst: 16
signature:
  signed_by: "Rex Kenyon (operator)"
  signed_at: "2026-05-15T18:00:00Z"
  sig: "BASE64-DETACHED-SIG"
contact_tree:
  primary:
    name: "Rex Kenyon"
    discord: "Rex#0001"
  escalation:
    name: "Acme CISO"
    email: "ciso@acme.test"
in_scope:
  - kind: http
    pattern: "staging-*.acme.test"
    allowed_methods: [GET, POST, PUT, DELETE, PATCH, OPTIONS]
    allowed_ports: [443]
  - kind: code
    pattern: "git@github.com:acme/web-app.git"
    branch: "main"
out_of_scope:
  - kind: http
    pattern: "admin-internal.acme.test"
focus_areas: ["auth", "bola", "ssrf"]
post_exploit_authorized: false
parent_engagement_id: 20260410-acme-staging
notes: "Quarterly follow-up to 20260410 run."
```

## 6. Example — CTF engagement

```yaml
engagement_id: 20260516-htb-blackfield
mode: ctf
dev: true
target_type: htb
flag_format: "HTB\\{[a-f0-9]{32}\\}"
time_window:
  start: "2026-05-16T18:00:00Z"
  end:   "2026-05-17T06:00:00Z"
contact_tree:
  primary:
    name: "Rex Kenyon"
    discord: "Rex#0001"
in_scope:
  - kind: net
    pattern: "10.10.10.192/32"
    allowed_ports: [0-65535]
    protocols: [tcp, udp]
out_of_scope: []
notes: "Personal HTB lab — full destructive permissions, DoS still banned."
```

---

## 7. Validation rules (enforced by `scope-validator`)

1. `mode: production` requires `signature` present and verifiable.
2. `time_window.end > time_window.start`.
3. `in_scope` non-empty.
4. Every `out_of_scope` entry's `pattern` must overlap at least one `in_scope` pattern, else warn (likely a typo).
5. CTF mode: `flag_format` must compile as a regex.
6. No `in_scope` http pattern may target `localhost`, `127.0.0.0/8`, or RFC1918 ranges **unless** `mode: ctf`.
7. `rate_limit.requests_per_second` ≤ 100 (anything higher is a `scope-validator` error; operator must justify in `notes` and bump explicitly).
8. If `parent_engagement_id` is set, the referenced engagement directory must exist on disk.

Failure-closed: any validation error blocks engagement start. `scope-validator` emits a structured error list and the orchestrator refuses to dispatch any sub-agent.

---

## 8. Schema versioning

```yaml
schema_version: "0.4"     # implicit if absent; defaults to current version
```

When the schema changes, bump `schema_version` and update `scope-validator` to read both versions during the transition window.

---

## 9. What this doc does NOT cover

- The exact regex set for PII detection — see `SYSTEM_PROMPT.md §3 #11` and the (future) `pii-detector` skill spec.
- The audit-log hash-chain algorithm — see `audit-log-hash-chain.md`.
- Sub-agent crash recovery — see `sub-agent-crash-semantics.md`.
- Finding dedup keys — see `finding-store-dedup-key.md`.
