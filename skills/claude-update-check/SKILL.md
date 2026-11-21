---
name: claude-update-check
description: Claude Code 새 버전이 나왔는지 점검하고 사용자의 승인/거부/보류 결정을 기록한다. "Claude Code 업데이트 확인", "새 버전 나왔어?", "업데이트 승인/거부/보류 기록" 요청에 쓴다. 점검은 시스템을 바꾸지 않는다(설치·업데이트 없음, 상태 파일에만 기록). 설치·업데이트 명령은 절대 실행하지 않는다.
---

# claude-update-check — Claude Code 업데이트 점검과 승인 기록

번들 스크립트: `${CLAUDE_PLUGIN_ROOT}/skills/claude-update-check/claude_update_check.py` (Python 3, 표준 라이브러리만 사용; `claude`와 `npm`이 PATH에 있어야 한다).

권장 운용: `~/.claude/settings.json`의 `env`에 `DISABLE_AUTOUPDATER=1`을 두어 자동 업데이트를 끄고, 새 버전은 이 도구가 알리고 사용자가 승인했을 때만 설치한다.

## 사용법
```
python ${CLAUDE_PLUGIN_ROOT}/skills/claude-update-check/claude_update_check.py                          # 12시간이 지났을 때만 실제 점검, 아니면 상태 파일만 읽음
python ... --force                  # 간격 무시하고 즉시 점검
python ... --decide 승인|거부|보류 [--version X.Y.Z]   # 사용자 결정 기록(생략하면 최신 버전)
python ... --status                 # 상태 파일 요약, 점검 안 함
```
사용자 결정은 사용자가 말한 뒤에만 `--decide`로 기록한다. AI가 임의로 결정하지 않는다.

## 점검 내용
- 현재 버전: `claude --version`. 최신 버전: `npm view @anthropic-ai/claude-code dist-tags`의 `latest`(`stable`도 함께 기록).
- 새 버전이면 공개 CHANGELOG에서 현재 초과~최신 이하 버전 절의 앞부분(버전당 최대 8줄, 최대 3개 버전)을 요약해 상태 파일에 남긴다. 보안 관련 단어(security·CVE·bypass 등)가 있으면 `보안수정의심`을 켠다(키워드 판정이라 확정이 아니다).
- 조회가 실패하면 `점검결과`에 실패를 적고 이전 값을 유지한다.
- 설치·업데이트 코드(`npm install`·`claude update` 호출)는 이 도구에 없다.

## 상태 파일
기본 위치 `~/.claude/claude-update-check/state.json` (환경변수 `CLAUDE_UPDATE_CHECK_STATE`로 변경 가능)

| 키 | 내용 |
|---|---|
| 확인시각 / 점검결과 | 마지막 실제 점검 시각 / 정상 또는 실패 |
| 현재버전 / 최신버전 / stable버전 | 비교 대상(최신은 npm `latest`) |
| 릴리스노트요약 / 보안수정의심 | 새 버전일 때만 채움 |
| 사용자결정 | `{버전, 결정(승인/거부/보류), 결정일}` |
| 거부보류버전 | 거부·보류한 버전과 결정 |
| 보류재알림 | 보류 버전의 재알림 진행(`다음점검`→`대기`→`완료`) |

## 알림 규칙
- 새 버전이 있고 그 버전에 결정이 없으면 "새 버전 X (현재 Y) — 승인/거부/보류 결정 필요"를 사용자에게 알린다.
- 거부한 버전은 다시 올리지 않는다. 더 새 버전이 나오면 그 버전으로 다시 올린다.
- 보류한 버전은 다음 실제 점검 때 한 번 더 올린 뒤 조용히 둔다. 더 새 버전이 나오면 다시 올린다.
- 승인한 버전은 설치될 때까지 `승인됨, 설치 대기` 줄이 남고, 현재 버전이 최신 이상이 되면 사라진다.

## 승인 후 설치 절차
설치는 AI가 하지 않는다. 사용자가 모든 세션을 종료한 상태에서 직접 설치한다.
1. 사용자가 모든 Claude Code 세션을 종료한다.
2. 사용자가 [공식 설치 안내](https://code.claude.com/docs/en/setup)에서 설치한 방식(네이티브 설치·Homebrew·npm 등)에 맞는 방법으로, 승인한 버전을 직접 설치한다.
3. `claude --version`과 `claude agents`가 정상인지 확인한다.
4. `session-wake`로 필요한 세션을 재기동한다.
5. `claude_update_check.py --force`로 현재 버전이 승인한 버전이 되었는지 확인한다.
