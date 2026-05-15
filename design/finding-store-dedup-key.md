# `finding-store` Dedup Key & Finding/Attempt ID Model (DRAFT v0.4)

The `finding-store` skill persists every candidate and every confirmed finding in a way that lets the system (and `diff-watcher` across engagements) recognize "this is the same bug we found before." This doc specifies:

1. The finding ID format (`F-NNN`).
2. The per-attempt sub-ID format (`F-NNN/A-K`).
3. The cross-engagement dedup key.
4. How `diff-watcher` walks the chain across `parent_engagement_id`.

---

## 1. Finding IDs

Within a single engagement, every candidate (confirmed or not) gets a unique ID:

```
F-001, F-002, F-003, ...
```

Allocated monotonically by `finding-store` at first write. `F-NNN` is zero-padded to 3 digits; if an engagement exceeds 999 findings, expand to 4 digits (`F-NNNN`) and update this spec.

ID assignment is **per-engagement**, not global. The cross-engagement dedup key (§3) is the thing that links findings across runs.

---

## 2. Attempt sub-IDs

Each verification or exploitation **attempt** against a finding gets a sub-ID:

```
F-007/A-1, F-007/A-2, F-007/A-3, ...
```

| Use case | When sub-ID is required |
|---|---|
| Single-attempt confirmation in `exploit-agent` | `F-NNN/A-1` records the one attempt. Required for audit trail. |
| 0-day sub-loop (≤10 attempts per `PLAN.md §6.7`) | `F-NNN/A-1` through `F-NNN/A-10`. The attempt cap is enforced by `finding-store` refusing to allocate `F-NNN/A-11`. |
| Retry after sub-agent crash | New attempt sub-ID. Prior `F-NNN/A-K` lines stay in the audit log untouched. |
| Re-verification across engagements | A new engagement's first attempt against the same dedup key starts at `F-NEW-NNN/A-1` in the new engagement, but `finding-store` records the cross-engagement link via §3. |

Every attempt sub-ID appears in `logs/audit.jsonl` (per `audit-log-hash-chain.md` §2). Every attempt has its own evidence subdirectory:

```
engagements/<id>/evidence/F-007/A-1/{request.http, response.http, screenshot.png}
engagements/<id>/evidence/F-007/A-2/{...}
```

---

## 3. Cross-engagement dedup key

The dedup key is a composite hash, stored alongside every finding record:

```
dedup_key = sha256_hex(content_hash + "::" + asset_fingerprint)
```

### 3.1 `content_hash`

```
content_hash = sha256_hex(canonical_json({
  "class": "<finding class slug>",        // e.g., "xss-reflected", "sqli-blind-time", "bola-horizontal"
  "cwe":   "<primary CWE ID>",            // e.g., "CWE-79"
  "payload_template": "<normalized>",     // see §3.3
  "sink": "<normalized sink>"             // see §3.4
}))
```

`class` is one of the slugs in `corpus/cwe/` aligned to `vuln-knowledge`'s class taxonomy. `finding-store` rejects writes where `class` isn't in the registered set (this prevents typo'd classes from breaking dedup).

### 3.2 `asset_fingerprint`

For HTTP assets:

```
asset_fingerprint = sha256_hex(canonical_form(asset_url))

canonical_form(url):
  scheme = lowercase(scheme)
  host   = lowercase(host)
  port   = explicit_port_or_default_for_scheme
  path   = url.path with trailing-slash stripped, percent-encoding normalized
  param  = lowercase(name_of_vulnerable_parameter) if applicable, else omitted
  return "scheme://host:port/path?param=<PARAM_NAME>"
```

For network assets: `proto://ip:port` after IP-canonicalization (no leading zeros in octets).

For cloud assets: provider-scoped — `aws:account:resource-arn`, `gcp:project:resource-id`.

For code assets: `repo-url@<commit-or-branch>:<path>:<line-range>`.

### 3.3 `payload_template` normalization

To make the same logical bug hash to the same key regardless of incidental payload variation:

1. Replace any concrete value the operator's `session-manager` provided (cookie value, token, user ID belonging to a test role) with a placeholder: `<TOKEN>`, `<USER_ID>`, `<ROLE>`.
2. Replace numeric IDs with `<N>`.
3. Lowercase HTTP method names.
4. Strip any per-run nonce values.

The normalizer is part of `finding-store` and its rules are versioned (`normalizer_version: "1"` recorded with each finding). If the normalizer changes, recompute keys on read.

### 3.4 `sink` normalization

For code-analysis findings (`code-analyzer` / `taint-tracer` outputs), `sink` is the API or syntax node where tainted data lands — e.g., `node.execSync`, `String.format`, `document.innerHTML`. Normalized to the language's fully-qualified canonical form when possible.

For black-box findings without code context, `sink` is omitted from the hash.

---

## 4. The finding record on disk

Each finding gets a record under `finding-store`'s persistence:

```
engagements/<id>/findings/.store/<F-NNN>.json
```

```json
{
  "finding_id": "F-007",
  "engagement_id": "20260515-acme-staging",
  "class": "bola-horizontal",
  "cwe": "CWE-639",
  "status": "confirmed",
  "severity": "medium",
  "cvss_v3_1_score": 6.5,
  "cvss_v4_0_score": 6.1,
  "dedup_key":   "9f3c2a1e...",
  "content_hash":      "f7e6...",
  "asset_fingerprint": "12ab...",
  "normalizer_version": "1",
  "attempts": [
    {"attempt_id": "F-007/A-1", "result": "confirmed", "evidence_path": "evidence/F-007/A-1"}
  ],
  "first_seen_engagement": "20260410-acme-staging",
  "first_seen_finding_id": "F-019",
  "occurrences": [
    {"engagement_id": "20260410-acme-staging", "finding_id": "F-019"},
    {"engagement_id": "20260515-acme-staging", "finding_id": "F-007"}
  ]
}
```

`first_seen_*` and `occurrences[]` are maintained by `diff-watcher` (next section) on every new engagement that has a `parent_engagement_id`.

---

## 5. `diff-watcher` walk

When a new engagement starts with `parent_engagement_id: <prior-id>` (per `scope-schema.md` §3), `diff-watcher`:

1. Reads `engagements/<prior-id>/findings/.store/*.json`.
2. Builds an in-memory map: `dedup_key → (engagement_id, finding_id)`.
3. Recurses via the prior engagement's own `parent_engagement_id` until the chain terminates. Cap the walk at 50 generations to avoid pathological loops.
4. During the new engagement, every time `finding-store` writes a record, `diff-watcher` checks the new record's `dedup_key` against the map:
   - **Match found:** update `first_seen_*` to the earliest occurrence, append the new engagement to `occurrences[]`, mark the finding `regression: true` if the prior occurrence was already remediated (i.e., its prior engagement's final `status` was `confirmed` and the parent had a remediation date).
   - **No match:** finding is genuinely new in this engagement series; `first_seen_*` = this engagement.

The report-agent uses `regression: true` to surface a "previously reported, now reappears" callout in the technical report.

---

## 6. Edge cases

- **Same class, different parameter, same host:** different `asset_fingerprint`s (param name differs), so different `dedup_key`s — treated as distinct findings. Correct, because remediation is per-parameter.
- **Same bug, host renamed between engagements:** `asset_fingerprint` differs, so dedup misses. Operator can manually link by editing the new finding's `occurrences[]` to point at the prior `engagement_id, finding_id`. `diff-watcher` respects manual edits and won't overwrite.
- **Bug with no good asset fingerprint (e.g., reasoning-derived design flaw):** `asset_fingerprint` set to `"design::<class>"`. Dedup falls back to `content_hash` only — coarser but better than nothing.
- **Reclassified finding mid-run:** `class` change recomputes `dedup_key`. `finding-store` writes a new record and marks the old one `superseded_by: F-NEW`. Both stay on disk for audit.

---

## 7. What this doc does NOT cover

- Severity recomputation across engagements (`cvss-calculator` skill spec, future).
- The full report-agent presentation of regressions (lives in `report-builder` skill spec).
- Manual operator-side link/unlink CLI — operator tooling, lives in `/scripts/` (`link-findings.py` is a candidate name; not yet specified).
