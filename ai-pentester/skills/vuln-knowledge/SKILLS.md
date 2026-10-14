---
name: vuln-knowledge
description: Authoritative lookup for vulnerability classes, exploitation
  techniques, CVE details, and attack patterns. Use BEFORE analyzing any
  finding, planning exploitation, or writing report remediation guidance.
  Returns curated reference material from a local corpus (HackTricks,
  PayloadsAllTheThings, OWASP WSTG, CWE, nuclei templates) plus optional
  live fetches from trusted security sources.
triggers:
  - Agent has identified a potential vulnerability and needs context
  - Agent is planning an exploitation chain
  - Agent encounters an unfamiliar service, framework, or CVE
  - Agent is writing the remediation section of a finding
  - User asks "how do I test for X" or "what does CVE-YYYY-NNNNN do"
---

# vuln-knowledge

## When to invoke

Call this skill the moment a finding's class is identified, BEFORE deciding
how to verify or exploit it. Cheap to call, expensive to skip — operating
without grounding is the #1 cause of hallucinated exploitation steps.

## Inputs

- `query` (required): natural language or specific identifier (CVE, CWE,
  technique name, error string)
- `mode` (optional, default `auto`):
  - `lookup` — return reference material only
  - `exploit` — return reference + known exploitation techniques + payloads
  - `remediate` — return reference + defensive guidance for the report
  - `auto` — infer from query
- `max_results` (optional, default 5)
- `allow_fetch` (optional, default true): permit live fetch fallback

## How to use the results

Returned chunks are ground truth. Quote or paraphrase them in your reasoning,
but never invent details that aren't in the returned material. If results are
empty or low-confidence, say so explicitly in your next message — do not
substitute training-data recall for retrieved knowledge. That distinction is
the difference between this agent and a guessing scanner.

If `exploit` mode returns payloads, treat them as templates, not literals.
Adapt to the target's stack, encoding, and observed filtering. Never fire a
payload without first running it through `scope-guard`.

## Procedure

1. Run `python3 lookup.py --query "{query}" --mode {mode} --k {max_results}`
2. Parse the returned JSON (schema below)
3. If `confidence < 0.4` AND `allow_fetch` is true, call `fetch.py` with
   the same query against the trusted-source allowlist
4. Return the merged result set, ranked by relevance, with source attribution

## Output schema

```json
{
  "query": "...",
  "results": [
    {
      "source": "hacktricks/pentesting-web/sql-injection.md",
      "source_type": "local|fetched",
      "title": "...",
      "content": "...",
      "relevance": 0.0-1.0,
      "url": "https://... (if applicable)"
    }
  ],
  "confidence": 0.0-1.0,
  "fetched_external": true|false
}
```

## Corpus layout

- `corpus/hacktricks/` — git mirror, updated weekly
- `corpus/payloads/` — git mirror of PayloadsAllTheThings
- `corpus/wstg/` — OWASP testing guide
- `corpus/cwe/` — parsed MITRE CWE database
- `corpus/nuclei-templates/` — detection logic, indexed by CVE and tag
- `corpus/cache/` — fetched external content, keyed by URL hash
- `index.db` — sqlite-vec hybrid index, rebuilt by `reindex.py`

## Maintenance

`reindex.py` runs nightly via cron. `update-corpus.sh` runs weekly to
`git pull` the mirrored repos. If `index.db` is older than 14 days, the
skill emits a warning in its result and the agent should notify the operator.

## Failure modes

- Empty results + fetch disabled: tell the operator, don't guess
- Index missing: fall back to ripgrep over the corpus, flag degraded mode
- Fetched content from a non-allowlisted domain: discard, log, alert