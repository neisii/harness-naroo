---
name: qa-inbox
description: 대기 장부의 모든 항목을 읽어 qa-master 수신, open 상태인 항목만 긴급도(막힘 우선)와 보낸시각(오름차순)으로 정렬해 표시하는 읽기 전용 CLI입니다(AG-15).
---

# qa-inbox — 대기 장부 조회 (AG-15)

대기 장부(`*.json`)의 모든 항목을 읽어 **현재 qa-master가 처리해야 할 것**만 필터링·정렬해 표시합니다.

정본: `${CLAUDE_PLUGIN_ROOT}/rules/향상된_AI-DLC_6단계-Agent간소통규칙.md` (AG-15).

**읽기 전용**: 장부 수정·삭제 없음. 날짜 파싱 실패, 폴더 없음 등 오류는 표시하되 실패하지 않음(stdout 폴백).

## 실행

```sh
python3 "${CLAUDE_PLUGIN_ROOT}/skills/qa-inbox/qa_inbox.py" \
  [--ledger-dir <경로>] \
  [--recipient <역할어>] \
  [--json]
```

예:
```sh
python3 "${CLAUDE_PLUGIN_ROOT}/skills/qa-inbox/qa_inbox.py"

python3 "${CLAUDE_PLUGIN_ROOT}/skills/qa-inbox/qa_inbox.py" --json

python3 "${CLAUDE_PLUGIN_ROOT}/skills/qa-inbox/qa_inbox.py" \
  --ledger-dir ~/.my-ledger \
  --recipient my-role
```

## 옵션

| 옵션 | 기본값 | 설명 |
|------|-------|------|
| `--ledger-dir <경로>` | `~/.claude/qa-inbox/ledger` | 장부 폴더. 환경변수 `QA_INBOX_LEDGER_DIR` 으로도 설정 가능 |
| `--recipient <역할어>` | `qa-master` | 수신자 필터 |
| `--json` | — | JSON 형식으로 출력(CI/자동화용) |

- `--ledger-dir` 생략 시 환경변수 `QA_INBOX_LEDGER_DIR` 확인. 둘 다 없으면 `~/.claude/qa-inbox/ledger`.
- 폴더가 없어도 에러 대신 안내 메시지 출력(--json이면 error 필드 포함).

## 장부 항목 스키마

각 JSON 파일은 다음 구조를 가집니다 (한글 키 우선, 영문 키 폴백):

```json
{
  "항목": [
    {
      "종류": "상시위임" | "일반 지시",
      "상태": "open" | "hold" | "done",
      "수신자": "qa-master" | "...",
      "요청자": "session-label",
      "보낸시각": "2026-10-27 14:30:00",
      "요지": "스캔 작업 완료 확인 필요",
      "긴급도": "막힘" | "일반"
    }
  ]
}
```

| 필드 | 한글/영문 | 설명 | 기본값 |
|------|---------|------|-------|
| 종류 | `종류` | 항목 분류. 상시위임은 별도 집계 | — |
| 상태 | `상태`/`status` | 필터링 기준(open만 표시) | open(필드 없으면) |
| 수신자 | `수신자`/`recipient` | 필터링 기준 | — |
| 요청자 | `요청자`/`requester` | 발신 세션/역할 | — |
| 보낸시각 | `보낸시각`/`sentAt` | ISO-like 날짜(`YYYY-MM-DD HH:MM:SS` 또는 `T` 구분) | — |
| 요지 | `요지`/`summary` | 항목 설명. 표시는 앞 80자 | — |
| 긴급도 | `긴급도` | 정렬 우선순위. 막힘은 리스트 상단 | 일반 |

## 동작

1. 장부 폴더에서 `*.json` 파일 모두 로드
2. 각 파일의 `항목` 배열을 순회
3. 상시위임(`종류=="상시위임"`) 건수 집계
4. **필터링**: 상태=`open`(또는 없음) AND 수신자=`--recipient` 값
5. **정렬**: ① 긴급도(막힘=0, 나머지=1) ② 보낸시각(오래된 것 먼저)
6. **경과분**: 보낸시각으로부터 현재까지 시간 계산
7. 읽기 문제(JSON 파싱 실패 등) 별도 기록

## 출력

### 테이블 형식(기본)

```
=== qa-inbox (qa-master 수신, 2026-10-27 14:35:00) ===

상시위임 사후 보고 건수: 2

[막힘] master → qa-master  스캔 작업에서 DB 쿼리 타임아웃
  보낸시각 2026-10-27 13:45:00 / 경과 50분
  장부 파일: /path/to/master_20261027.json

[일반] alice → qa-master  화면 추출 완료
  보낸시각 2026-10-27 14:00:00 / 경과 35분
  장부 파일: /path/to/alice_20261027.json
```

막힘(긴급도="막힘")은 빨간색 강조.

### JSON 형식(--json)

```json
{
  "조회시각": "2026-10-27 14:35:00",
  "수신항목": [
    {
      "보낸세션": "master",
      "긴급도": "막힘",
      "보낸시각": "2026-10-27 13:45:00",
      "경과분": 50.0,
      "요지": "스캔 작업에서 DB 쿼리 타임아웃",
      "장부파일경로": "/path/to/master_20261027.json"
    }
  ],
  "건수": 1,
  "상시위임사후보고건수": 2,
  "읽기문제": []
}
```

폴더 없으면:
```json
{
  "error": "LedgerDir not found",
  "path": "~/.claude/qa-inbox/ledger",
  "조회시각": "2026-10-27 14:35:00",
  "수신항목": [],
  "건수": 0,
  "상시위임사후보고건수": 0,
  "읽기문제": [...]
}
```

## 플랫폼 메모

- 표준 라이브러리만 사용. 외부 패키지 필요 없음.
- 날짜 파싱: 정규식 `^\s*(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}(:\d{2})?)` 후 Python `datetime.strptime` 적용.
  파싱 실패 항목은 정렬 시 맨 뒤로 이동.
- 파싱 오류·읽기 실패는 `읽기문제` 배열에 누적. 스크립트 종료 코드는 항상 0(성공).
- 장부 폴더가 빈 경우: "수신 대기 항목이 없습니다." 메시지 출력.
