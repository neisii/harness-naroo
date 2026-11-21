# 완료보고서 — session-stall-check: 창 대기와 답 대기 구분 (backlog T15, 0.2.1)

> 2026-11-22. 청사진 `blueprint.md`. 브랜치 `0.2.1`.

## 한 일

- **실측(시험 세션 2개, 임시 폴더, Haiku, 확인 뒤 `claude stop`·`claude rm`, 대화 기록 폴더는 safe-delete):**
  - 권한 창에 멈춘 세션: `state=blocked`, `status=waiting`, `waitingFor="permission prompt"`
  - 질문을 남기고 턴을 끝낸 세션: `state=blocked`, `status=idle`, `waitingFor` 없음
- **`session_stall_check.py`:** 분류를 나눔 — 창 대기(`waitingFor` 있음 또는 `status=waiting`), 답 대기(`state=blocked` + pid 있음 + `status=idle`), 프로세스 없음(마지막 상태: 답 대기)(`state=blocked` + pid 없음). `state=blocked` + `busy`는 작업 중으로 넘김. 출력에 `waitingFor`. docstring 사용법을 `python3`로.
- **`SKILL.md`:** 설명, 사용법(`python3 "${CLAUDE_PLUGIN_ROOT}/…"`), 판정 표(1·1-2·1-3), 알려진 한계 두 줄(실측한 `waitingFor`는 permission prompt뿐 / 로그인 만료 등도 답 대기로 보일 수 있음), 활용, 이력.
- **규칙 6단계 AG-15:** 1T 행(창 대기는 사람에게, 답 대기는 요청자가 줄 수 있는 답이면 보내고 사람의 결정이면 사람에게), developer 예외 문장, 체크리스트.
- **그 밖:** 오케스트레이션 가이드 4걸음과 권한 창 줄, README 두 개, 영문 개요, pending-status-check 스킬의 옛 표현.

## 확인

- 분류 함수 사례 12개 통과(창 대기 pid 있음·없음, 답 대기, blocked+pid 없음 두 꼴, blocked+busy, waiting, busy, 할 일 남은 대기, 지시 대기, 프로세스 없음 완료·실패).
- 실제 세션으로 실행: 지시 대기 세션(`master`)과, 재검증이 찾은 `app-developer`(`state=blocked`, pid 없음 → 고친 뒤 "프로세스 없음(마지막 상태: 답 대기), session-wake로 먼저 깨움"). 없는 이름은 exit code 1.
- `python3 design-notes/tools/release_check.py` 실패 0(이 보고서까지 쓴 뒤).

## 새 맥락 재검증

작업 맥락을 물려받지 않은 서브에이전트(general-purpose, Opus)가 diff와 공식 문서(agent-view)를 읽고 재검증했다. **1차 조건부.**

- **버그 1건(직접 재현해 확인):** `state=blocked`면 pid·status와 상관없이 답 대기로 보내, 프로세스가 끝난 세션(`app-developer`)에 "메시지를 보내면 깨어남"이라고 안내했다. 바꾸기 전 판은 이 경우를 "사람에게 알림"으로 안전하게 처리했는데, 나누면서 생긴 회귀다. → pid 없음은 "프로세스 없음(마지막 상태: 답 대기)", busy는 작업 중으로 고침.
- **규칙 6단계에 옛 용어 2곳**(developer 예외 문장, 체크리스트) → "창 대기"로, 체크리스트에 답 대기 갈래 추가.
- **누락:** 답 대기에서 사람의 결정이 필요한 경우의 갈래, 실측 범위 밖의 `waitingFor` 값, 로그인 만료 같은 원인 → 규칙·한계에 적음.
- **경미:** 판정 문구 띄어쓰기, 주어가 빠진 문장, docstring 사용법, 영문 개요 줄바꿈 → 고침.
- 같은 재검증이 `release_check.py` 보강(앵커·이미지 점검)의 거짓 실패·거짓 통과 가능성도 짚어, `~~~` 코드 블록·HTML 태그·`_강조_`·이미지 경로 대조를 고침. setext 제목, 대문자 앵커, `foo-1-1` 같은 드문 경우는 지금 저장소에 사례가 없어 두었다.

## 미검증

- `waitingFor` 값 가운데 `input needed`·`sandbox request`·`worker request`·`dialog open`은 실측하지 않았다(안전한 쪽, 사람에게 알림으로 분류).
- Windows에서는 실행해 보지 않았다(작업 환경이 macOS).
