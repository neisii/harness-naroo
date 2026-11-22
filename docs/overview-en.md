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

AI-DLC (AI-Driven Development Lifecycle) is a development method where AI does the planning, design, code,
and tests while people review and approve. This repository is a Claude Code harness for that method: it
formalizes, on top of that flow, the rules that were built up step by step to address each of these on a
4-month next-gen quasi-public commerce build. The guiding principle: **treat the AI like a disciplined teammate** — clear
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
| 5 | `CM` | Result review, completion report, commit message (AI-attribution lines are the team's call; a team that forbids them turns them off with Claude Code's `attribution` setting, `CM-11`) |
| 6 | `AG` | Agent-to-agent comms (handshake), no cross-project reads, 3-line task mandate |
| 7 | `BR` | Branch naming, scope, merge flow |
| 8 | `AR` | Artifact paths, blueprint storage, required completion reports, diagram→HTML |
| 9 | `CC` | Common-code: survey all sources, present candidates, get a decision |
| 10 | `TS` | E2E scenario re-verification, test-account provenance |
| 11 | `CS` | Commit-plan approval, staging diff, dangerous git commands |
| 12 | `WT` | Worktree creation/teardown, server build & ports |

A key discipline: the summary ([`rules/향상된_AI-DLC_00-핵심규칙요약.md`](../rules/향상된_AI-DLC_00-핵심규칙요약.md))
is only an index — the step document always wins, and any drift is surfaced to a human. The
[`dlc-gate`](../skills/dlc-gate) skill points you to the right document at the moment you act.

**Adapt, don't rewrite.** The rules keep the original team's concrete values (paths, stack, OS, session names,
commit attribution, conversation language) as examples; [`환경값-정의.md`](./환경값-정의.md) (Korean) lists
what to swap.

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

These are the original team's names. What the harness separates is the kind of session: a **lead** session
(총괄) takes no implementation work and connects the human with other sessions or handles project-wide work; a
**worker** session (워커) does the assigned work, usually implementation. Names are an environment value
([`환경값-정의.md`](./환경값-정의.md) B); the small-mode gateway below is a lead session, its workers are worker
sessions.

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
- **Workers are separate sessions** (`claude --bg`), not subagents (the `Agent` tool), because they wait for the
  human's approval across several gates.
- **Permission mode defaults to `auto`** for the gateway and the workers. What must be blocked is blocked
  elsewhere: direct and force pushes to main by GitHub branch protection, and decisions (blueprint, business
  decisions, merge, delegation scope) by the gates in the delegation record rather than by permission prompts.
  `acceptEdits` with an allowlist is the conservative option.
- **Check before sending.** Idle background workers get cleaned up, which is normal. Before relaying, the
  gateway runs `session-stall-check`; if the worker is stuck on a dialog such as a permission prompt it tells
  the human instead (only a person who opens that session can answer it), and if
  there is no process it revives the worker with `session-wake` first.
- **Push is not left to workers.** Push and PRs are the human's (the gateway does them on the human's
  instruction); direct and force pushes to main are blocked by GitHub branch protection, not by command options.
- **Optional narrow delegation:** the gateway may approve commit plans (CS-01) and requirement-vs-result checks
  (CM-01) — reversible, rule-checkable gates, chosen by applying the reversibility criteria to each gate — but
  only after its own check **and** a fresh-context re-verification both pass. Everything else (blueprint
  approval, push/PR/merge, irreversible git, business decisions) stays with the human. A one-time instruction
  ("merge this PR") never becomes a standing permission. Optionally, one step wider: if both checks pass and
  only the wording of a commit message or completion report is off, the gateway has the worker fix it,
  re-verifies, approves, and reports to the human afterwards.
- **Short approvals are relayed only when their target is clear.** If the human answers briefly ("approve as
  recommended"), the gateway relays it only when it is clear which task and what is being approved; otherwise it
  asks back instead of guessing. If it expands a short answer ("question 3 is A"), it shows the expansion to the
  human first.
- **Dogfooded** on a real repository: a gate round-trip, two narrow-delegation runs, and a three-worker run
  through blueprint, PR, merge, and cleanup — no lane violations and no wrong approvals. Before the 0.2.0
  release (2026-11-21), a run on a new public repository ([gate3-trial](https://github.com/neisii/gate3-trial)):
  one gateway and four workers (one skeleton task, then three in parallel, then two follow-ups), with tasks deliberately
  set up to affect one another. Again no lane violations or wrong approvals; that effect reached the human at
  the blueprint stage, and its quieter breakage (orders with a partial cancellation dropping out of the revenue
  total) was caught by a fresh-context re-verifier. Workers stalling on permission prompts in that run led to
  the `auto` default above. Samples are still small.
- **Not yet included:** an engine that splits work automatically (in small mode the human splits it), the
  waiting ledger and patrol, and workers launching their own worker sessions. Planned, one opt-in bundle per
  minor version: 0.3.0 integration and release flow → 0.4.0 waiting ledger and asynchronous review → 0.5.0
  patrol and alerts → … → 1.0.0 the full setup.
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
   portable [`session-stall-check`](../skills/session-stall-check) skill generalizes the detect layer: it
   classifies a session from `claude agents` state·status·pid·waitingFor (stuck on a dialog / waiting for a reply
   / working / idle / no process).

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
| `blueprint-index` / `index-refresh` | Assume the project's `docs/` inventory layout (`survey-gen` was rebuilt for the public edition in 0.2.0) |
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
