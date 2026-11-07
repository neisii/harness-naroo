---
name: session-stall-check
description: bg 세션 1개가 지금 AskUserQuestion 등으로 정체(사람 입력 대기)된 것으로 보이는지 즉시 조회한다. "저 세션 지금 막힌 거 아냐?", "재요청 전에 수신자 상태 확인" 요청에 쓴다. `claude agents`의 state만으로는 입력 대기와 정상 작업 중을 구분 못 하므로 transcript mtime 경과를 추가로 본다.
---

# session-stall-check — 세션 정체 즉시 조회

번들 스크립트: `${CLAUDE_PLUGIN_ROOT}/skills/session-stall-check/session_stall_check.py` (Python 3, 표준 라이브러리만 사용). 읽기 전용이라 승인 없이 바로 호출한다.

## 사용법

```
python -X utf8 ${CLAUDE_PLUGIN_ROOT}/skills/session-stall-check/session_stall_check.py <세션명>
python -X utf8 ${CLAUDE_PLUGIN_ROOT}/skills/session-stall-check/session_stall_check.py <세션명> --threshold-min 15
```

출력(한 줄): `세션: <이름> | state: <값> | transcript 무활동: <N>분 | 판정: <정상|입력 대기 의심|...>`

- **판정 기준**: `state == "done"`이면 "정상(세션 종료됨)". 아니면 transcript(jsonl, `~/.claude/projects/*/<sessionId>.jsonl`) mtime 경과가 `--threshold-min`(기본 15분) 이상이면 "입력 대기 의심"(정상적으로 다음 지시를 기다리는 중일 수도 있음을 같이 표기), 아니면 "정상".
- **왜 state가 아니라 transcript mtime을 보는가**: `claude agents --json`의 `state`는 AskUserQuestion 대기 중에도 멈추기 직전 값("working")에 그대로 고정된다 — state만으로는 "입력 대기"와 "정상 작업 중"을 구분할 수 없다.
- 세션이 `claude agents --all --json`에 없으면(이름 오타·daemon 정리) 그 사실만 알리고 exit code 1.
- 같은 이름이 여러 레코드로 보이면 `pid` 있는(살아있는) 레코드를 우선하고, 없으면 `startedAt`이 가장 큰 것을 쓴다.

## 활용
다른 세션에 재요청을 보내기 직전, 수신자 세션명을 조회해 "입력 대기 의심"이면 재요청 대신 사람에게 알린다.

## 알려진 한계
- "입력 대기 의심"은 AskUserQuestion 정체와 "정상적으로 다음 지시를 기다리는 유휴 상태"를 구분하지 못한다. 판정은 참고용이고 최종 판단은 사람이 한다.
- `claude agents --json`은 조회 순간의 스냅샷이다 — 조회와 실제 재요청 사이에 상태가 바뀔 수 있다.
