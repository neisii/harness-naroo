---
name: worktree
description: AI-DLC 12단계(WT-02~WT-04, WT-06)에 따라 작업 브랜치와 sparse 워크트리를 만들 때 사용합니다. 수동 `git worktree add` 대신 이 스크립트를 써서 업스트림 없는 로컬 브랜치 생성·원격 뒤처짐 검사·sparse-checkout·메트릭 환경변수 기록을 한 번에 수행합니다. macOS/Linux/Windows 공용(원본 new-worktree.ps1의 크로스플랫폼 구현).
---

# worktree — 작업 브랜치 + sparse 워크트리 생성 (WT-02/WT-03/WT-06)

정본: 12단계 `${CLAUDE_PLUGIN_ROOT}/rules/향상된_AI-DLC_12단계-워크트리사용규칙.md` (WT-02~WT-04, WT-06).
이 스크립트는 WT-03이 지정하는 전용 헬퍼(`new-worktree.ps1`)의 **크로스플랫폼 구현**이다. PowerShell이 없는
macOS/Linux에서는 이 `new_worktree.py`가 그 역할을 하며, 동작은 원본과 동일하다. **수동 `git worktree add`를
쓰지 않는다(WT-03).**

## 실행

```sh
python3 "${CLAUDE_PLUGIN_ROOT}/skills/worktree/new_worktree.py" \
  --project <프로젝트폴더명> \
  --branch  <새 브랜치명> \
  --name    <워크트리명> \
  [--base <기준브랜치>] [--root <프로젝트 상위 경로>] [--metrics-root <메트릭 루트>] [--no-exclude-docs]
```

예:
```sh
python3 "${CLAUDE_PLUGIN_ROOT}/skills/worktree/new_worktree.py" \
  --project buyer-portal --branch team-a/alice_dev/screen-058 --name b-m-x-foo-task
```

- `--root` 생략 시 환경변수 `PRJ_ROOT`, 없으면 현재 디렉터리를 프로젝트 상위로 본다. 프로젝트 경로 = `<root>/<project>`.
- `--base` 생략 시 `--branch`의 첫 구간 + `/main`(예: `team-a/...` → `team-a/main`). 그 브랜치가 로컬에 없으면
  `main`으로 대체하고 알린다. `--base`를 명시하면 로컬에 없을 때 대체 없이 실패한다.

## 하는 일 / 안 하는 일

한 번에: 사전점검 → `git fetch origin <base>`(30초 제한, 비대화식) → 뒤처짐 검사 → `core.longpaths=true` →
업스트림 없는 로컬 브랜치(`branch --no-track`) → `worktree add --no-checkout` → sparse-checkout(`/*`, `!/docs/`) →
checkout → 워크트리 `.claude/settings.local.json`에 `env.PRJ_METRICS_DIR` 병합 기록 → 검증 출력.

**커밋·push·삭제·docs 생성·기존 워크트리 수정은 하지 않는다.** 실패하면 그 자리에서 멈추고 무엇이 남았는지
출력하며, 스스로 정리하지 않는다.

## 멈추는 경우(규칙 준수)

| 상황 | 조치 |
|---|---|
| 로컬 기준 브랜치가 origin보다 뒤처짐 | 로컬 기준 브랜치를 임의로 갱신하지 말고 사람(또는 qa-master)에게 확인 (WT-03) |
| fetch 실패·30초 초과(로그인 만료 등) | 사람이 `! git -C <프로젝트> fetch`로 한 번 로그인한 뒤 다시 실행 |
| `.claude/settings.local.json`이 git-ignore 안 됨 | 환경파일이 커밋되지 않도록 중단 — 사람에게 보고 |
| 기준 브랜치 없음(`--base` 명시) / 브랜치·워크트리 이름 충돌 | 인자 확인 |

## 플랫폼 메모

- 표준 라이브러리만 사용하며 `git`이 PATH에 있으면 된다. `core.longpaths`는 Windows용이지만 설정해도 무해하다.
- Windows 260자 경로 한계 점검은 Windows에서만 수행한다.
- Windows에서는 동등한 PowerShell 원본(`new-worktree.ps1`)을 써도 된다(이 레포에는 미포함; WT 규칙 문서 참조).
