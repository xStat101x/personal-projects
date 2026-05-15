# Responses to Design Updates Questions

Pairs with `PLAN.md v0.3` and `SYSTEM_PROMPT.md v0.3`. Answers your numbered questions from `Design Updates.md`.

> **v0.3 note:** all operator inline answers below have been folded into PLAN.md and SYSTEM_PROMPT.md. See `PLAN.md §14` for the resolved-questions table, `§15` for the dispatch decision, `§16` for the `/AGENTS.md` review, and `§17` for the new Round-3 questions. This file is preserved as-is for traceability.
>
> **v0.4 note (read me first):** this file is **historical**. Any numbers, thresholds, or open questions below were superseded by `PLAN.md v0.4` and `SYSTEM_PROMPT.md v0.4`. In particular: the 0-day confidence floor is **0.90** (not the 0.85 you'll see quoted in Q6's "Resolved in v0.2" recap), all Round-3 questions are resolved in `PLAN.md §17`, and four companion spec docs (`scope-schema.md`, `audit-log-hash-chain.md`, `sub-agent-crash-semantics.md`, `finding-store-dedup-key.md`) under `/design/` are required reading before implementation begins. Read `PLAN.md v0.4` for ground truth, treat this file as a record of how we got here.

---

## Q1 — What other skills are necessary for maximum effectiveness?

Beyond the 10 skills already in `PLAN.md §7.1`, here's what I'd add — separated into "core for an XBOW-class agent" and "Mythos-class code-reasoning amplifiers":

**Core (raise to MVP if you agree):**

- **`asset-graph`** — graph data structure with query API over hosts, services, endpoints, parameters, technologies, observed authentication boundaries. Both recon and enum write into it; vuln and exploit read from it. Without this, the orchestrator passes huge JSON blobs between sub-agents.
- **`session-manager`** — handles authenticated testing: stores cookies/tokens per role, refreshes when expired, lets sub-agents request "test as role X." Critical for BOLA/IDOR/horizontal-priv-esc work; also for any auth-gated surface.
- **`http-history`** — append-only log of every HTTP request the agent has sent + responses, indexed by target/endpoint/parameter. Lets exploit-agent diff baseline vs payload responses without re-firing.
- **`screenshot-er`** — Playwright wrapper that captures evidence screenshots with annotation overlays. Already implied; making it a dedicated skill simplifies evidence capture.
- **`cvss-calculator`** — both CVSS 3.1 and 4.0 vectors → score, plus business-context override applier. Separating this from `finding-store` keeps scoring logic auditable.

**Mythos-class amplifiers (the differentiator):**

- **`code-analyzer`** — already in §7.1. Concretely: takes decompiled JS/Java/.NET/binary code + a vuln hypothesis, returns a structured analysis (sources, sinks, dataflow path, confidence). Calls into `tree-sitter` or LSP-style language servers under the hood.
- **`taint-tracer`** — sub-skill of code-analyzer focused on dataflow: given an input source and a sensitive sink, can we prove the input reaches the sink without sanitization? This is what humans miss in large codebases.
- **`sast-bridge`** — wraps `semgrep` and `codeql` so the agent can spin a quick query against the target's source if the operator has provided it (gray-box add-on; not strictly blackbox but useful in many engagements).
- **`diff-watcher`** — for engagements with longitudinal scope (test the same target weekly). Compares this run's surface map and findings against last run's; flags new exposure / new findings.

**Operational:**

- **`engagement-init`** — bootstraps a new `engagements/<id>/` directory from a template, validates `scope.yaml` schema, generates the audit log seed.
- **`scope-validator`** — separate from `scope-guard`. Lints `scope.yaml` for ambiguities ("you wrote `*.acme.com` but `admin.acme.com` is also listed as out-of-scope"), warns operator before engagement starts.
- **`secret-scanner`** — pattern + entropy-based hunt for keys/tokens/credentials in JS bundles, mobile binaries, public S3, etc. (Trufflehog-equivalent, callable as a skill.)
- **`safe-browsing`** — when the agent navigates URLs found in OSINT, runs them through a malware-check first so we don't visit attacker-controlled lures during recon.

I'd promote `asset-graph`, `session-manager`, `http-history`, `cvss-calculator`, `code-analyzer`, `taint-tracer`, `engagement-init`, `scope-validator`, and `secret-scanner` to **MVP** in M1–M3. The rest stay stretch.

I would like you to implement as many of these as possible and prioritize the ones you believe would be most valuable.

## Q2 — CTF / development mode flag with relaxed destructive constraints

**Yes — already added to `PLAN.md §10.2` and `SYSTEM_PROMPT.md §10`.**

How it works in v0.2:

- Mode is declared in `scope.yaml` at engagement creation: `mode: production | ctf`.
- An optional `dev` overlay can be added: `dev: true`.
- `ctf` mode allows destructive actions without per-action confirmation (still logged).
- **DoS / DDoS is banned in every mode, no exception.** Per your rule.
- Mode cannot be escalated mid-run. To change modes, operator ends the engagement and starts a new one. This prevents the agent from "talking itself" into broader permissions.
- When the orchestrator detects `mode: ctf`, it enables `ctf-flag-detector` automatically.

Example `scope.yaml` mode block:

```yaml
mode: ctf
dev: true
target_type: htb_lab          # htb | thm | local_vm | other
flag_format: HTB\{[a-f0-9]{32}\}
notes: "Hack The Box - Active machine - personal lab account"
```

## Q3 — Adjust plan to match OpenClaw file structure

**Done in v0.2.** Specifically:

- New code splits into `/skills/` (existing convention, unchanged) and `/agents/` (new, follows your OpenClaw `/agents/` convention).
- Each agent has its own `AGENT.md` (system prompt) and `tools.yaml` (allowed skill list).
- Personal knowledge gets its own top-level directory `/knowledge/` (separate from the public `/corpus/`).
- Engagement workspaces live in `/engagements/<id>/`.
- Operator-side scripts live in `/scripts/`.
- The existing `/AGENTS.md` (your generic OpenClaw startup file) is preserved. The orchestrator's `AGENT.md` extends it rather than replacing it. (See open question 6 in `PLAN.md §14`.)

Final proposed top-level layout:

```
/Users/openclaw/ai-pentester/
├── AGENTS.md                       # existing OpenClaw startup file (preserved)
├── README.md                       # existing project intent (preserved)
├── design/                         # planning docs (this directory)
├── agents/
│   ├── orchestrator/
│   │   ├── AGENT.md
│   │   └── tools.yaml
│   ├── recon-agent/ ...
│   ├── enum-agent/ ...
│   ├── vuln-agent/ ...
│   ├── exploit-agent/ ...
│   ├── report-agent/ ...
│   └── retro-agent/ ...
├── skills/
│   ├── scope-guard/                # existing
│   ├── vuln-knowledge/             # existing
│   ├── personal-knowledge/         # new
│   ├── evidence-vault/             # new
│   ├── finding-store/              # new
│   ├── report-builder/             # new
│   └── ... (others per §7.1)
├── corpus/                         # existing — external public knowledge
│   ├── hacktricks/
│   ├── PayloadsAllTheThings/
│   ├── wstg/
│   ├── CheatSheetSeries/
│   ├── nuclei-templates/
│   └── cwe/
├── knowledge/                      # NEW — personal knowledge base
│   ├── payloads/                   # operator-validated payloads
│   ├── engagements/                # sanitized lessons keyed by stack
│   ├── house-style/                # report tone, severity calibration
│   └── target-notes/               # per recurring client/lab
├── engagements/                    # NEW — per-run workspaces
│   └── <engagement-id>/
│       ├── scope.yaml
│       ├── state.json
│       ├── recon/
│       ├── enum/
│       ├── findings/
│       ├── evidence/
│       ├── report/
│       ├── logs/
│       └── improvements/
│           ├── proposed/
│           ├── applied/
│           └── rejected/
└── scripts/                        # NEW — operator-side helpers
    └── apply-improvements.sh
```

This preserves everything that exists today and only adds. Confirm this layout and I'll lock it.

## Q4 — Dev mode flag for verbose logging

**Yes — added as the `dev` overlay** in `PLAN.md §10.2` and `SYSTEM_PROMPT.md §10`.

What `dev` mode does:

- Every active action also writes to `engagements/<id>/logs/reasoning.jsonl`. Each line: timestamp, agent, planned action, *why* (the agent's chain-of-thought rationale), expected outcome, actual outcome.
- Every sub-agent dispatch writes its full task spec + final result to `logs/dispatch.jsonl`.
- The orchestrator emits a per-phase status to stdout in addition to writing to disk — so if you're watching live, you see the reasoning unfold.
- Output is **not** included in any client deliverable. It's purely for your development review.
- `dev` is composable with both `production` and `ctf`. So you can run a dev-mode CTF engagement (full logging, relaxed destruction) for fastest feedback.

Recommendation: keep `dev` mode on through M1–M5. Turn it off in `production` engagements once you trust the loop, because reasoning logs can leak target info if disclosed.

## Q5 — Will this work on free models temporarily?

**Partially — and the multi-agent design helps.**

Concrete picture:

- **Orchestrator** — needs strong instruction-following and the ability to refuse out-of-scope reasoning. Free Sonnet-class on the API or Haiku 4.5 should handle it for `ctf` / lab work. For real engagements, Opus 4.6 is worth the spend (it's the safety layer).
- **`recon-agent`** — mostly tool-driving + JSON output. Haiku 4.5 or any free Sonnet-tier should do fine.
- **`enum-agent`** — same. Cheap models work.
- **`vuln-agent`** — depends on whether code-analysis is dominating. For nuclei-driven triage, cheap models are fine. For Mythos-class code reasoning, you want Opus 4.6.
- **`exploit-agent`** — this is where model quality matters most. Payload mutation, response interpretation, multi-step verification. Opus 4.6 strongly preferred. Free models will work for simple known-class verification but will hallucinate or loop on tricky cases.
- **`report-agent`** — Sonnet 4.6 (free or paid) is plenty. Writing-grade work, not reasoning-grade.
- **`retro-agent`** — Opus 4.6 ideal but Sonnet 4.6 works.

**Practical recommendation:** for the M1–M4 development path against local lab VMs and CTF boxes, you can run the whole stack on free / cheap models — accepting that exploit-agent will sometimes give up on bugs that Opus would solve. You'd lose maybe 20–30% of findings on tricky targets. As you move to M5+ and real targets, swap exploit-agent and orchestrator to Opus 4.6 first; keep the others cheap.

The architecture supports this — each AGENT.md declares its preferred model, and you can override per-engagement if needed.

## Q6 — Review for inconsistencies / missed effectiveness items

Walked through both v0.2 docs against your concerns. Findings:

**Resolved in v0.2:**

- 0-day discovery: gated, capped at 10, confidence floor 0.85, operator notification on promotion. (Plan §6.7 / Prompt §6.)
- Skills vs agents: cleanly split. (Plan §4, §7.)
- Multi-agent decomposition: orchestrator dispatches specialists. (Plan §5, Prompt §5.)
- DoS/DDoS: hard banned in every mode. (Plan §10.1 #2, Prompt §3 #3.)
- Self-improvement loop: operator-reviewed proposal queue, agent never auto-applies. (Plan §12, Prompt §15.)
- Kali VM tooling: assumed default, no runtime install. (Plan §8, Prompt §7.)
- Reporting timing: per-finding markdown during exploit, synthesis at the end after all stretch milestones, plus per-phase interim checkpoints for resilience. (Plan §6.6, Prompt §9.6.)
- Knowledge structure: corpus = external, knowledge = personal. (Plan §9, Prompt §8.)
- Technical vs non-technical reports: explicit separate deliverables. (Plan §11, Prompt §2.)

**Remaining inconsistencies / gaps I want to flag:**

1. **Mode declared in scope.yaml** — but `scope.yaml` schema isn't documented yet. We should write a `scope.yaml` schema spec before M0→M1, otherwise sub-agents can't validate. I'd put it under `design/scope-schema.md` next iteration.
2. **Audit log integrity** — the hash chain in `logs/audit.jsonl` is described but the chaining algorithm isn't specified. Need a one-pager: `previous_hash = sha256(prev_line.this_hash + this_line.payload)`. Worth nailing before implementation.
3. **Sub-agent failure isolation** — if `exploit-agent` crashes mid-finding, the orchestrator needs to know whether the partial evidence is usable. Not currently specified. Suggest: every sub-agent writes a `done.flag` or `crashed.flag` to its phase directory before exiting; orchestrator checks.
4. **Operator notification channel** — "the orchestrator notifies the operator" appears repeatedly but where does that notification land? Discord? Email? In the same chat? Need to decide. (See follow-up question below.)
5. **Code-analyzer skill is doing a lot** — it's listed as a skill but Mythos-class taint analysis is genuinely hard and may want to be its own agent (`code-agent`) with its own context. Worth thinking about.
6. **Finding deduplication across runs** — same bug found across multiple engagements should be linked (especially for recurring clients). Not currently specified. Easy add: `finding-store` keys findings with a content hash + asset fingerprint.

I haven't changed the docs to address #1–#6 — they're the next refinement pass after you've validated everything else.

---

## Follow-up questions back to you (please answer in `Design Updates.md` again, or inline)

1. **Sub-agent dispatch mechanism** — should I plan around Anthropic Agent SDK's `Agent` tool (clean per-task context isolation, costs more per dispatch), or filesystem-coordinated dispatch (cheaper, more portable, less clean)?
Answered in PLAN.md
2. **Operator notification channel** — when the orchestrator needs to notify you (0-day promotion, destructive-action confirmation, retro proposals queued), should it: (a) post in the active chat, (b) write a single `notifications.md` file the operator polls, (c) send to Discord via the existing OpenClaw integration, (d) something else?
Discord will be the notification channel 
3. **Code analysis as agent vs skill** — given how central Mythos-class code reasoning is to your differentiator goal, do you want it as its own `code-agent` (own context, can take long reasoning chains) or as a skill the `vuln-agent` calls (simpler architecture, but vuln-agent's context fills up faster)?
seperate skill is good id like to preserve context
4. **0-day confidence threshold of 0.85** — gut-check: does that feel right, too cautious, too loose? It's the single most impactful number in the system.
Answered in PLAN.md
5. **`/knowledge/` directory shape** — does the proposed `payloads / engagements / house-style / target-notes` split make sense, or do you envision other categories (e.g., `tools-quirks/` for "this version of nuclei has a bug with this template")?
Answered in PLAN.md
6. **Existing `/AGENTS.md`** — confirm: the orchestrator's `AGENT.md` *extends* the existing `/AGENTS.md`, doesn't replace it. (I.e., the orchestrator inherits the OpenClaw conventions and adds pentest-specific rules on top.)
Answered in PLAN.md
7. **Third-party 0-day disclosure path** — when the agent finds a 0-day in a third-party dependency in the target's stack, my v0.2 says "logged but not exploited; coordinated-disclosure is operator's problem." Want me to wire in a `disclosure-prep` skill that drafts a vendor advisory ready for your review?
that would be good