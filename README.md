# AI-DLC Harness (naroo)

A reusable **Claude Code harness** for AI-driven development on real SI / enterprise projects —
a 12-step rule system with **human gates**, **role sessions**, and a few portable skills.

> Distilled and anonymized from a real next-gen public-procurement build (2026). On that project this
> harness helped deliver **34 screens about a month ahead of schedule**, grew to **13 rules · 27 skills ·
> 31 tools**, and ran **7 role-scoped sessions** with a patrol loop every 10 minutes.
> See [`NOTICE.md`](./NOTICE.md) for how it was anonymized, and [`docs/overview-en.md`](./docs/overview-en.md)
> for the full picture.

한국어 요약은 [아래](#한국어-요약)에 있습니다.

---

## What this is

Most "AI coding" setups break down on a real delivery project: the model guesses business rules, edits
outside its lane, marks untested work as verified, or stalls silently waiting for input. This harness is
the set of **rules, gates, and session roles** that kept an AI pair-programming workflow honest and shippable
over a 4-month SI project.

The core idea: **treat the AI like a disciplined teammate.** Clear boundaries, a human approval gate before
implementation, one canonical source of truth per rule, and "verified only means actually verified."

## The model

- **12-step rule system** (`rules/`) — the canonical rules (정본), each step entered *just before* the action
  it governs. IDs like `GL` (global), `RL` (roles), `GT` (gate), `CM` (commit), `AG` (agent-to-agent),
  `CS` (commit safety), `WT` (worktree). Start at [`rules/향상된_AI-DLC_00-핵심규칙요약.md`](./rules).
- **Human Gate** — blueprint → **human (or `qa-master`) approval** → implement → verify → completion report.
  Nothing gets implemented before approval.
- **Role sessions** — decision-making, rule edits, and tool-building are split into separate sessions
  (`qa-master`, `ai-rule-master`, `skill-gen-master`, `*-developer`) so no one session is a bottleneck.
- **Skills** (`skills/`) — a curated, portable subset you can actually run (see below).

## Install

Requires [Claude Code](https://claude.com/claude-code).

```sh
# in Claude Code
/plugin marketplace add neisii/harness-naroo
/plugin install ai-dlc-harness@harness-naroo
```

Then restart or reload. The `dlc-gate` skill activates at AI-DLC decision points, and the rule documents
load from the plugin root.

To try it locally before publishing:

```sh
/plugin marketplace add /path/to/harness-naroo
/plugin install ai-dlc-harness@harness-naroo
```

## What's inside

| Path | What |
|---|---|
| `rules/` | The 12-step canonical rule documents (Korean, 정본) + the `00` summary index |
| `skills/dlc-gate/` | Points you to the right canonical rule *at the moment you act* (gate, commit, verify…) |
| `skills/session-wake/` | Wake a named background session by name, without creating a duplicate |
| `skills/session-stall-check/` | Detect whether a background session is silently stalled on input (via transcript mtime) |
| `skills/claude-update-check/` | Check for a new Claude Code version and record an approve/defer/reject decision (never installs) |
| `skills/worktree/` | Create a work branch + sparse worktree per the WT rules (no-upstream branch, remote behind-check, sparse-checkout) — cross-platform (macOS/Linux/Windows) |
| `skills/memcheck/` | Read-only check of free physical memory (+ top Java processes) before starting a server — cross-platform (WT-10 gate) |
| `skills/safe-delete/` | Move to the OS trash instead of permanent delete, with protected-folder/home/root guards (GL-28) — cross-platform |
| `skills/os-notify/` | Fire a native OS notification (Windows/macOS/Linux) with stdout fallback — the primitive the patrol/alert skills call |
| `skills/patrol-notify/` | Back-off notifier for "waiting on a human" items (AG-15): reads a status JSON, notifies via os-notify, tracks per-item back-off state |
| `skills/qa-inbox/` | Read-only view of a delegate's (`qa-master`) open inter-session requests from the ledger, sorted blocked-first then oldest (AG-15) |
| `skills/pending-status-check/` | Read-only aggregation of the whole AG-15 waiting ledger into text or JSON (severity by deadline multiple, hold/deferred, rule-propagation, 3T pre-check) — the status-JSON producer that `patrol-notify` consumes |
| `docs/overview-en.md` | English overview + the project case studies (scenario verification, stall prevention, bottleneck removal…) |
| `design-notes/` | Design rationale for the harness's **next version** — positioning, the human-bottleneck & flow-control problems, branch/ledger strategy, reversibility gate, and writing rules, tied together by an operating-loop diagram (Korean; 7 Mermaid diagrams). Work-in-progress notes. |
| `NOTICE.md` | Anonymization & reference-copy disclosure |

The bundled skills use only the Python standard library and were rewritten to be portable.

## Caveats

- The **rule documents are in Korean** (kept as the canonical source; not machine-translated to avoid drift).
  The README and `docs/overview-en.md` are the English entry points.
- **Reference copies won't run as-is** outside the skills above — paths and names were genericized. See `NOTICE.md`.
- The original harness ran on **Windows** with PowerShell/C# tooling (patrol notifier, status widgets); that
  platform-specific tooling was **excluded** and is only described in `docs/overview-en.md`.
- This is a **curated core**, not the full internal harness. Deeply project-coupled pipelines
  (E2E scenario verification, doc consolidation, API-spec generation) are described as methodology rather than
  shipped as runnable code.

## 한국어 요약

실제 SI 프로젝트(2026, 공공 조달 차세대)에서 운영하던 Claude Code 하네스를 **익명화해 공개**한 것입니다.
핵심은 **12단계 규칙 체계 + Human Gate(사람/`qa-master` 승인) + 역할 세션**으로 AI를 "규율 있는 팀원"처럼
운영하는 방식입니다.

설치: `/plugin marketplace add neisii/harness-naroo` → `/plugin install ai-dlc-harness@harness-naroo`

- `rules/` : 12단계 정본 규칙(한글)
- `skills/` : 설치하면 실제 동작하는 범용 스킬 10개(dlc-gate, session-wake, session-stall-check, claude-update-check, worktree, memcheck, safe-delete, os-notify, patrol-notify, qa-inbox)
  - `worktree`·`memcheck`·`safe-delete`·`os-notify`·`patrol-notify`·`qa-inbox`는 Windows 전용 PowerShell을 **macOS/Linux/Windows 공용 Python**으로 포팅한 것
- `docs/overview-en.md` : 영문 개요 + 사례
- `design-notes/` : 하네스 **다음 버전 설계 근거**(포지셔닝·사람 병목·브랜치/장부·가역성 게이트·서술 규칙 + 작동 루프). 한글, 다이어그램 7개. 진행 중 메모.
- `NOTICE.md` : 익명화 고지

결합도 높은 파이프라인(시나리오 검증, 문서 통합 등)은 `docs/`에 방법론으로만 소개했습니다.

## License & credits

MIT © 2026 neisii (Baek Ga Hui) — see [`LICENSE`](./LICENSE).

Author: [github.com/neisii](https://github.com/neisii). Built with [Claude Code](https://claude.com/claude-code).
Issues and improvements welcome.
