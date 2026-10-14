# AI Pentester Agent — Design Plan (DRAFT v0.5)

**Status:** Draft for review. Nothing in `/Users/openclaw/ai-pentester/skills/`, `/corpus/`, `AGENTS.md`, or `README.md` is modified by this plan. New design files live under `/design/`. Future agents under `/agents/<agent-name>/`. Future skills under `/skills/<skill-name>/`. Future personal knowledge under `/knowledge/`.

**Reference points:** XBOW (autonomous bug-hunting agent), Project Mythos (code-analysis-driven offensive security). Goal is XBOW-class lifecycle coverage with Mythos-class code-reasoning depth, achieved through multi-agent decomposition rather than one giant context.

**v0.2 changelog:** Skills vs agents distinction added; multi-agent architecture; Kali Linux VM target environment; 0-day discovery gated workflow; explicit no-DoS rule; CTF/development mode flag; knowledge directory split (corpus = external, knowledge = personal); self-improvement workflow with operator review queue; reporting timing decision; technical vs non-technical report split.

**v0.3 changelog:** 0-day confidence threshold raised 0.85 → 0.9; full new-skill set promoted to MVP per operator request; Discord chosen as operator notification channel; PII/sensitive-info sanitization rule for `/knowledge/target-notes/`; CTF mode explicitly permits account creation and permission edits in pursuit of flags (DoS still banned); sub-agent dispatch question resolved (Claude Code `Agent` tool + filesystem coordination as backup); `disclosure-prep` skill added for third-party 0-day handling.

**v0.4 changelog:** Confidence-floor stragglers fixed (every active reference now reads 0.90; historical changelogs preserved). Round-3 questions resolved and folded into §17. Duplicate section numbering corrected — `What This Plan Does NOT Touch` is now §18. PII sanitizer policy tightened: **redact-and-warn on read AND a pre-flight PII check on every outbound model prompt** — the operator reviews any redacted prompt before it leaves the orchestrator. CTF-mode reporting policy clarified: minimal artifacts only — `findings/*.md` + `run-log.md`, no exec PDF, no DOCX, no SARIF, no `disclosure-prep`. Finding ID model extended to per-attempt sub-IDs (`F-NNN/A-K`). Engagement-series linkage via `parent_engagement_id` in `scope.yaml`. Four companion spec docs added under `/design/` — `scope-schema.md`, `audit-log-hash-chain.md`, `sub-agent-crash-semantics.md`, `finding-store-dedup-key.md`. These four are **required reading before implementation begins**.

**v0.5 changelog:** Implementation strategy changed from sequential foundation milestones to an **integrated MVP bundle**. The first useful test case is a complete authorized lab/CTF pentest lifecycle, so the Kali VM cowork session should implement nearly all MVP skills and agents together with conservative v1 behavior rather than waiting for later milestones. `traffic-replay` remains stretch. `retro-agent` is promoted to MVP-minimal so the lifecycle does not dead-end after reporting. `design/IMPLEMENTATION_HANDOFF.md` is added as the first-read handoff for the fresh cowork session. On this host, only `/design/` is edited; implementation changes happen in the Kali VM.

---

## 1. Mission

Build a **multi-agent system** — codename **OpenClaw Pentester** — that, given a signed engagement scope, autonomously executes the full blackbox penetration testing lifecycle:

1. Reconnaissance and asset discovery
2. Enumeration and surface mapping
3. Vulnerability identification (automated + reasoned + 0-day discovery within strict bounds)
4. Verification and exploitation (with proof-of-impact)
5. Evidence capture
6. Documentation and reporting (machine-readable + non-technical exec + technical client-ready)

The system must produce findings that are **defensible** — every claim backed by captured request/response pairs, command output, or screenshots, and grounded in the local corpus and personal knowledge base rather than model recall.

---

## 2. Non-Goals (for this revision)

- **No DoS or DDoS, ever.** Not even on CTF targets. Not even with operator confirmation. The agent does not flood, does not exhaust resources, does not run sustained high-RPS attacks. This is hard-coded into `scope-guard` and the system prompt.
- No persistent C2 / implant deployment.
- No social engineering or human-targeted phishing.
- No movement of money or initiating financial transactions on the target.
- No self-modification of `scope-guard` rules during a run.

**Allowed (with strict gating):** 0-day discovery — see §6.

---

## 3. What Already Exists (Preserved As-Is)

| Component | Path | Role |
|---|---|---|
| OpenClaw `AGENTS.md` | `/AGENTS.md` | Generic OpenClaw startup file. Defines workspace conventions. The pentester orchestrator extends, never replaces, this. |
| `scope-guard` **skill** | `/skills/scope-guard/` | Mandatory pre-flight check for every active action. |
| `vuln-knowledge` **skill** | `/skills/vuln-knowledge/` | BM25 FTS5 lookup over `/corpus/`. |
| `corpus/` | `/corpus/` | External public knowledge: HackTricks, PayloadsAllTheThings, OWASP WSTG, OWASP CheatSheets, MITRE CWE, nuclei-templates. Operator manages refresh via git. |
| `README.md` | `/README.md` | Project intent. |

**Rule:** every new agent and every new skill assumes these exist and calls them. `scope-guard` runs before every active action. `vuln-knowledge` runs before every vulnerability claim.

---

## 4. Skills vs Agents — The Distinction

This is the architectural pivot from v0.1.

| | **Skill** | **Agent** |
|---|---|---|
| Lives in | `/skills/<name>/` | `/agents/<name>/` |
| Has its own context window? | No — runs in its caller's context | Yes — own conversation, own model choice |
| Form | Procedural: SKILLS.md + scripts | Conversational: AGENT.md + system prompt + skill access list |
| State | Stateless or short-lived | Maintains its own working state for the task |
| Examples | `scope-guard` (gate), `vuln-knowledge` (retrieval), `report-builder` (transform) | `recon-agent`, `vuln-agent`, `exploit-agent`, `report-agent` |

**Heuristic:** if the work is a deterministic transform (input → output) or a check, it's a skill. If the work requires reasoning, looping, calling other tools, and accumulating state, it's an agent.

---

## 5. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       Orchestrator Agent (Opus 4.6)                     │
│  reads scope.yaml · plans phases · dispatches sub-agents · merges state │
└───┬──────────┬──────────┬──────────┬──────────┬──────────┬──────────────┘
    │          │          │          │          │          │
    ▼          ▼          ▼          ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
│ recon- │ │ enum-  │ │ vuln-  │ │exploit-│ │ report-│ │ retro- │
│ agent  │ │ agent  │ │ agent  │ │ agent  │ │ agent  │ │ agent  │
│(Sonnet)│ │(Sonnet)│ │(Sonnet)│ │(Opus)  │ │(Sonnet)│ │(Opus)  │
└───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘
    │          │          │          │          │          │
    └──────────┴──────────┴──────────┴──────────┴──────────┘
                              │
       ┌──────────────────────┼─────────────────────────────┐
       ▼                      ▼                             ▼
┌──────────────┐    ┌────────────────┐          ┌──────────────────────┐
│  Skills      │    │ Knowledge      │          │ Engagement workspace │
│  scope-guard │    │ corpus/  (ext) │          │ engagements/<id>/    │
│  vuln-       │    │ knowledge/     │          │  scope.yaml          │
│   knowledge  │    │   (personal)   │          │  state.json          │
│  evidence-   │    │                │          │  recon/ enum/        │
│   vault      │    │                │          │  findings/ evidence/ │
│  finding-    │    │                │          │  report/ logs/       │
│   store      │    │                │          │                      │
│  report-     │    │                │          │                      │
│   builder    │    │                │          │                      │
│  exploit-0d  │    │                │          │                      │
└──────────────┘    └────────────────┘          └──────────────────────┘
```

**Why multi-agent:** each phase has different reasoning needs and different context budgets. Recon produces lots of low-value text (port scan output) that would blow the orchestrator's context. Exploit reasoning requires deep technical chain-of-thought that doesn't need recon's noise. By giving each phase its own agent with its own context, we keep each one focused and let us pick a cost-appropriate model per role.

**How they coordinate:**
- The orchestrator is the only agent the operator talks to directly.
- Sub-agents receive a structured task spec from the orchestrator and return a structured result (JSON summary + paths to artifacts on disk).
- Sub-agents never call each other directly. The orchestrator owns sequencing.
- All persistent state lives on disk in `engagements/<id>/`. No agent depends on another's in-context memory.

**Three invariants preserved across all agents:**

1. **No active action bypasses `scope-guard`.**
2. **No claim bypasses `vuln-knowledge` grounding.**
3. **No finding leaves any agent without evidence in the vault.**

---

## 6. Lifecycle Phases

The orchestrator runs an explicit phase machine; each phase dispatches a sub-agent that emits artifacts the next phase consumes.

### 6.1 Engagement Setup (orchestrator only)

- Operator authors `engagements/<engagement-id>/scope.yaml`.
- Orchestrator reads scope, summarizes back, confirms.
- Allocates `engagements/<id>/{recon,enum,findings,evidence,report,logs,improvements}`.

### 6.2 Reconnaissance — `recon-agent`

**Tools (Kali VM defaults — see §8 for the full assumed toolchain):** `nmap`, `subfinder`, `amass`, `dnsx`, `httpx`, `tlsx`, `naabu`, `whatweb`, `theHarvester`, `dnsenum`, plus native HTTP for CT logs / Wayback / GitHub.

**Out (require explicit operator opt-in):** credential stuffing against the target's auth, paid-data breach checks.

**Artifact:** `engagements/<id>/recon/asset-graph.json`.

### 6.3 Enumeration — `enum-agent`

**Tools (Kali defaults):** `ffuf`, `gobuster`, `dirb`, `katana`, `gau`, `arjun`, `wfuzz`, `nikto`, `wpscan`, `enum4linux-ng`, `smbclient`, `smbmap`, `crackmapexec`, `snmp-check`, `onesixtyone`, native HTTP for API spec scraping and GraphQL introspection.

**Cloud-specific (if scope permits):** AWS CLI for public S3, `pacu`, `cloudfox` (install if missing — operator-approved).

**Mobile:** `jadx`, `apktool`, `class-dump`, `frida` (static side only at this phase).

**Artifact:** `engagements/<id>/enum/surface-map.json`.

### 6.4 Vulnerability Triage — `vuln-agent`

For every surface element:

1. Run `nuclei` filtered to relevant templates.
2. Run reasoned manual checks for OWASP Top 10 + WSTG categories `nuclei` can't cover (BOLA/IDOR, business logic, race conditions, blind-side-channel SSRF).
3. **Code analysis (Mythos-style)** when source / decompiled artifacts are available — this is the core differentiator. The vuln-agent reasons about *why* code is vulnerable, not just whether a regex matches.
4. Query `vuln-knowledge` for class context before promoting any candidate.

**Artifact:** `engagements/<id>/findings/candidates.jsonl`.

### 6.5 Verification & Exploitation — `exploit-agent`

For each candidate, in order of impact × confidence:

1. Re-run `scope-guard` (action class may have changed).
2. Construct the **smallest** payload that proves the bug.
3. Capture request, response, server-side effect, screenshot if browser-rendered.
4. Stop at proof. No deeper pivoting unless scope explicitly authorizes post-exploitation impact demo.
5. Destructive-class candidates (mutating state, account takeover, sustained DoS) — DoS/DDoS is **never** allowed; other destructive actions pause for fresh operator confirmation, even within signed scope.
6. **0-day discovery sub-loop** (see §6.7) — gated, capped, high-confidence-only.

**Artifact:** `engagements/<id>/evidence/<finding-id>/`.

### 6.6 Reporting — `report-agent`

**When does the agent write?** End of engagement, after all stretch milestones (network, cloud, mobile) finish. Per-finding markdown is written *during* exploit-agent's work (so nothing is lost if the run is interrupted), but the **synthesis pass** — exec summary, technical narrative, attack-chain diagram, CVSS calibration — happens at the end when the agent has full surface visibility.

**Two distinct deliverables:**
- **Non-technical executive report** — for leadership / non-technical stakeholders. Plain English, business-impact framing, no jargon, no CVSS vectors. ≤5-page PDF.
- **Technical client report** — for the customer's security team. Full attack chains, CVSS 3.1 + 4.0 vectors, reproduction steps, code snippets, remediation with cheatsheet citations. DOCX → PDF.

Plus the machine-readable / learning artifacts:
- `report/findings.json`
- `report/findings.sarif`
- `report/run-log.md`

**Resilience checkpoint:** at the end of each phase, the report-agent generates a one-page interim status doc (`report/interim-<phase>.md`). Cheap, prevents total loss if a later phase crashes. Not the same as the final synthesis.

### 6.7 0-Day Discovery (Gated Sub-Loop within `exploit-agent`)

**Why it's a sub-loop, not its own phase:** 0-day discovery is *opportunistic* — it happens when the agent encounters a candidate that doesn't match anything in `vuln-knowledge` but the surface evidence (e.g., unusual error response, parser confusion, type confusion) suggests a real underlying bug.

**Hard constraints:**
1. **Confidence floor: 0.90.** The agent computes a confidence score from corpus distance + behavioral signal strength + reproducibility across attempts. Below 0.90, the candidate is logged as `interesting` in `findings/candidates.jsonl` with full evidence and *not* pursued. (Raised from 0.85 in v0.2 to reduce rabbit-holing.)
2. **Attempt cap: 10.** For any single 0-day candidate, the agent gets 10 verification attempts. If the bug isn't reproduced in 10 attempts, it's parked as `unverified-anomaly` with all attempts logged, and the agent moves on. No infinite loops.
3. **No exploit weaponization.** The agent demonstrates the bug exists; it does not write a reusable exploit, does not chain it into RCE if the bug is "just" memory corruption, does not store payload artifacts that would survive past report generation.
4. **Operator notification on every promotion (via Discord).** When a candidate crosses the 0.90 threshold, the orchestrator posts a notification to the operator's Discord channel before the exploit-agent attempts it. Operator may veto.
5. **Third-party dependencies handled separately:** 0-day discovery against in-scope targets only. If the agent finds a 0-day in a third-party dependency, the `disclosure-prep` skill drafts a coordinated-disclosure-ready vendor advisory (under `engagements/<id>/disclosures/<cve-class>/`) for operator review. The advisory is not sent automatically.

**Output:** confirmed 0-days appear in the report under a separate `Novel Findings` section, clearly distinguished from CVE-class findings, with a reduced-confidence marker until the operator validates.

### 6.8 Cleanup

- Enumerate test accounts, files uploaded, rows inserted.
- Confirm evidence vault is hash-chained and complete.
- Note any gaps explicitly.

---

## 7. Skills + Agents Roadmap

### 7.1 Skills (procedural, no own context)

All skills live under `/skills/` (operator confirmed).

Existing — preserved:
- `scope-guard`
- `vuln-knowledge`

New skills. Per operator direction, all listed below are **MVP** unless explicitly marked otherwise. For implementation, do not treat the tables below as a long sequential release plan. The Kali VM cowork session should scaffold and wire the full MVP bundle together, using conservative v1 implementations where needed, because the first acceptance test is an end-to-end pentest lifecycle.

**Infrastructure & state (built first — every other skill depends on these):**

| # | Skill | Purpose | Tier |
|---|---|---|---|
| 1 | `engagement-init` | Bootstraps `engagements/<id>/` from template, validates `scope.yaml` schema, seeds the audit log, sets mode flags | MVP |
| 2 | `scope-validator` | Lints `scope.yaml` for ambiguities (e.g., wildcards conflicting with explicit out-of-scope entries); warns operator before engagement starts | MVP |
| 3 | `evidence-vault` | Atomic write of req/resp/screenshots, hash-chained audit log | MVP |
| 4 | `finding-store` | CRUD for finding records, content-hash + asset-fingerprint dedupe across runs, persistence | MVP |
| 5 | `cvss-calculator` | CVSS 3.1 + 4.0 vectors → score + business-context override applier; auditable scoring | MVP |
| 6 | `improvements-queue` | Read/write the operator-review proposal queue (see §12) | MVP |

**Knowledge & retrieval:**

| # | Skill | Purpose | Tier |
|---|---|---|---|
| 7 | `personal-knowledge` | BM25 over `/knowledge/` (mirror of `vuln-knowledge` over `/corpus/`) | MVP |

**Active operations (recon / enum / exploit):**

| # | Skill | Purpose | Tier |
|---|---|---|---|
| 8 | `asset-graph` | Graph data structure with query API over hosts, services, endpoints, parameters, technologies, observed authentication boundaries. Recon + enum write; vuln + exploit read | MVP |
| 9 | `session-manager` | Stores cookies/tokens per role, refreshes when expired, lets sub-agents request "test as role X." Critical for BOLA/IDOR/horizontal-priv-esc | MVP |
| 10 | `http-history` | Append-only log of every HTTP request + response, indexed by target/endpoint/parameter. Powers diff-based payload reasoning without re-firing | MVP |
| 11 | `screenshot-er` | Playwright wrapper that captures evidence screenshots with annotation overlays | MVP |
| 12 | `secret-scanner` | Pattern + entropy hunt for keys/tokens/credentials in JS bundles, mobile binaries, public S3 (Trufflehog-equivalent) | MVP |
| 13 | `safe-browsing` | Pre-checks any OSINT-discovered URL against malware/lure lists before agent navigates | MVP |
| 14 | `exploit-runner` | Scope-guarded HTTP / shell sender that records to evidence vault | MVP |
| 15 | `payload-mutator` | Adapts corpus / personal-knowledge payloads to target stack + observed filtering | MVP |

**Code analysis (Mythos-class differentiator — operator confirmed: keep as skills, not a separate agent, to preserve vuln-agent context):**

| # | Skill | Purpose | Tier |
|---|---|---|---|
| 16 | `code-analyzer` | Static analysis on decompiled JS/Java/.NET/binary code. Sources, sinks, dataflow paths, structured confidence. Returns concise findings, not raw code, to keep caller context lean | MVP (web/mobile), Stretch (native binaries) |
| 17 | `taint-tracer` | Sub-skill: given a source and a sink, can input reach sink without sanitization? | MVP |
| 18 | `sast-bridge` | Wraps `semgrep` and `codeql` for gray-box queries when operator provides source | MVP |

**Reporting & disclosure:**

| # | Skill | Purpose | Tier |
|---|---|---|---|
| 19 | `report-builder` | md → docx → pdf pipeline; emits non-technical exec + technical variants | MVP |
| 20 | `disclosure-prep` | When the agent finds a 0-day in a third-party dependency, drafts a coordinated-disclosure-ready vendor advisory under `engagements/<id>/disclosures/` for operator review | MVP |

**Operational & longitudinal:**

| # | Skill | Purpose | Tier |
|---|---|---|---|
| 21 | `diff-watcher` | For longitudinal scope (same target tested weekly): compares this run's surface map and findings against last run's; flags new exposure | MVP |
| 22 | `ctf-flag-detector` | Recognizes flag formats (HTB, THM, custom regex) when CTF mode is active | MVP |
| 23 | `notification-discord` | Posts orchestrator notifications (0-day promotion, destructive-action confirmation, retro proposals queued) to a configured Discord channel | MVP |
| 24 | `traffic-replay` | Replays captured HAR/pcap with mutations | Stretch |

### 7.2 Agents (own context, conversational)

| # | Agent | Model | Owns | MVP / Stretch |
|---|---|---|---|---|
| 1 | `orchestrator` | Opus 4.6 | scope.yaml, phase machine, sub-agent dispatch, operator I/O | MVP |
| 2 | `recon-agent` | Sonnet 4.6 | recon phase | MVP |
| 3 | `enum-agent` | Sonnet 4.6 | enumeration phase | MVP |
| 4 | `vuln-agent` | Sonnet 4.6 (Opus when code-analysis dominates) | triage phase, code analysis | MVP |
| 5 | `exploit-agent` | Opus 4.6 | verification + 0-day sub-loop | MVP |
| 6 | `report-agent` | Sonnet 4.6 | report synthesis, interim checkpoints | MVP |
| 7 | `retro-agent` | Opus 4.6 | post-engagement retrospective; writes to improvements queue | MVP-minimal |

Each agent has an `AGENT.md` (its system prompt) and a `tools.yaml` listing the skills it's allowed to call. Sub-agents cannot escalate skills they're not granted.

---

## 8. Tooling Environment — Kali Linux VM

The agent runs inside a Kali Linux VM. This means most pentest tooling is already present at the OS level — the plan does **not** install tools at runtime; it assumes Kali defaults plus a small set of explicit additions.

**Already in Kali (use directly):** `nmap`, `nikto`, `dirb`, `gobuster`, `wpscan`, `enum4linux`, `smbclient`, `smbmap`, `crackmapexec`, `sqlmap`, `hydra`, `metasploit-framework`, `searchsploit`, `theHarvester`, `dnsenum`, `dnsrecon`, `whatweb`, `whois`, `wfuzz`, `ffuf`, `john`, `hashcat`, `responder`, `tcpdump`, `wireshark`, `burpsuite` (community), `zaproxy`, `mitmproxy`, `jadx`, `apktool`, `binwalk`, `radare2`, `gdb`, `frida`, `python3`, `go`, `nodejs`.

**Add to Kali for OpenClaw (operator installs once):** `subfinder`, `amass`, `dnsx`, `httpx`, `tlsx`, `naabu`, `katana`, `gau`, `arjun`, `nuclei` + nuclei-templates, `wappalyzer-cli`, Playwright (headless Chromium), `pacu`, `cloudfox`, AWS/GCP/Azure CLIs.

**Tool installation policy:** if a skill needs a tool that isn't installed, it returns a structured `tool_missing` error. The agent does NOT `apt install` or `pip install` on the fly. Tool installation is an operator action recorded in the VM's setup script.

**Versioning:** every active skill records the tool version it invoked (`nuclei v3.x.y, templates @ <commit>`) into the evidence vault.

**Egress:** limited allowlist — engagement-scope targets plus the curated `vuln-knowledge` trusted-source list (when fetch fallback is enabled).

---

## 9. Memory & State Model

Three layers:

1. **Engagement state** (per-engagement, on disk under `engagements/<id>/`): scope, asset graph, surface map, candidates, findings, evidence, report, logs. Persisted, resumable.

2. **Knowledge** (cross-engagement, persistent):
   - `corpus/` — external public knowledge (HackTricks etc.). Operator-managed via git.
   - `knowledge/` — **personal** knowledge: prior-engagement lessons (sanitized), custom payloads the operator has validated, target-stack notes, operator's house-style remediation language. Indexed by `personal-knowledge` skill.

   **PII / sensitive-info containment rule (target-notes):** anything written to `/knowledge/target-notes/` for a recurring client must be sanitized before write — no customer IPs, employee names, internal hostnames, credential fragments, dumped data, or screenshots. The `retro-agent` is responsible for sanitization on write; the `personal-knowledge` skill rejects retrieval of any chunk that fails a final-pass PII regex check before returning to a sub-agent. Sensitive prior-engagement info never bleeds into a future client's report.

3. **Agent memory** (per-agent, under standard `memory/` directory): operator preferences (severity calibration, naming conventions, report tone), validated heuristics from `retro-agent`. Subject to existing memory rules (no PII, no protected attributes, no secrets, no customer-specific data).

4. **In-conversation working state** (TodoList, per agent): phase progress, blocked items, queued candidates. Cleared between conversations.

**Resumption:** every agent reads `engagements/<id>/state.json` on startup. The orchestrator reads `state.json` plus the most recent entries of each phase's logs.

---

## 10. Safety, Legal & CTF/Dev Modes

### 10.1 Hard rules (encoded in every agent's system prompt; re-injected post-compaction)

1. No active action without a successful `scope-guard` allow.
2. No DoS or DDoS, ever — including resource-exhaustion attacks, sustained high-RPS, slow-loris, fork bombs. No mode flag changes this.
3. No exfiltration of real user data beyond proof-of-existence.
4. Destructive actions (other than DoS, which is banned outright) require fresh operator confirmation in the current conversation, even within signed scope.
5. No financial transactions on the target.
6. The engagement time window is hard.
7. No agent ever modifies `scope.yaml` or `scope-guard`'s rules.
8. No agent ever disables, mocks, or works around `scope-guard` or `vuln-knowledge`.
9. 0-day discovery follows §6.7 constraints — confidence ≥ 0.90, ≤10 attempts, no weaponization, operator notified on promotion.

### 10.2 Modes (set at engagement start)

| Mode | Purpose | Constraint changes |
|---|---|---|
| `production` (default) | Real client engagement | All hard rules apply. Destructive actions need fresh confirmation. |
| `ctf` | HackTheBox / TryHackMe / lab targets the operator owns or has full authorization for | Destructive actions allowed without per-action confirmation (but logged). **Account creation, permission edits, lateral movement, and privilege escalation explicitly permitted** when the agent judges them necessary to obtain a flag. DoS / DDoS still banned. Flag-format detection enabled via `ctf-flag-detector`. |
| `dev` | Internal development / debugging | Verbose logging on. Reasoning traces written to `logs/reasoning.jsonl` for every active action. Operator may attach `dev` to either `production` or `ctf`. |

Mode is declared in `scope.yaml` at engagement creation. Cannot be escalated mid-run; operator must end the engagement and restart in the new mode.

### 10.3 Audit log

Every active action is hash-chained into `engagements/<id>/logs/audit.jsonl`. Each line:

```json
{"ts":"...","phase":"...","agent":"...","skill":"...",
 "scope_guard_decision":"allow|deny","target":"...","action":"...",
 "rate_limited_to":"...","tool_version":"...",
 "previous_hash":"...","this_hash":"..."}
```

In `dev` mode, an additional `logs/reasoning.jsonl` records the agent's stated reasoning for each active action. This is for operator review during development; it's not part of the client deliverable.

### 10.4 Failure semantics

- `scope-guard` failure: **failure-closed.** Action denied.
- `vuln-knowledge` failure: **failure-open with labeling.** Agent proceeds but flags the claim as `grounding: model-recall-only`; report-builder marks it visibly.
- DoS-class action attempt: **hard refusal with audit log entry.** Agent does not proceed and notifies the operator.

---

## 11. Deliverable Pipeline

```
findings/*.md  ─┐
                ├──► report-builder ──► non-technical-exec.pdf  (leadership)
                │                  ├──► technical-report.docx ──► technical-report.pdf  (sec team)
exec-summary.md ┘                                                                        
                                                                                         
findings.json  ─────────────────────────────────────────────────► SARIF / vuln-mgmt feed (machine)
findings.sarif ─────────────────────────────────────────────────► same                   
run-log.md     ─────────────────────────────────────────────────► retro-agent input      (learning)
interim-<phase>.md ─────────────────────────────────────────────► resilience checkpoints (operator visibility)
```

- **Markdown findings** are the source of truth. Everything else is derived.
- **Non-technical executive PDF** ≤ 5 pages. Plain English. Business impact, not vectors.
- **Technical report** = full DOCX with attack chains, CVSS 3.1 + 4.0 vectors, remediation cited from cheatsheets.
- **PDF** generation: docx → PDF via headless LibreOffice or the `pdf` skill.
- **JSON / SARIF** emitted directly from `finding-store` (no markdown round-trip).

---

## 12. Self-Improvement Loop (Operator-Reviewed)

This was the under-developed section in v0.1. v0.2 makes it operator-gated end-to-end.

### 12.1 The flow

```
engagement ends
      │
      ▼
retro-agent reads run-log.md + findings.json
      │
      ▼
retro-agent writes proposals to:
  engagements/<id>/improvements/proposed/
    ├── memory-updates.md       (proposed memory entries)
    ├── prompt-patches.md       (suggested system-prompt edits, with diffs)
    ├── corpus-seeds.md         (vuln classes the corpus didn't cover well)
    └── skill-bugs.md           (skills that misbehaved)
      │
      ▼
orchestrator notifies operator: "N improvements proposed for review"
      │
      ▼
operator reviews each file, edits/approves/rejects
      │
      ▼
operator runs: ./apply-improvements.sh <engagement-id>
      │
      ▼
approved items moved to:
  improvements/applied/<date>-<engagement-id>/
  (memory writes, prompt edits, corpus PRs, skill bug tickets)
```

### 12.2 What's enforced

- The `retro-agent` never writes directly to memory, never edits a system prompt, never patches a skill. It only writes to `improvements/proposed/`.
- Every proposed change includes a `Why:` (what observation in the run motivated it) and a `Risk:` (what could go wrong if applied).
- `apply-improvements.sh` is operator-only. The agent does not invoke it.
- Rejected proposals are archived to `improvements/rejected/` with the operator's note, so the agent can learn (via memory) not to re-propose.

### 12.3 Skills that participate

- `improvements-queue` — read/write the proposal queue.
- `retro-agent` — generates proposals.
- (Operator-side) `apply-improvements.sh` — script lives in `/scripts/`, edits applied with explicit operator approval.

---

## 13. Integrated MVP Implementation Strategy

The implementation target is an **integrated MVP**, not a foundation-only slice. The operator's first meaningful test case is a full authorized lab/CTF pentest lifecycle, so the Kali VM cowork session should implement nearly all MVP skills and agents together with stable interfaces and conservative v1 behavior. Depth can improve later; the first pass must prove the components can cooperate.

**Host rule:** this workstation only updates `/design/`. The Kali VM cowork session performs all repo implementation changes from this design folder.

### 13.1 MVP bundle

Implement these together as one coordinated build:

- **Foundation/state:** `engagement-init`, `scope-validator`, updated v0.4-compatible `scope-guard`, `evidence-vault`, `finding-store`, `cvss-calculator`, `improvements-queue`, and shared helpers for canonical JSON, schema loading, path safety, audit hashing, structured errors, and tool-result envelopes.
- **Knowledge:** existing `vuln-knowledge`, new `personal-knowledge`, and a PII/prompt-redaction helper used before outbound model prompts.
- **Recon/enum/exploit operations:** `asset-graph`, `session-manager`, `http-history`, `screenshot-er`, `secret-scanner`, `safe-browsing`, `exploit-runner`, and `payload-mutator`.
- **Code analysis:** `code-analyzer`, `taint-tracer`, and `sast-bridge`. Initial versions may wrap Semgrep/CodeQL/simple static patterns and return the compact JSON contract from §17.
- **Reporting/disclosure/ops:** `report-builder`, `disclosure-prep`, `diff-watcher`, `ctf-flag-detector`, and `notification-discord`.
- **Agents:** `orchestrator`, `recon-agent`, `enum-agent`, `vuln-agent`, `exploit-agent`, `report-agent`, and `retro-agent` (minimal but present).

`traffic-replay` stays stretch unless the first authorized target explicitly requires HAR/pcap replay to complete the lifecycle.

### 13.2 Build order inside the integrated MVP

1. Implement shared contracts first: canonical JSON, schema loading, audit hash-chain append/verify, path safety, structured errors, and uniform JSON result envelopes.
2. Create all MVP skill directories and CLI entrypoints so every planned component is callable, even if some v1 behavior is intentionally narrow.
3. Wire storage skills: engagement init, evidence vault, finding store, audit log, state file, and crash/dispatch directories.
4. Wrap every target-touching operation so it calls `scope-guard` first and emits an audit entry.
5. Add agent prompts and tool allowlists, then wire the orchestrator phase machine.
6. Run one authorized lab/CTF engagement through setup, recon, enum, triage, verification, reporting, cleanup, and retro; fix integration gaps until it produces findings, evidence, audit logs, and a report.

### 13.3 MVP acceptance criteria

- A fresh Kali VM can receive `/design/` and implement the repo from it.
- A single CTF/local-VM engagement can run through all lifecycle phases.
- Every active action has a `scope-guard` decision and audit entry.
- Every confirmed finding has evidence in the vault and a `finding-store` record.
- Reports are generated from stored findings, not transient agent memory.
- Crashes leave recoverable or clearly quarantined partial state.
- 0-day logic is gated by the 0.90 confidence threshold, 10-attempt cap, and operator notification path.

### 13.4 Post-MVP deepening

After the first end-to-end run works, deepen capability in this order: richer web exploitation, report polish, network/cloud breadth, code-analysis precision, longitudinal diffing, then stretch features such as `traffic-replay`, deeper mobile/binary analysis, and multi-step chain planning.

---

## 14. Resolved Questions (from Round 2)

| # | Question | Resolution |
|---|---|---|
| 1 | Skill placement | Confirmed: existing + new skills all live under `/skills/`; agents under `/agents/`. |
| 2 | Sub-agent dispatch mechanism | **Decision:** primary mechanism is the Claude Code `Agent` tool (which OpenClaw uses natively — same token cost as any other model invocation, no separate "Anthropic SDK fee"). Filesystem-coordinated dispatch (`tasks/<phase>.json` → sub-agent → result file) kept as a documented fallback for cheap-model / out-of-band experiments. The two are not mutually exclusive: state is filesystem-persistent regardless of dispatch mechanism, so resume-after-crash works either way. |
| 3 | Code-analyzer placement | Confirmed: `code-analyzer`, `taint-tracer`, `sast-bridge` stay as **skills**, not their own agent. They're designed to return concise structured output so the calling `vuln-agent`'s context stays lean. |
| 4 | 0-day confidence floor | **Adjusted: 0.85 → 0.90.** Attempt cap stays at 10. |
| 5 | `/knowledge/` shape | Confirmed: `payloads/`, `engagements/`, `house-style/`, `target-notes/`. **Plus a hard PII/sensitive-info sanitization rule on `target-notes/`** (see §9 layer 2). |
| 6 | CTF mode scope | Confirmed and tightened in §10.2: explicitly permits account creation, permission edits, lateral movement, and privilege escalation in pursuit of flags. DoS remains banned. |
| 7 | `AGENTS.md` interaction | Confirmed: orchestrator's `AGENT.md` extends `/AGENTS.md` rather than replacing it. Operator asked for a review of `/AGENTS.md` itself for any adjustments — addressed in §16 below. |
| 8 | Notification channel | **Discord**, via the new `notification-discord` skill (re-uses the existing OpenClaw Discord integration). |
| 9 | Third-party 0-day disclosure | New `disclosure-prep` skill drafts a vendor-advisory-ready document under `engagements/<id>/disclosures/` for operator review. Never sent automatically. |
| 10 | Skill prioritization | Operator approved bringing every previously-stretch skill (asset-graph, session-manager, http-history, screenshot-er, cvss-calculator, code-analyzer, taint-tracer, sast-bridge, diff-watcher, engagement-init, scope-validator, secret-scanner, safe-browsing) up to MVP. Reflected in §7.1. |

---

## 15. Sub-Agent Dispatch — Mechanism & Cost Note

The operator asked whether OpenClaw has its own sub-agent mechanism vs the "Anthropic SDK." Clarification:

- "OpenClaw" is the operator's workspace built on top of Claude Code / the Claude Agent SDK. They are **not separate billing systems**. Spawning a sub-agent through the Claude Code `Agent` tool charges the same per-token rate as any other model call. There's no extra "SDK license fee."
- The `Agent` tool is what gives sub-agents their own context window — that *is* the value (it prevents the orchestrator from drowning in port-scan output).
- The "extra cost" that's real is **token cost**: each sub-agent dispatch starts a fresh context, so the system prompt + task spec are paid for again. That's a few thousand tokens per dispatch — meaningful but not catastrophic, and well worth it for context isolation.

**Final decision:**

- **Primary:** `Agent` tool dispatch from orchestrator → sub-agent. Each sub-agent boots from its own AGENT.md, reads engagement state from disk, returns a structured result.
- **Fallback / parallel mode:** filesystem-coordinated dispatch — orchestrator writes `engagements/<id>/tasks/<phase>.json`, an externally-launched sub-agent (cron, manual, separate machine, free-tier model) processes it and writes `result.json`. Used when the operator wants to experiment with cheaper models or run sub-agents on a separate box.
- Both modes work because all persistent state is on disk. The orchestrator doesn't care how a sub-agent was invoked, only whether its result file appeared.

---

## 16. `/AGENTS.md` — Review and Suggested Adjustments

The operator asked whether `/Users/openclaw/ai-pentester/AGENTS.md` itself needs adjustments. Reading it now: it's the generic OpenClaw startup file (read SOUL.md, read USER.md, read memory/, manage MEMORY.md, heartbeats, group-chat etiquette, etc.). It is **not pentest-specific**.

The orchestrator's `AGENT.md` will extend it, not replace it. But two pentest-relevant adjustments to `/AGENTS.md` itself would help:

1. **Add a pointer section** near the top of `/AGENTS.md`:
   > **Pentest engagements:** if a session involves an active engagement, also load `/agents/orchestrator/AGENT.md` and the active `engagements/<id>/scope.yaml` before doing anything. Pentest sessions inherit OpenClaw conventions plus the pentester hard rules.

2. **Tighten the existing "Red Lines" section** for pentest contexts. Current text: "Don't run destructive commands without asking." For pentest sessions specifically, the harder rule is "no DoS ever, scope-guard before every active action." A small inline note pointing to `/agents/orchestrator/AGENT.md §3` would prevent drift if a non-pentest session later mutates the workspace.

These are minor, additive edits. Suggested but not made — operator should approve before I touch `/AGENTS.md`.

---

## 17. Round-3 Questions — Resolved

| # | Question | Resolution |
|---|---|---|
| 1 | Discord channel binding — reuse existing bot or new identity? | **Reuse the existing OpenClaw Discord bot.** It's already implemented and running on a separate machine. `notification-discord` posts to that bot's HTTP/webhook endpoint with the engagement payload; bot identity, channel routing, and rate-limit policy live on the bot side, not in the pentester repo. The skill's job is to deliver a well-formed message and surface delivery failures back to the orchestrator. Wiring of the actual endpoint (URL + auth header) lives in `/skills/notification-discord/SKILLS.md` as an operator-supplied config — the design treats Discord as a black-box sink. |
| 2 | PII sanitizer aggressiveness on `/knowledge/target-notes/` | **Redact-and-warn, plus a pre-flight PII check on every outbound model prompt.** The headline concern is that PII never leaves the local machine in a prompt to any model. On read from `target-notes/`, the `personal-knowledge` skill redacts PII fields and returns the redacted chunk with a warning. Independently, before any sub-agent submits a prompt that contains text retrieved from `/knowledge/`, the orchestrator runs a final-pass PII regex over the assembled prompt. If PII survived (e.g., because the operator wrote raw PII into a code-analysis spillover file), the prompt is paused and surfaced to the operator with the offending substrings highlighted — the operator can edit/approve/cancel before the prompt is sent. The operator is permitted to view PII locally; the agent is not permitted to send it to any model. |
| 3 | CTF mode + `disclosure-prep` | **Disabled in CTF mode.** CTF runs are internal testing — reports are not sent to anyone, so vendor advisories aren't generated. CTF-mode `report-agent` emits only `findings/*.md` and `run-log.md` (no exec PDF, no DOCX, no SARIF, no `interim-<phase>.md` synthesis pass). `disclosure-prep` is gated `mode != ctf`. If a 0-day in a third-party dep is found during a CTF run, it's logged as `interesting` in `findings/candidates.jsonl` for operator triage but not turned into an advisory. |
| 4 | Code-analyzer return contract | **Adopted as proposed.** Each `code-analyzer` invocation returns ≤2 KB of JSON (sources, sinks, dataflow summary, confidence). Anything larger spills to `engagements/<id>/code-analysis/<call-id>.md`, and the JSON return includes the `spillover_path` field. `vuln-agent` reads spillover lazily — only when it decides to drill further on that candidate. Keeps the calling context lean by default. |
| 5 | Engagement-series linkage | **`parent_engagement_id` field in `scope.yaml`.** A repeat-engagement target inherits its parent's ID; `diff-watcher` walks the chain to find prior surface maps and findings. Each finding within an engagement gets a unique `F-NNN` ID (as today). Each verification attempt against a finding — especially in the 0-day sub-loop where ≤10 attempts are permitted — gets a sub-ID of the form `F-NNN/A-K` recorded in the audit log and evidence vault. Spec details for the dedup key live in `design/finding-store-dedup-key.md`. |

---

## 18. What This Plan Does NOT Touch

- `/Users/openclaw/ai-pentester/skills/scope-guard/` — preserved.
- `/Users/openclaw/ai-pentester/skills/vuln-knowledge/` — preserved.
- `/Users/openclaw/ai-pentester/corpus/` and submodules — preserved.
- `/Users/openclaw/ai-pentester/AGENTS.md` — preserved (orchestrator extends it).
- `/Users/openclaw/ai-pentester/README.md` — preserved.
- Existing memory under any `memory/` directory — preserved.

All new files in this revision live under `/Users/openclaw/ai-pentester/design/`.
