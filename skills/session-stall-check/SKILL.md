---
name: session-stall-check
description: 세션 1개가 지금 창 대기(권한 창 등에 멈춤)인지, 답 대기(턴을 끝내고 답을 기다림)인지, 작업 중인지, 지시 대기인지, 프로세스가 없는지 즉시 조회한다. "저 세션 지금 막힌 거 아냐?", "재요청 전에 수신자 상태 확인" 요청에 쓴다. `claude agents`의 state·status·pid·waitingFor 조합으로 판정하고, 재요청해도 되는지·사람에게 알릴지·session-wake로 깨울지까지 한 줄로 알려 준다. 읽기 전용.
---

# session-stall-check — 세션 상태 즉시 조회

번들 스크립트: `${CLAUDE_PLUGIN_ROOT}/skills/session-stall-check/session_stall_check.py` (Python 3, 표준 라이브러리만 사용). 읽기 전용이라 승인 없이 바로 호출한다.

## 사용법

```
python3 "${CLAUDE_PLUGIN_ROOT}/skills/session-stall-check/session_stall_check.py" <세션명>
python3 "${CLAUDE_PLUGIN_ROOT}/skills/session-stall-check/session_stall_check.py" <세션명> --threshold-min 15
```

출력(한 줄): `세션: <이름> | state: <값> | status: <값> | waitingFor: <값|없음> | pid: <있음|없음> | 마지막 기록: <N분 전> | 분류: <…> | 판정: <…>`

## 판정 기준

`claude agents --all --json`의 필드를 아래 순서로 본다(Claude Code agent-view 문서 기준, 2.1.328에서 실측 확인, `waitingFor` 구분은 2026-11-22 실측).

| 순서 | 조건 | 분류 | 판정 |
|---|---|---|---|
| 1 | `waitingFor` 있음 또는 `status=waiting` (pid 무관) | 창 대기(권한 창·입력 창 등, `waitingFor` 값을 함께 보임) | 메시지가 들어가지 않음. 재요청하지 말고 사람에게 알림, 사람이 그 세션을 열어(attach) 답해야 함 |
| 1-2 | `state=blocked` + pid 있음 + `status=idle`, `waitingFor` 없음 | 답 대기(턴을 끝내고 사람·게이트 답을 기다림) | 메시지를 보내면 깨어남. 그 세션이 기다리는 답(게이트 승인 등)을 보냄. 사람의 결정이 필요한 답이면 사람에게 알림. 같은 요청을 다시 보내지는 않음 |
| 1-3 | `state=blocked` + pid 없음 | 프로세스 없음(마지막 상태: 답 대기) | 답을 기다리다 유휴 정리로 끝난 세션. 메시지가 닿지 않음 — session-wake로 깨운 뒤 기다리던 답을 보냄 |
| 2 | pid 있음 + `status=busy` | 작업 중 | 끝날 때까지 기다림. 기록이 `--threshold-min`(기본 15분) 넘게 안 바뀌면 멈춤 의심 표시 |
| 3 | pid 있음 + `status=idle` + `state=working` | 할 일 남은 대기(`/loop` 등) | 정상, 재요청 가능 |
| 4 | pid 있음 + 그 밖의 `idle` | 지시 대기 | 정상, 재요청 가능 |
| 5 | pid 없음 | 프로세스 없음 | 메시지가 닿지 않음 — session-wake로 먼저 깨움 |

- **`done`은 종료가 아니다.** 턴을 끝내고 다음 지시를 기다리는 살아 있는 세션도 `state=done`이다. 살았는지는 pid로 본다.
- 같은 이름이 여러 레코드면 pid 있는 것 가운데 가장 늦게 시작한 것(실제로 메시지를 받는 쪽)을 쓴다. session-wake와 같은 기준이다.
- 목록에 아예 없으면(이름 오타·기록 정리) 그 사실만 알리고 exit code 1.

## 알려진 한계

- `waitingFor` 값 가운데 실측한 것은 `permission prompt`뿐이다. `input needed`(Claude가 묻는 질문)는 공식 문서상 peek 패널 답장으로 답할 수 있다고 하지만, 세션 간 메시지로도 풀리는지는 미확인이라 안전한 쪽(창 대기, 사람에게 알림)으로 둔다.
- 공식 문서는 `blocked`의 원인으로 만료된 로그인, 첫 프롬프트 없이 띄운 경우도 든다. 이때 `waitingFor`가 없으면 답 대기로 보일 수 있다. 답을 보내도 풀리지 않으면 사람이 그 세션을 열어 본다.

- 조회 순간의 스냅샷이다. 특히 `blocked`는 늦게 반영되거나 이미 풀렸을 수 있어, 조치하기 전에 한 번 더 조회한다.
- '마지막 기록'은 transcript(`~/.claude/projects/*/<sessionId>.jsonl`) 수정 시각이다. 턴이 끝난 뒤에도 자리 비움 요약(away_summary)이 몇 초~몇 분 뒤 자동 기록되어 실제보다 조금 최근으로 보인다. 판정에는 busy 멈춤 의심에만 쓴다.
- 백그라운드 작업(예: 백그라운드 Bash)을 걸어 두고 기다리는 세션이 3번(`working`+`idle`)으로 보이는지는 미확인이다(`/loop` 세션은 3번으로 실측됨).

## 활용

다른 세션에 재요청을 보내기 직전 수신자를 조회한다. 창 대기면 재요청 대신 사람에게 알리고(사람이 그 세션을 열어 답해야 함), 답 대기면 기다리는 답을 보내고, 프로세스 없음이면 session-wake로 깨운 뒤 보낸다.

## 바뀐 이력

- 2026-11-22: 사람 대기를 창 대기와 답 대기로 나눔(backlog T15). 새 맥락 재검증에서 pid 없는 `blocked`(답을 기다리다 유휴 정리로 끝난 세션)를 답 대기로 잘못 보내는 버그를 잡아, 프로세스 없음으로 따로 분류함. 시험 세션으로 실측: 권한 창에 멈춘 세션은 `state=blocked`·`status=waiting`·`waitingFor="permission prompt"`, 질문을 남기고 턴을 끝낸 세션은 `state=blocked`·`status=idle`·`waitingFor` 없음. `waitingFor` 값 목록(permission prompt·input needed·sandbox request·worker request·dialog open)은 Claude Code agent-view 문서. 이전 판은 둘을 "사람 입력 대기"로 묶어, 게이트웨이가 실무자 대화 기록을 직접 읽어 확인해야 했다(gate3).

- 2026-11-19: 판정 기준을 state·status·pid 조합으로 바꿈. 이전 판은 "state는 입력 대기 중에도 working에 고정된다"는 전제로 transcript 무활동 시간만 봤고, `state=done`을 '세션 종료됨'으로 판정해 살아 있는 지시 대기 세션을 종료로 잘못 보였다. 기준은 사용자가 만든 세션 현황판(claude-agents-board)의 분류를 옮겨 왔다.
