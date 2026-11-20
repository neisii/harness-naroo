---
name: survey-gen
description: 사람에게 물을 결정을 모아 HTML 설문으로 만들고, 사람이 답한 텍스트를 기록·관리하는 CLI입니다. "설문 만들어", "사용자 결정 설문", "결정 사항 한 번에 물어봐", "설문 응답 기록", "설문 반영 완료 처리", "설문 인덱스 갱신" 요청이나, 사람에게 물을 결정이 여럿 쌓여 한 번에 묻고 싶을 때 씁니다. 설문 하나가 폴더 하나이고 상태(미응답, 응답됨, 반영 완료)는 survey.json에서 관리하며 파일은 옮기지 않습니다. 표준 라이브러리만 쓰는 macOS/Linux/Windows 공용 Python.
---

# survey-gen — 결정 설문 만들기·기록·관리

사람에게 물을 결정이 여럿이면 하나씩 묻지 않고, 선택지·배경·권고안을 담은 HTML 설문 한 장으로 묻는다.
사람은 설문에서 답하고 "답변 생성 → 복사"한 텍스트를 세션에 붙여 넣는다. 세션은 그 텍스트를 `record`로 기록한다.

## 흐름

1. **만들기(`new`)**: 세션이 질문 JSON을 파일로 쓰고 `new`를 실행한다. 폴더·`survey.json`·`survey.html`이 생긴다. 사람에게 `survey.html` 경로를 알려 준다.
2. **기록(`record`)**: 사람이 붙여 넣은 답변 텍스트를 세션이 파일로 저장하고 `record`를 실행한다. `answers.md`가 생기고 상태가 "응답됨"이 된다. 출력된 경고(빠진 문항·없는 번호·선택지에 없는 답·제목 불일치)는 사람에게 전하고, 필요하면 되묻는다.
3. **반영 완료(`close`)**: 결정을 코드·문서에 반영한 뒤 `close`로 반영한 곳(커밋·문서)을 적는다.

상태 흐름: **미응답 → 응답됨(`record`) → 반영 완료(`close`)**. 파일을 옮기지 않는다.

## 실행

```sh
python3 "${CLAUDE_PLUGIN_ROOT}/skills/survey-gen/survey_gen.py" new --input <질문.json> [--root <설문 루트>]
python3 "${CLAUDE_PLUGIN_ROOT}/skills/survey-gen/survey_gen.py" record <설문ID> --input <답변.txt> [--root <설문 루트>]
python3 "${CLAUDE_PLUGIN_ROOT}/skills/survey-gen/survey_gen.py" close <설문ID> --note "<반영한 곳>" [--root <설문 루트>]
python3 "${CLAUDE_PLUGIN_ROOT}/skills/survey-gen/survey_gen.py" index [--root <설문 루트>]
```

- Windows는 `python3` 대신 설치된 Python 명령(`python`, `py`)을 쓴다.
- `--root`가 없으면 `./docs/surveys/`를 쓴다.
- 설문ID는 설문 폴더 이름이다(예: `2026-11-20-01-결정모음`). `new`가 출력한다.

| 하위 명령 | 하는 일 |
|---|---|
| `new` | 입력을 검증하고 설문 폴더를 만든다. 검증에 실패하면 아무것도 만들지 않고 오류를 나열한 뒤 종료 코드 1로 끝난다 |
| `record` | 답변 텍스트를 문항 번호로 대조해 `answers.md`에 저장하고 상태를 "응답됨"으로 바꾼다. 경고가 있어도 읽은 만큼은 저장한다. 읽을 수 있는 답변이 하나도 없으면 저장하지 않고 종료 코드 1로 끝난다 |
| `close` | 상태를 "반영 완료"로 바꾸고 `closedAt`·`closeNote`를 적는다 |
| `index` | `index.md`를 다시 만든다. 위 세 명령은 끝에 자동으로 함께 갱신한다. 내용(갱신 시각 줄 제외)이 같으면 쓰지 않는다 |

## 질문 JSON

```json
{
  "title": "설문 제목",
  "note": "(선택) 상단 안내",
  "slug": "(선택) 폴더 이름에 붙일 짧은 이름",
  "items": [
    {
      "id": "1",
      "title": "문항 제목",
      "background": "배경",
      "options": [{"key": "A", "label": "..."}, {"key": "B", "label": "..."}],
      "recommend": "A",
      "recommendReason": "(선택) 권고 이유",
      "hold": "(선택) 응답 전까지 보류되는 작업",
      "movedTo": "(선택) 이 문항을 옮긴 설문ID"
    }
  ]
}
```

- 검증: `title` 필수 / `items` 1개 이상 / 문항마다 `id`(중복 불가)·`title`·`background` 필수 / `options` 2개 이상(`key` 중복 불가, `key`·`label` 필수) / `recommend`는 `options`의 `key` 중 하나.
- `status`·`createdAt`·`answeredAt`·`closedAt`·`closeNote`는 도구가 채운다. 입력에 넣지 않는다.
- 문항을 다른 설문으로 옮겼으면 그 문항에 `movedTo`(옮겨 간 설문ID)를 적는다. `index.md` 비고에 나타난다.

## 폴더 구조

```
<설문 루트>/
  index.md
  2026-11-20-01-<짧은 이름>/
    survey.json
    survey.html
    answers.md
```

- 폴더 이름은 날짜, 그날의 순번(2자리), 짧은 이름 순이다. 순번은 설문 루트의 기존 폴더를 보고 정한다.
- `index.md`는 미응답을 맨 위에 두고, 나머지는 만든 날·순번 내림차순이다. 열은 상태·제목·문항 수·만든 날·설문 링크·답변 링크·비고다.

## 답변 텍스트 형식

설문 화면의 "답변 생성"이 만드는 형식이다. `record`는 이 형식만 읽는다. 사람이 붙여 넣은 텍스트를 고치지 말고 그대로 파일에 저장한다.

```
[<설문 제목> 응답]
1. <문항 제목> → A. <선택지>
   메모: <메모, 여러 줄이면 이어지는 줄은 3칸 들여쓰기>
2. <문항 제목> → (선택 없음)
   메모: ...
미응답: 2      (모두 답했으면 "미응답: 없음")
```

## 설문 화면 기능

선택 버튼, 문항별 메모, 권고안 일괄 선택, 답변 생성·복사, 미응답 문항 표시, 브라우저에 진행 상태 저장, 다크 모드.
화면은 `template.html`이 정한다. `survey.html`을 손으로 고치지 않는다(고칠 일이 있으면 `template.html`을 고친 뒤 새로 만든다).
