# AI-DLC Harness — Overview

> English companion to the Korean rule documents in [`../rules/`](../rules). This page explains the ideas
> behind the harness and the real cases that shaped it. For how it was anonymized, see
> [`../NOTICE.md`](../NOTICE.md).

## Why

On a real system-integration (SI) delivery, a naive "let the AI code" approach fails in predictable ways:

- it **guesses** business rules and plans when the spec is unclear,
- it edits **outside its lane** (another team's module, shared code),
- it reports untested work as **"verified,"**
- it **stalls silently**, waiting for an input nobody is watching for,
- and one "decision" session becomes a **bottleneck** for everything.

AI-DLC ("AI Development Life Cycle") is the harness that addressed each of these on a 4-month next-gen
public-procurement build. The guiding principle: **treat the AI like a disciplined teammate** — clear
boundaries, an explicit approval gate, one canonical source of truth, and *verified means actually verified.*

## The pipeline

```
request → research → blueprint → [HUMAN GATE] → implement → verify → completion report
```

Nothing is implemented before the blueprint is approved (by a human, or by the delegated `qa-master`
session). Verification is evidence-based, and work that could not be verified is **recorded as unverified**,
never quietly passed.

## The 12-step rule system

The rules (`rules/`) are the **canonical source (정본)**. Each step is read *just before* the action it
governs, not memorized up front. Rule IDs are `<prefix>-<nn>`:

| Step | Prefix | Governs |
|---|---|---|
| 1 | `GL` | Global constraints — stay in your lane, don't guess, don't fake verification |
| 2 | `RL` | Human vs. AI responsibilities; `qa-master` delegation scope (`RL-12`) |
| 3 | `RQ` | Research scope, A/B/C/D triage, option-style questions, blueprint format |
| 4 | `GT` | The implementation-start **gate** (`GT-02`) |
| 5 | `CM` | Result review, completion report, commit message (no AI-attribution lines) |
| 6 | `AG` | Agent-to-agent comms (handshake), no cross-project reads, 3-line task mandate |
| 7 | `BR` | Branch naming, scope, merge flow |
| 8 | `AR` | Artifact paths, blueprint storage, required completion reports, diagram→HTML |
| 9 | `CC` | Common-code: survey all sources, present candidates, get a decision |
| 10 | `TS` | E2E scenario re-verification, test-account provenance |
| 11 | `CS` | Commit-plan approval, staging diff, dangerous git commands |
| 12 | `WT` | Worktree creation/teardown, server build & ports |

A key discipline: the summary (`00-핵심규칙요약.md`) is only an index — the step document always wins, and any
drift is surfaced to a human. The [`dlc-gate`](../skills/dlc-gate) skill points you to the right document at
the moment you act.

## Human Gate

Explicit stop points where the AI does **not** proceed without approval — e.g. implementation start, commit
plans, interpreting business rules, cross-project changes, irreversible git commands (`--force`, reset/rebase,
deleting lock files). Approval authority is the human, with a documented delegation to `qa-master`.

## Role sessions

Rather than one overloaded session, responsibilities are split:

- **`qa-master`** — decisions and approvals (delegated human authority).
- **`ai-rule-master`** — edits the rules (and only the rules).
- **`skill-gen-master`** — builds tools/skills.
- **`*-developer`** — per-service implementation, each confined to its lane.

This is what removed the "everything funnels through one session" bottleneck.

### Small mode (0.2.0) — multiple sessions without the full setup

The full setup above assumes infrastructure a solo developer or small team won't have: a dedicated
`qa-master`, a waiting ledger, a patrol loop. Version 0.2.0 adds a **small mode** that needs none of it:

```
human (decides)  →  gateway session (relays & watches)  →  worker sessions (implement)
```

- The **gateway is a communication window, not a gate.** It creates and stops worker sessions, relays the
  human's approvals **verbatim**, watches progress, and escalates anything not on its written delegation list.
  The human stands in for `qa-master`, the ledger, and patrol.
- **Gateway ≠ worker**, so no session approves its own work.
- **Optional narrow delegation:** the gateway may approve commit plans (CS-01) and requirement-vs-result checks
  (CM-01) — reversible, rule-checkable gates — but only after its own check **and** a fresh-context
  re-verification both pass. Blueprint approval, push/PR/merge, irreversible git, and business decisions stay
  with the human. A one-time instruction ("merge this PR") never becomes a standing permission.
- **Dogfooded** on a real repository: a gate round-trip, two narrow-delegation runs, and a three-worker run
  through blueprint, PR, merge, and cleanup — no lane violations and no wrong approvals. Samples are still small.
- Guide (Korean): [`오케스트레이션-구성.md`](./오케스트레이션-구성.md) · delegation record template:
  [`위임기록-템플릿.md`](./위임기록-템플릿.md).

## Cases that shaped it

These ran on the original project. The pipelines themselves are **described here, not shipped as runnable
code**, because they were tightly coupled to the project's database, document system, and Windows tooling.

1. **Scenario verification (TEST).** Specs couldn't be trusted verbatim, so each E2E scenario was triaged
   against the actual code: **A** match → run, **B** mismatch → correct then run, **C** not-implemented →
   exclude, **D** out-of-scope → exclude, **E** needs-data → build dataset/stub. Remaining scenarios were run
   and captured with Playwright, batched overnight. Result: 26 of 34 screens verified, the rest handed over as
   explicitly unverified.

2. **Session-stall prevention (INCIDENT).** A session once sat **7h 37m** waiting on an input prompt while its
   status looked normal and no alert fired. Response in three layers: **prevent** (mandatory 3-line task
   instructions), **block** (disable the interactive question window), **detect** (watch for inactivity). The
   portable [`session-stall-check`](../skills/session-stall-check) skill is the detect layer, generalized.

3. **Decision-session bottleneck (BOTTLENECK).** The decision session was also doing patrols, tallies, and
   tool-building. Mechanical work was automated (a patrol ran ~254 times over ~40h, surfacing only urgent
   items) and tool-building was split into its own session. Duplicate work dropped ~26%.

4. **Spec-first lookup (BOUNDARY).** Instead of reading another team's source (which stalls their work),
   API specs were auto-generated and a lookup order was enforced: check the spec first, ask the owning session
   only if unresolved. Five generators were consolidated into one, replacing Swagger.

5. **Undocumented change detection (DOMAIN).** Undocumented common-code changes kept causing label/display defects.
   Snapshot diffs were auto-summarized and handover docs consolidated per screen/policy — 52 documents total,
   with discrepancies attached.

## What isn't shipped (and why)

| Component | Why it's described, not bundled |
|---|---|
| `scenario-verify` pipeline | Coupled to the project DB and scenario format; 90+ authoring scripts, PowerShell helpers |
| `docs-consolidate` | Tied to the project's document taxonomy (templates, policy/screen IDs) |
| `api-spec-gen` | Service list hardcoded to the project's modules |
| `common-code-sync` | Specific to the project's dev DB tables |
| `blueprint-index` / `index-refresh` / `survey-gen` | Assume the project's `docs/` inventory layout |
| `ops-report` (patrol hub) | Windows Task Scheduler + PowerShell notifier |
| Status widgets (memory / pending / usage), tray | Unsigned Windows `.exe` / C# — excluded on principle |

If you want to rebuild any of these for your own stack, the rules in `rules/` and the cases above are the
blueprint. Contributions that generalize one of them are welcome.

## Data handling

The plugin runs locally and sends no personal or project data off-platform. The one outbound network call is
`claude-update-check`, which reads the latest Claude Code version and changelog from GitHub
(`raw.githubusercontent.com`) and the npm registry — version info only, no user data. Some rules instruct
reading a local, read-only DB credential (`~/.claude/secrets/devdb_readonly.env`, AG-08) that is never printed,
logged, or transmitted; no secrets are bundled (see `NOTICE.md`).
