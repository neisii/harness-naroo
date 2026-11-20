# AI-DLC Harness (naroo)

[한국어](./README.md) · **English**

**An agent reports "done." But whether its result still fits the whole process and system — who checks that?**

A Claude Code harness that checks an agent's output against **whole-system coherence**, not just whether the one task "succeeded" — through human gates, re-verification in a fresh context, and a reversibility check. A 12-step rule system distilled from a real SI delivery.

*For SI developers — and, naturally, people who work in Korean — who hold that an agent succeeding at its task isn't the finish line. Keeping the whole system coherent is, and it has to be checkable.*

> Distilled and anonymized from a real next-gen public-procurement build (2026). On that project this
> harness helped deliver **34 screens about a month ahead of schedule**, grew to **13 rules · 27 skills ·
> 31 tools**, and ran **7 role-scoped sessions** with a patrol loop every 10 minutes.
> See [`NOTICE.md`](./NOTICE.md) for how it was anonymized, and [`docs/overview-en.md`](./docs/overview-en.md)
> for the full picture.

> **Language note.** The canonical rules and most docs are in **Korean** — the first audience is Korean SI teams.
> This page and [`docs/overview-en.md`](./docs/overview-en.md) are the English entry points. The harness does
> **not** force a conversation language: talk to Claude in whatever language you work in.

---

## What makes it different

Most agent tooling asks *"did this task succeed?"* This harness asks *"did this task leave the whole intact?"*

1. **Human gate before implementation.** Blueprint → **human approval** → implement → verify → completion report. Nothing gets implemented before approval.
2. **"Verified" means actually verified.** Work that could not be checked is recorded as *unverified*, never quietly passed.
3. **Re-verification in a fresh context.** A checker that shares the producer's context shares its blind spots. Before a commit is approved, a verifier that did **not** inherit that context looks again. In our own dogfood runs (using the harness on real work ourselves), this second look caught real gaps that the first, same-context check had passed.
4. **No self-grading.** The session that produced a result never approves it. Producer ≠ approver.
5. **Reversibility check, veto-first.** "Do it alone, or stop and ask?" is decided from four criteria — reversible? clear? scope? business rule? — If **any one** criterion trips, the agent does not proceed on its own: it pauses right there and asks a human for approval, or holds and waits. The other criteria looking fine cannot outweigh it.
6. **Use the platform, don't rebuild it.** The harness steers the flow; it does not try to control everything. Where Claude Code already has a setting (permissions, commit attribution, background sessions), the harness uses it instead of re-implementing it.

## Two ways to use it

| | Single session (since 0.1) | Multiple sessions (0.2.0, opt-in) |
|---|---|---|
| What | The per-session discipline: blueprint → approval → implement → verify, reversibility, commit safety, writing rules | Splitting work across several Claude Code sessions: **human (decides) → gateway session (relays & watches) → worker sessions (implement)** |
| Who approves | You | Still you. The gateway is a **communication window, not a gate** — it relays your approvals verbatim and escalates anything not on its written delegation list |
| Needs | Install the plugin | The plugin + a short delegation record. You stand in for the dedicated QA session, ledger, and patrol loop ("small mode") |
| Next | — | Gradually generalize the original SI's dedicated QA session, waiting ledger, patrol loop, etc., so teams can add them one at a time |
| Guide | `rules/` (start at `00`) | [`docs/오케스트레이션-구성.md`](./docs/오케스트레이션-구성.md) (Korean) |

The multi-session setup is new in 0.2.0 and has been dogfooded on a real repository: gate round-trips, narrow delegation (the gateway approving commit plans only after independent + fresh-context verification), and a three-worker run through PR and merge. It is still young — small samples, and the guide marks what is not yet verified.

## Install

Requires [Claude Code](https://claude.com/claude-code).

```sh
# in Claude Code
/plugin marketplace add neisii/harness-naroo
/plugin install ai-dlc-harness@harness-naroo
```

Then restart or run `/reload-plugins`. The `dlc-gate` skill activates at AI-DLC decision points, and the rule documents load from the plugin root.

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

See a rule decide, in one command — a runnable slice of the reversibility rule that routes real situations to *do it / report after / stop and ask / hold*:

```sh
python3 examples/reversibility_demo.py
```

Watch case **[3]**: an action that's reversible, clear, and looks like "your call" still gets stopped — because it's a business decision. That one-glance veto is the whole point. Full ~5-minute walk-through: **[QUICKSTART.md](./QUICKSTART.md)**.

The core value shows up **inside your own project**: once installed, `dlc-gate` stops you at the real decision points (before implementing, before committing, when something is marked "verified").

Also standalone — the Korean-prose linter: `python3 skills/seosul-lint/seosul_lint.py path/to/docs` (flags translationese, emoji, 2nd-person; standard-library Python).

## What's inside

**The coherence core**

| Path | What |
|---|---|
| `rules/` | The 12-step canonical rules (Korean) + the `00` summary index |
| `skills/dlc-gate/` | Points you to the right rule *at the moment you act* (gate, commit, verify…) |
| `skills/reversibility-gate/` | Four criteria → autonomous / audit-after / approve-before / hold, veto-first; records the evidence as JSON |

**Running several sessions without bottlenecking the human**

| Path | What |
|---|---|
| `skills/session-stall-check/` | Is a session waiting on a human, busy, awaiting instructions, or gone? (from `claude agents` state·status·pid) — and whether to re-request, alert a human, or wake it |
| `skills/session-wake/` | Wake a named background session without creating a duplicate; launch options are restored |
| `skills/qa-inbox/` · `skills/pending-status-check/` | Read-only views of the inter-session waiting ledger (AG-15) |
| `skills/patrol-notify/` · `skills/os-notify/` | Back-off notifications for "waiting on a human" items; native OS notification primitive |

**Utilities**

| Path | What |
|---|---|
| `skills/seosul-lint/` | Korean prose linter, dictionary-driven — swap the dictionary for your own rules |
| `skills/worktree/` | Work branch + sparse worktree per the WT rules |
| `skills/memcheck/` | Free-memory check before starting servers/tests |
| `skills/safe-delete/` | Move to trash instead of permanent delete, with guards |
| `skills/claude-update-check/` | Check for a new Claude Code version and record a decision (never installs) |

**Docs**

| Path | What |
|---|---|
| `docs/overview-en.md` | English overview + case studies |
| `docs/오케스트레이션-구성.md` | Multi-session (small mode) setup guide — Korean |
| `docs/위임기록-템플릿.md` | Delegation record template, incl. optional narrow delegation — Korean |
| `docs/환경값-정의.md` | Which values to swap for your own environment (paths, stack, OS, commit attribution, conversation language) — Korean |
| `design-notes/` | Design rationale and dogfood records (Korean, work in progress) |
| `NOTICE.md` | Anonymization disclosure |

All bundled skills are cross-platform (macOS/Linux/Windows) and use only the Python standard library.

## Caveats

- The **rules are in Korean** and kept as the canonical source (not machine-translated, to avoid the two drifting apart).
- **Adapt, don't rewrite.** The rules keep the original team's concrete values as examples; [`docs/환경값-정의.md`](./docs/환경값-정의.md) lists what to swap.
- The original harness ran on **Windows** with PowerShell/C# tooling; that platform-specific tooling was excluded.
- This is a **curated core**, not the full internal harness. Deeply project-coupled pipelines are described as methodology only.
- **Data handling:** the plugin runs locally and sends no personal or project data off-platform. The one outbound call is `claude-update-check`, which reads the latest Claude Code version and changelog from GitHub and the npm registry — version info only. Some rules read a local, read-only DB credential (`~/.claude/secrets/devdb_readonly.env`, AG-08) that is never printed, logged, or transmitted; no secrets are bundled.

## If the dog food was edible, leave a star

This harness eats its own dog food — on a real delivery, on its own design notes, and on its own multi-session setup. If the idea lands — an agent harness that checks the **whole**, not just the part — a star helps the next team find it.

## License & credits

MIT © 2026 neisii (Baek Ga Hui) — see [`LICENSE`](./LICENSE).

Author: [github.com/neisii](https://github.com/neisii). Built with [Claude Code](https://claude.com/claude-code). Issues and improvements welcome.
