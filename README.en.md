# AI-DLC Harness (naroo)

[한국어](./README.md) · **English**

**An AI agent reports "done." Whether its result still fits the whole system — who checks that?**

This repository is a Claude Code plugin, made of rule documents and skills (procedures and tools Claude picks up at set moments). Once installed, Claude does not stop at making one task succeed: it follows a procedure that checks whether the result keeps the **whole system coherent**, and it stops to ask at the points where a human has to decide.

AI-DLC (AI-Driven Development Lifecycle) is a development method where AI does the planning, design, code, and tests while people review and approve. This harness puts in order the rules that SI (systems integration) work built up, one real need at a time, on top of that flow.

> **Language note.** The canonical rules and most docs are in **Korean** — the first audience is Korean SI teams. This page, [`QUICKSTART.en.md`](./QUICKSTART.en.md), and [`docs/overview-en.md`](./docs/overview-en.md) are the English entry points. The harness does **not** force a conversation language: talk to Claude in whatever language you work in.

---

## Why it exists

The harness was used on a real next-generation public-procurement build (2026) and is published here, anonymized. That project split screen development across several AI sessions with different roles, and ran into this:

- Tasks the AI reported as "done, tests pass" broke once merged with other tasks.
- The AI committed or deleted files without asking.
- The more sessions there were, the more every approval request piled onto one person.

A rule was added each time. On that project the harness helped **deliver 34 screens about a month ahead of schedule** and grew to **13 rules, 27 skills, and 31 tools**. It ran 7 AI sessions with separate roles (QA, rule maintenance, tool building, per-service implementation), with a patrol every 10 minutes to find stalled sessions. The public version keeps the core that is not tied to that project. How it was anonymized: [`NOTICE.md`](./NOTICE.md).

## Who it's for

SI developers working in Korean who hold that an agent succeeding at its task isn't the finish line: keeping the whole system coherent is, and it should be possible to trace that check afterwards.

## What happens when you hand it one feature

Below is the harness's basic flow. Each step comes with what actually happened in the pre-release trial ([gate3-trial](https://github.com/neisii/gate3-trial), a public repository). The trial built a small order-processing system: first a skeleton (orders and three order states), then three features built at the same time by three AI sessions — partial order cancellation, daily revenue totals, and per-state notification messages.

1. **A human hands over a task.** In the trial, the skeleton task came first.
2. **Claude does not start writing code; it writes a blueprint first and stops.** A blueprint is a work plan listing the files to change, the test plan, and the questions a human must decide. In the trial, the skeleton blueprint carried a side note that partial cancellation would affect revenue totals and notification messages. The AI relaying messages between the human and the other sessions (the gateway session) raised that note separately as "something a human must decide before the three features start."
3. **The human approves the blueprint and makes the decisions raised.** Nothing is implemented before approval. In the trial, the human approved the skeleton blueprint and, before the three features started, decided how to handle that effect: revenue totals and notification messages would handle only the existing three states for now, and be fixed separately after partial cancellation was merged. That created two follow-up tasks.
4. **Claude implements and tests.** It does not just say "tests pass"; it quotes the commands it ran and their output, and writes down what it could not check.
5. **Another AI that did not inherit the work conversation (a fresh-context verifier) checks the result again.** In the trial, before partial cancellation was merged, the verifier checking the merge plan ran the merged code. With two paid orders totalling 6,000 won, partially cancelling one of them dropped even its remaining 3,000 won from revenue, so the total came out as 1,000 won instead of 4,000 won. Every feature's own tests were passing. That number became the basis of the revenue follow-up task's blueprint, and that task added a test that "every order state is marked as counted or not counted in revenue," so the same thing cannot quietly happen again.
6. **Before committing, Claude shows a commit plan (branch, files to include, commit message) and a human approves it.** Push and merge are the human's too. In the trial, the optional narrow delegation was on, so commit plans were approved by the gateway session only after both its own check and a fresh-context re-verification passed, and anything that did not pass went to the human. Push was done by the gateway session on the human's one-time instruction each time, and the human did the merge into main.
7. **When merging, the combined result is tested again even if each task passed.** In the trial, the final combination was built in advance before going into main and 90 tests passed; after the merge, they were checked again on main.

The human decides at steps 3 and 6, plus push and merge. Claude does the rest, but leaves evidence so it can be checked again. Once installed, the `dlc-gate` skill responds to phrases like "implement this," "commit," or "done" and guides Claude through this order.

## Core ideas

1. **Human gates.** A gate is a point that needs a human's approval to pass. No implementation before the blueprint (work plan) is approved; no commit before the commit plan is approved.
2. **Only what was checked is called checked.** Instead of "passed," the agent quotes the commands it ran and their output. Work it could not check is written down as "not checked," never quietly passed.
3. **Re-verification in a fresh context.** A verifier that shares the producer's conversation misses the same things. So before a commit is approved, an AI that did not inherit that context looks again — step 5 above.
4. **No self-grading.** The session that produced a result never approves it.
5. **Reversibility check, veto-first.** For a new situation no rule covers, "do it alone, or stop and ask?" is decided from four criteria: can it be undone · is the request clear · scope · is it a business rule a human must decide. Three of them (undoable, clear, business rule) carry a veto: if any one trips, the agent stops and asks, no matter how the others look.
6. **Use the platform, don't rebuild it.** The harness sets the overall flow; it does not try to control everything. Where Claude Code already has a setting (permissions, commit attribution, background sessions), the harness uses it.

## Two ways to use it

| | One session (since 0.1) | Several sessions (0.2.0, optional) |
|---|---|---|
| What | One Claude Code session follows the discipline above | Work is split across several sessions running at once: human (decides) → gateway session (an AI that relays messages between the human and other sessions and watches progress) → worker sessions (AIs that implement) |
| Who approves | You | You, by default. The gateway relays approvals verbatim and escalates anything it was not given. With narrow delegation (optional), only reversible gates such as commit-plan approval go to the gateway, after its own check and a fresh-context re-verification |
| Needs | The plugin | The plugin + one delegation record listing what the gateway was given. Without the original project's dedicated QA session, waiting ledger (a record of which session is waiting on whom for what), and patrol, the human covers those roles (this is called small mode, as opposed to the full setup the original project ran) |
| Guide | [`rules/`](./rules/향상된_AI-DLC_00-핵심규칙요약.md) (start at `00`, Korean) | [`docs/오케스트레이션-구성.md`](./docs/오케스트레이션-구성.md) (Korean) |

The multi-session setup is new in 0.2.0. It was checked by using it on real repository work (gate round-trips, narrow delegation, a three-worker run through PR and merge), and before release, in the trial above, four workers carried tasks deliberately set up to affect one another from start to finish. Samples are still small, and the guide marks what has not been verified.

## Install

Requires [Claude Code](https://claude.com/claude-code) and Python 3 (used by the skill scripts and examples; on Windows use `python` or `py` instead of `python3`).

```sh
# in Claude Code
/plugin marketplace add neisii/harness-naroo
/plugin install ai-dlc-harness@harness-naroo
```

Then restart or run `/reload-plugins`. The rule documents load from the plugin folder.

- **Check the install:** run `claude plugin list` in a terminal; `ai-dlc-harness@harness-naroo` should show as `enabled`.
- **Where it applies:** you choose a scope when installing ([docs](https://code.claude.com/docs/en/plugins/install#choose-an-install-scope)). In the `/plugin` panel pick user (you, every project), project (everyone in this repository), or local (you, this repository only); the terminal `claude plugin install` defaults to user scope (`--scope project` / `--scope local` to change). To use the harness in one project only, install with local or project scope. If you installed at user scope and want it off in a project, run `claude plugin disable ai-dlc-harness@harness-naroo --scope local` in that project folder (it turns off only there). `dlc-gate` triggers on phrases like "implement" or "commit", so setting the scope is worth it.

To try a local copy, first clone the repository:

```sh
# in a terminal
git clone https://github.com/neisii/harness-naroo.git
```

Then register the cloned folder as a marketplace and install:

```sh
# in Claude Code
/plugin marketplace add <path to the cloned folder>
/plugin install ai-dlc-harness@harness-naroo
```

## Try it

One command shows how the reversibility check decides. The example rates five situations on the four criteria and puts each into one of four outcomes: do it alone (A) / do it, then report (B) / ask first (C) / hold and ask (D).

```sh
python3 examples/reversibility_demo.py
```

The output is in Korean. Three of the five cases, translated:

```
[1] Fix a variable typo on my own feature branch
    → A  do it alone — reversible, clear, my own area.

[3] Put a 15% discount rate into the code
    → C  ask first — ④ a business decision for a human (veto): reversible, but not mine to decide.

[4] Implement an item the screen spec only describes as "handle that thing there"
    → D  hold and ask — ② unclear what is being asked (veto): set it aside, take the next task.
```

Look at [3]. Changing the discount rate in code is reversible and the request is clear, so it looks like something the AI could just do — but the outcome is "C — ask first," because a discount rate is a business decision for a human. Even with every other criterion fine, one veto criterion stops it. A walk-through you can follow in about five minutes: [QUICKSTART.en.md](./QUICKSTART.en.md).

This example is a taste. Where the harness is actually useful is your own project: once installed, Claude stops for confirmation at each decision point, in the order described in "What happens when you hand it one feature" above.

There is also a tool you can use without installing: a writing linter that finds translationese, emoji, and second-person address in Korean documents (standard-library Python only).

```sh
python3 skills/seosul-lint/seosul_lint.py <docs folder>
```

## Guide map — what to read for what

| To… | Read |
|---|---|
| Find your way by the problem you are having | [Situation map](./docs/guide/00-상황지도.md) (Korean) → its chapters (6 passed without testing · 7 committed or deleted without asking · 9 broke when merged · 10 approvals pile up) |
| Get a taste in five minutes | [QUICKSTART.en.md](./QUICKSTART.en.md) |
| See the whole rule set | [`rules/` 00 summary](./rules/향상된_AI-DLC_00-핵심규칙요약.md) (Korean); the steps are in the table below |
| Fit it to your team's environment | [`docs/환경값-정의.md`](./docs/환경값-정의.md) (Korean) — leave the rules alone and read values such as paths, stack, OS, and session names as your own |
| Split work across several sessions | [`docs/오케스트레이션-구성.md`](./docs/오케스트레이션-구성.md) (Korean), delegation record form [`docs/위임기록-템플릿.md`](./docs/위임기록-템플릿.md) (Korean) |
| Look up an unfamiliar term | [Glossary](./docs/guide/용어집.md) (Korean) |
| Read in English | This page, [QUICKSTART.en.md](./QUICKSTART.en.md), [`docs/overview-en.md`](./docs/overview-en.md) |
| See why it is designed this way | [`design-notes/`](./design-notes/00-인덱스.md) (Korean; design rationale and trial records, in progress) |

**The 12 rule steps**

Each step is one document, and every rule has an ID (for example `CS-01`). Claude reads a step's document right before doing the action it covers.

| Step | ID | Covers |
|---|---|---|
| 1 | `GL` | Base rules for every task (don't fill gaps by guessing, only write what was checked, delete to the trash, writing rules, …) |
| 2 | `RL` | What a human decides and what the AI does |
| 3 | `RQ` | Research scope before implementing, how to ask a human, the blueprint format |
| 4 | `GT` | Approval to start implementing (no implementation before the blueprint is approved) |
| 5 | `CM` | Result review, completion report, commit message |
| 6 | `AG` | How sessions talk to each other, how to hand a task to another session |
| 7 | `BR` | Branch names and the merge flow |
| 8 | `AR` | Where and how work products such as blueprints and completion reports are kept, handover documents |
| 9 | `CC` | Researching common codes and proposing candidates |
| 10 | `TS` | E2E test scenarios and test accounts |
| 11 | `CS` | Commit-plan approval, matching staged files to the plan, risky git commands |
| 12 | `WT` | Creating work branches and worktrees, push, running servers |

## What's inside

**The coherence core**

| Path | What |
|---|---|
| `rules/` | The 12-step rules (Korean) + the `00` summary |
| `skills/dlc-gate/` | Points to the right rule at decision points such as implementing, approving, committing, and verifying |
| `skills/reversibility-gate/` | Four criteria → do it alone / do it, then report / ask first / hold, veto-first; records the evidence as JSON |

**Running several sessions without bottlenecking the human**

| Path | What |
|---|---|
| `skills/session-stall-check/` | Is a session waiting on a human, busy, awaiting instructions, or gone? (from `claude agents` state·status·pid) — and whether to re-request, alert a human, or wake it |
| `skills/session-wake/` | Wake a named background session without creating a duplicate; launch options are restored |
| `skills/qa-inbox/` · `skills/pending-status-check/` | Read-only views of the inter-session waiting ledger (AG-15). For the full setup; not used in small mode (ledger generalization planned for 0.4.0) |
| `skills/patrol-notify/` · `skills/os-notify/` | Back-off notifications for "waiting on a human" items; native OS notification primitive. Patrol is for the full setup; not used in small mode (planned for 0.5.0) |
| `skills/survey-gen/` | Batch the decisions a human must make into one HTML survey; record the answers and track them until applied (default location: `docs/surveys/` in the working repository) |

**Utilities**

| Path | What |
|---|---|
| `skills/seosul-lint/` | Korean writing linter; swap the dictionary file to apply another team's rules |
| `skills/worktree/` | Creates a work branch + sparse worktree per the WT rules |
| `skills/memcheck/` | Checks free memory before starting servers or tests |
| `skills/server-ops/` | Register, build, start, stop, and check servers. Spring Boot + Gradle projects only (it refuses and explains when the project doesn't fit) |
| `skills/safe-delete/` | Moves to the trash instead of deleting permanently, with guards on protected folders |
| `skills/claude-update-check/` | Checks for a new Claude Code version and records the decision (never installs) |

All bundled skills are written to be cross-platform (macOS/Linux/Windows) and use only the Python standard library; some have not been verified on Windows (`server-ops`, `survey-gen`).

## Versions and roadmap

Each version adds one bundle of features you can turn on or leave off.

| Version | What | Status |
|---|---|---|
| 0.1.x | The discipline one session keeps (human gates, quoted evidence, reversibility check, commit safety, writing rules) | Published |
| 0.2.0 | Splitting work across sessions (small mode), narrow delegation (optional), beginner guidebook | This release |
| 0.3.0 | Merging several tasks and shipping them together (integration and release), handling tangled changes, a "verification done" mark | Planned |
| 0.4.0 | Waiting ledger and batched review (the human handles piled-up decisions at a time they choose) | Planned |
| 0.5.0 | Patrol and alerts (finding stalled sessions first) | Planned |
| 0.6.0 | Delegation to a dedicated QA session; the reversibility criteria become formal rules | Planned |
| 0.7.0 | A task-splitting engine; workers launching sub-workers | Planned |
| 1.0.0 | The full setup (the original project's whole setup plus the features of the versions above), complete | Planned |

Canonical roadmap: [`design-notes/10-오케스트레이션-구성.md` §10](./design-notes/10-오케스트레이션-구성.md#10-버전-로드맵-020--100) (Korean).

## Caveats

- **The rules are canonical in Korean.** There is no machine translation of them, so no copy can drift out of sync. The harness does not set your conversation language.
- **Adapt, don't rewrite.** The rules still carry the original team's concrete values as examples. What to read as your own is collected in [`docs/환경값-정의.md`](./docs/환경값-정의.md) (Korean).
- The original harness ran with **Windows** PowerShell/C# tools. Those platform-only tools were left out and rewritten as cross-platform skills.
- This is a **distilled core**, not the whole internal harness. Pipelines tied deeply to the project (scenario verification, document integration, …) are described as methodology only.
- **Data:** the plugin runs locally and sends no personal or project data anywhere. The only outbound calls are `claude-update-check` reading the latest Claude Code version and changelog from GitHub and npm (version info only). Some rules read a local read-only DB credential file (`~/.claude/secrets/devdb_readonly.env`, AG-08) but never print, log, or send it, and no secrets are bundled.

## If it was worth trying, a star

The harness was checked by being used directly on real delivery work, on its own design documents, and on its own multi-session setup. If "an agent harness that checks the whole, not the parts" makes sense to you, a star helps the next team find this repository.

## License

Apache-2.0 © 2026 neisii (Baek Ga-hui) — see [`LICENSE`](./LICENSE) and the attribution in [`NOTICE`](./NOTICE). Versions up to v0.1.2 were released under MIT.

Made by [github.com/neisii](https://github.com/neisii), with [Claude Code](https://claude.com/claude-code). Issues and suggestions welcome.
