# OpenClaw Pentester — Integrated MVP Handoff

This file is the first-read document for the fresh cowork session that receives `/design/` inside the Kali Linux VM.

The design folder is the source of truth. The VM implementation session should update the real repo from these docs. On the original host, do not edit anything outside `/design/`.

---

## 1. Implementation posture

Build an **integrated MVP bundle**, not a foundation-only prototype.

The operator's first useful test case is a complete authorized lab/CTF pentest lifecycle. That means the MVP components need to exist and interoperate in one coordinated build, even when individual skills start with conservative v1 behavior.

The target outcome is:

```
engagement setup
  -> scope validation
  -> recon
  -> enumeration
  -> vulnerability triage
  -> verification
  -> reporting
  -> cleanup
  -> retro proposal queue
```

Do not wait to implement later lifecycle skills just because the foundation is still young. Instead, give every MVP skill a stable CLI/API, structured JSON I/O, clear degraded-mode behavior, and enough real behavior to participate in the end-to-end run.

---

## 2. Read these design docs first

Read in this order:

1. `PLAN.md`
2. `SYSTEM_PROMPT.md`
3. `scope-schema.md`
4. `audit-log-hash-chain.md`
5. `sub-agent-crash-semantics.md`
6. `finding-store-dedup-key.md`

`RESPONSES.md` and `Design Updates.md` are historical context. Use `PLAN.md v0.5` and the companion specs as current ground truth.

---

## 3. Filesystem boundaries

In the Kali VM implementation repo:

- Existing `/AGENTS.md`, `/README.md`, `/corpus/`, `/skills/scope-guard/`, and `/skills/vuln-knowledge/` are preserved unless this design explicitly requires compatible updates.
- New skills live under `/skills/<skill-name>/`.
- New agents live under `/agents/<agent-name>/`.
- Engagement runtime data lives under `/engagements/<engagement-id>/`.
- Personal operator knowledge lives under `/knowledge/`.
- Operator-side scripts live under `/scripts/`.

The existing repo uses `SKILLS.md` for skill documentation. Prefer that convention for new skills unless the local repo has been migrated.

---

## 4. MVP bundle to implement together

### Foundation and state

- `engagement-init`
- `scope-validator`
- v0.4-compatible update to `scope-guard`
- `evidence-vault`
- `finding-store`
- `cvss-calculator`
- `improvements-queue`
- Shared helpers for canonical JSON, schema loading, path safety, audit hashing, structured errors, and tool-result envelopes

### Knowledge

- Existing `vuln-knowledge`
- `personal-knowledge`
- PII/prompt-redaction helper required by `SYSTEM_PROMPT.md §3 #11`

### Recon, enum, and exploit operations

- `asset-graph`
- `session-manager`
- `http-history`
- `screenshot-er`
- `secret-scanner`
- `safe-browsing`
- `exploit-runner`
- `payload-mutator`

### Code analysis

- `code-analyzer`
- `taint-tracer`
- `sast-bridge`

Initial code-analysis implementations can be conservative wrappers around Semgrep, CodeQL when available, and simple static patterns. They must return the compact JSON contract described in `PLAN.md §17`.

### Reporting, disclosure, and operations

- `report-builder`
- `disclosure-prep`
- `diff-watcher`
- `ctf-flag-detector`
- `notification-discord`

`notification-discord` may begin as a structured local stub if the real OpenClaw bot endpoint is not configured. It must still expose the same result envelope and failure modes.

### Agents

- `orchestrator`
- `recon-agent`
- `enum-agent`
- `vuln-agent`
- `exploit-agent`
- `report-agent`
- `retro-agent`

`retro-agent` can be minimal, but it must exist and write operator-review proposals so the lifecycle closes cleanly.

### Stretch

- `traffic-replay`

Keep `traffic-replay` out of the integrated MVP unless the first authorized target requires HAR/pcap replay to complete the lifecycle.

---

## 5. Build order inside the integrated MVP

1. Implement shared contracts: canonical JSON, schema loading, audit hash-chain append/verify, path safety, structured errors, and uniform JSON result envelopes.
2. Create every MVP skill directory and CLI entrypoint.
3. Wire storage skills: engagement init, evidence vault, finding store, audit log, state file, and dispatch/crash directories.
4. Wrap every target-touching operation so it calls `scope-guard` first and emits an audit entry.
5. Add agent prompts and tool allowlists.
6. Wire the orchestrator phase machine.
7. Run one authorized lab/CTF engagement end to end and fix integration gaps.

The rule is "all MVP components present and integrated," not "all MVP components maximally powerful."

---

## 6. Acceptance criteria

- A fresh Kali VM can implement the repo from `/design/`.
- A single CTF/local-VM engagement runs through setup, recon, enum, triage, verification, reporting, cleanup, and retro.
- Every active action has a `scope-guard` decision and audit entry.
- Every confirmed finding has evidence in the vault and a `finding-store` record.
- Reports are generated from stored findings, not transient agent memory.
- Crashes leave recoverable or clearly quarantined partial state.
- 0-day logic is gated by confidence `>= 0.90`, attempt cap `<= 10`, no weaponization, and operator notification.

---

## 7. Known implementation risk to resolve first

The existing `scope-guard` skill in the current repo may use an older `scope.yaml` shape (`window`, object-style `in_scope`, `rate_limits`). The current design uses `scope-schema.md v0.4` (`time_window`, list-style scope entries, `rate_limit`). Resolve this early by making `scope-validator` authoritative and updating `scope-guard` to support v0.4. A temporary legacy compatibility path is acceptable during migration, but v0.4 is the target contract.

Do not begin autonomous active testing until `scope-validator`, `scope-guard`, audit logging, and evidence/finding persistence agree on the same engagement schema.
