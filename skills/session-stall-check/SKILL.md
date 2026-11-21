---
name: session-stall-check
description: 세션 1개가 지금 사람 입력 대기(승인·응답·로그인)인지, 작업 중인지, 지시 대기인지, 프로세스가 없는지 즉시 조회한다. "저 세션 지금 막힌 거 아냐?", "재요청 전에 수신자 상태 확인" 요청에 쓴다. `claude agents`의 state·status·pid 조합으로 판정하고, 재요청해도 되는지·사람에게 알릴지·session-wake로 깨울지까지 한 줄로 알려 준다. 읽기 전용.
---

# session-stall-check — 세션 상태 즉시 조회

번들 스크립트: `${CLAUDE_PLUGIN_ROOT}/skills/session-stall-check/session_stall_check.py` (Python 3, 표준 라이브러리만 사용). 읽기 전용이라 승인 없이 바로 호출한다.

## 사용법

```
python -X utf8 ${CLAUDE_PLUGIN_ROOT}/skills/session-stall-check/session_stall_check.py <세션명>
python -X utf8 ${CLAUDE_PLUGIN_ROOT}/skills/session-stall-check/session_stall_check.py <세션명> --threshold-min 15
```

출력(한 줄): `세션: <이름> | state: <값> | status: <값> | pid: <있음|없음> | 마지막 기록: <N분 전> | 분류: <…> | 판정: <…>`

## 판정 기준

`claude agents --all --json`의 세 필드를 아래 순서로 본다(Claude Code agent-view 문서 기준, 2.1.328에서 실측 확인).

| 순서 | 조건 | 분류 | 판정 |
|---|---|---|---|
| 1 | `state=blocked` 또는 `status=waiting` (pid 무관) | 사람 입력 대기 | 재요청하지 말고 사람에게 알림 |
| 2 | pid 있음 + `status=busy` | 작업 중 | 끝날 때까지 기다림. 기록이 `--threshold-min`(기본 15분) 넘게 안 바뀌면 멈춤 의심 표시 |
| 3 | pid 있음 + `status=idle` + `state=working` | 할 일 남은 대기(`/loop` 등) | 정상, 재요청 가능 |
| 4 | pid 있음 + 그 밖의 `idle` | 지시 대기 | 정상, 재요청 가능 |
| 5 | pid 없음 | 프로세스 없음 | 메시지가 닿지 않음 — session-wake로 먼저 깨움 |

- **`done`은 종료가 아니다.** 턴을 끝내고 다음 지시를 기다리는 살아 있는 세션도 `state=done`이다. 살았는지는 pid로 본다.
- 같은 이름이 여러 레코드면 pid 있는 것 가운데 가장 늦게 시작한 것(실제로 메시지를 받는 쪽)을 쓴다. session-wake와 같은 기준이다.
- 목록에 아예 없으면(이름 오타·기록 정리) 그 사실만 알리고 exit code 1.

## 알려진 한계

- 조회 순간의 스냅샷이다. 특히 `blocked`는 늦게 반영되거나 이미 풀렸을 수 있어, 조치하기 전에 한 번 더 조회한다.
- '마지막 기록'은 transcript(`~/.claude/projects/*/<sessionId>.jsonl`) 수정 시각이다. 턴이 끝난 뒤에도 자리 비움 요약(away_summary)이 몇 초~몇 분 뒤 자동 기록되어 실제보다 조금 최근으로 보인다. 판정에는 busy 멈춤 의심에만 쓴다.
- 백그라운드 작업(예: 백그라운드 Bash)을 걸어 두고 기다리는 세션이 3번(`working`+`idle`)으로 보이는지는 미확인이다(`/loop` 세션은 3번으로 실측됨).

## 활용

다른 세션에 재요청을 보내기 직전 수신자를 조회한다. 사람 입력 대기면 재요청 대신 사람에게 알리고, 프로세스 없음이면 session-wake로 깨운 뒤 보낸다.

## 바뀐 이력

- 2026-11-19: 판정 기준을 state·status·pid 조합으로 바꿈. 이전 판은 "state는 입력 대기 중에도 working에 고정된다"는 전제로 transcript 무활동 시간만 봤고, `state=done`을 '세션 종료됨'으로 판정해 살아 있는 지시 대기 세션을 종료로 잘못 보였다. 기준은 사용자가 만든 세션 현황판(claude-agents-board)의 분류를 옮겨 왔다.
