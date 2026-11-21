# 청사진 — session-stall-check: 창 대기와 답 대기 구분 (backlog T15, 0.2.1)

> 2026-11-22. 사용자 지시("T15랑 release_check 보강 넣어서 진행해")로 착수. 계획은 대화에서 먼저 제시했다: "`claude agents` 출력에 `waitingFor`가 실제로 나오는지 확인한 뒤 고칠 안을 드린다". 확인 뒤 바로 구현했고, 이 문서는 그 계획을 기록으로 옮긴 것이다.

## 문제

- 스킬은 `state=blocked` 또는 `status=waiting`을 한데 묶어 "사람 입력 대기"로만 알렸다.
- gate3에서 게이트웨이가 둘을 구분하려고 실무자 대화 기록을 직접 읽느라 권한 창을 더 불렀다.
- 둘은 할 일이 다르다: 권한 창에 멈춘 세션은 메시지가 들어가지 않아 사람이 세션을 열어 답해야 하고, 턴을 끝내고 답을 기다리는 세션은 메시지를 보내면 깨어난다.

## 근거

- Claude Code agent-view 문서: 백그라운드 세션의 `waitingFor`는 `permission prompt`·`input needed`·`sandbox request`·`worker request`·`dialog open` 가운데 하나(T13 확인, `tasks/release-0.2.0/T13-공식안내글-비교.md` 5절).
- 실측 계획: 시험 세션 둘(권한 창에 멈추게 / 질문을 남기고 턴을 끝내게)을 임시 폴더에서 Haiku로 띄워 `claude agents --all --json`을 본다. 끝나면 끄고 기록을 치운다.

## 바꿀 것

1. `skills/session-stall-check/session_stall_check.py`: 분류를 "창 대기(`waitingFor` 있음 또는 `status=waiting`)"와 "답 대기(`state=blocked`+`status=idle`)"로 나누고, 출력에 `waitingFor`를 더한다.
2. `SKILL.md`: 설명·판정 표·활용·이력. 사용법 줄을 다른 스킬과 같은 `python3 "${CLAUDE_PLUGIN_ROOT}/…"` 꼴로.
3. 규칙 6단계 AG-15 재요청 절차, 오케스트레이션 가이드 4걸음, README 두 개, 영문 개요의 스킬 설명.

## 확인

- 분류 함수를 사례 표로 시험(창 대기·답 대기·작업 중·할 일 남은 대기·지시 대기·프로세스 없음).
- 실제 세션과 없는 이름으로 스크립트 실행.
- `release_check.py` 통과, 새 맥락 재검증.
