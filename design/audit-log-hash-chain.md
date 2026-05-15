# Audit Log Hash Chain (DRAFT v0.4)

Every active action in every engagement appends one line to `engagements/<id>/logs/audit.jsonl`. The file is append-only and hash-chained so any tampering — by an agent, an operator, or a malicious target with file access — is detectable.

This doc is the contract `evidence-vault` writes against and that `report-agent` and any future verifier read.

---

## 1. File location and format

```
engagements/<engagement-id>/logs/audit.jsonl
```

One JSON object per line. UTF-8. LF line endings. No trailing comma. Lines never edited or deleted. If a sub-agent needs to mark a prior entry as superseded, it appends a *new* line with `kind: supersede` referencing the prior line's `this_hash`.

---

## 2. Line schema

```json
{
  "seq": 0,
  "ts": "2026-05-15T18:42:11.123Z",
  "engagement_id": "20260515-acme-staging",
  "phase": "verification",
  "agent": "exploit-agent",
  "skill": "exploit-runner",
  "kind": "active-action",
  "finding_id": "F-007",
  "attempt_id": "F-007/A-2",
  "scope_guard_decision": "allow",
  "target": "https://staging-api.acme.test/v1/users/42",
  "action": "GET with id=42 in Authorization=Bearer <role:user-b>",
  "rate_limited_to": "8 rps",
  "tool_version": "curl 8.7.1",
  "previous_hash": "0000000000000000000000000000000000000000000000000000000000000000",
  "this_hash":     "9f3c2a1e..."
}
```

| Field | Required | Notes |
|---|---|---|
| `seq` | yes | Monotonically increasing integer starting at 0. Catches gaps. |
| `ts` | yes | ISO 8601 UTC with millisecond precision. |
| `engagement_id` | yes | Slug. Lets the verifier reject lines that drifted from another engagement. |
| `phase` | yes | One of: `setup` \| `reconnaissance` \| `enumeration` \| `triage` \| `verification` \| `reporting` \| `cleanup` \| `retro`. |
| `agent` | yes | Which sub-agent (or `orchestrator`). |
| `skill` | yes | Which skill made the active call (or `none` for orchestrator-direct actions). |
| `kind` | yes | `active-action` \| `evidence-write` \| `notification` \| `supersede` \| `mode-change` \| `phase-exit`. |
| `finding_id` | when applicable | `F-NNN`. Omit for pre-finding work like recon scans. |
| `attempt_id` | when applicable | `F-NNN/A-K`. Required for verification attempts and 0-day sub-loop steps. |
| `scope_guard_decision` | required for `kind: active-action` | `allow` \| `deny` \| `config_error`. A `deny` line is still appended (so denial attempts are auditable). |
| `target` | required for active actions | Full URL, host:port, or asset identifier. |
| `action` | required for active actions | One-line description of what was attempted. |
| `rate_limited_to` | required for active actions | E.g., `"8 rps"`. Records the active rate ceiling. |
| `tool_version` | required for active actions | E.g., `"nuclei v3.2.4, templates @ a1b2c3d"`. |
| `previous_hash` | yes | 64 hex chars. Genesis line uses 64 zeros. |
| `this_hash` | yes | 64 hex chars. Computed per §3. |

Extra fields are allowed (e.g., `dev_reasoning_ref` pointing at a `logs/reasoning.jsonl` line in dev mode) but must not appear inside the hash payload — see §3.

---

## 3. Hash chain algorithm

```
payload = canonical_json(line_without_hash_fields)
this_hash = sha256_hex(previous_hash + "\n" + payload)
```

Where:

- `line_without_hash_fields` is the JSON line minus `previous_hash` and `this_hash` and minus any optional `_meta_*` fields. Everything else stays in.
- `canonical_json` means: keys sorted lexicographically, no insignificant whitespace, UTF-8, no trailing newline. Equivalent to Python `json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`.
- `previous_hash + "\n" + payload` is byte concatenation. The `\n` is literal LF (0x0A).
- `sha256_hex` is lowercase hex output.

Genesis line:

```
previous_hash = "0" * 64
```

---

## 4. Verification procedure

A verifier (the `report-agent` does this implicitly at the end of every run; an operator-side script does it on demand) walks the file:

1. Read line N. Parse JSON.
2. Recompute `this_hash` per §3.
3. Assert it equals the line's `this_hash` field.
4. Assert `previous_hash` equals line N-1's `this_hash` (or 64 zeros if N == 0).
5. Assert `seq` equals N.
6. If any assertion fails, mark the chain `broken` and report which line.

A broken chain blocks report generation. The orchestrator surfaces a `chain-integrity-failure` notification via `notification-discord` and refuses to emit any client-facing report until the operator inspects the breakage.

---

## 5. Concurrency

Active actions are serial across an engagement (see `SYSTEM_PROMPT.md §4`), so audit-log writes are naturally serialized. Implementation must still:

1. Take a file lock (`flock` style) around the read-prev → compute-hash → append sequence.
2. fsync after the append.
3. Release lock.

Without these, two near-simultaneous writes can race and produce a fork that the verifier will reject.

---

## 6. Supersede / correction lines

When an agent needs to mark a prior line as inaccurate (e.g., it later determines a `scope_guard_decision: allow` was based on stale rules), it appends a new line:

```json
{
  "kind": "supersede",
  "superseded_seq": 142,
  "superseded_hash": "9f3c2a1e...",
  "reason": "scope rule v2 retroactively forbade this action — see operator note 2026-05-16",
  ...
}
```

The original line stays untouched. The chain remains intact. Verifiers reading the chain see both lines and use the most recent.

---

## 7. What this doc does NOT cover

- Encryption at rest: the audit log is plain text. Disk-level encryption is operator responsibility.
- Off-machine tamper-evidence: if the operator wants Merkle-rooting to an external service (Sigstore, an internal time-stamp authority), that's a future skill, not in scope here.
- Log retention/rotation: audit logs live for the life of the engagement directory. Engagement directories are operator-managed.
