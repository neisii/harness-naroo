---
name: safe-delete
description: 파일·폴더를 지울 때 `rm -rf`나 `Remove-Item` 대신 사용하는 삭제 도구입니다(GL-28). "지워", "삭제해", "정리해" 요청이나 산출물·임시 폴더를 제거해야 할 때 사용합니다. 기본은 휴지통 이동이며, 공용 산출 상위 폴더 자체(홈·루트 포함)는 거부하고, 영구 삭제는 사람 확인 뒤에만 허용합니다. macOS/Linux/Windows 공용(원본 safe-delete.ps1의 크로스플랫폼 구현).
---

# safe-delete — GL-28 삭제 도구

정본: 1단계 `${CLAUDE_PLUGIN_ROOT}/rules/향상된_AI-DLC_1단계-전역제약.md` (GL-28).
이 스크립트는 원본 `safe-delete.ps1`의 **크로스플랫폼 구현**이다. 파일·폴더를 지울 때는 `rm -rf`를 직접 쓰지 않고 이 도구를 쓴다.

## 실행

```sh
python3 "${CLAUDE_PLUGIN_ROOT}/skills/safe-delete/safe_delete.py" <경로>                 # 휴지통 이동(기본)
python3 "${CLAUDE_PLUGIN_ROOT}/skills/safe-delete/safe_delete.py" <경로> --permanent      # 영구 삭제(사람 확인 후에만)
python3 "${CLAUDE_PLUGIN_ROOT}/skills/safe-delete/safe_delete.py" <경로> --force          # 보호 대상 거부 무시(사람 확인 후에만)
python3 "${CLAUDE_PLUGIN_ROOT}/skills/safe-delete/safe_delete.py" <경로> --protect <폴더> # 이번 호출에 보호 폴더 추가(반복 가능)
```

종료 코드: 0 성공(또는 대상 없음), 1 보호 대상 거부, 2 삭제 실패.

## 가드 (GL-28)

- **① 영구 삭제는 확인 뒤에만.** `--permanent`는 사람(또는 qa-master)의 확인을 받은 뒤에만 쓴다. 기본은 항상 휴지통 이동이다.
- **② 공용 산출 폴더 자체 삭제 금지.** 여러 세션이 함께 쓰는 상위 산출 폴더(예: 검증결과/ 같은 폴더)를 통째로 지정하면 거부한다. 그 아래 타임스탬프·세션 하위 폴더만 지정한다. 상위 폴더를 통째로 지우면 다른 세션이 막 만든 하위 폴더까지 함께 사라지는 사고가 난다.
  - 보호 목록은 환경변수 `SAFE_DELETE_PROTECTED`(OS 경로 구분자 — Unix `:`, Windows `;`)와 `--protect`로 지정한다. 새 공용 폴더가 생기면 환경변수에 추가한다.
  - 홈 디렉터리와 파일시스템 루트는 항상 보호된다.
  - 정말 그 폴더 자체를 지워야 하면(흔치 않음) 사람 확인 후 `--force`.
- **③ 삭제 전 파일 수 표시.** 폴더면 "파일 N 개"를 출력하므로, 의도한 범위인지 확인하고 진행한다.
- 경로는 와일드카드로 해석하지 않고 문자 그대로 다룬다. 파일명에 `[`·`]`·`*`·`?`가 있어도 "대상 없음"으로 조용히 건너뛰지 않는다. 대상이 없으면 그 사실을 출력하고 종료 코드 0으로 끝난다.

## OS별 휴지통 이동

| OS | 방법 |
|---|---|
| macOS | `osascript`로 Finder 휴지통 이동. 실패하면 `~/.Trash`로 직접 이동(이름 충돌 시 번호 부여) |
| Linux | `gio trash`가 있으면 사용, 없으면 XDG 휴지통(`$XDG_DATA_HOME` 또는 `~/.local/share/Trash`)에 `files/`+`info/*.trashinfo`로 이동 |
| Windows | `SHFileOperationW`(ctypes, `FOF_ALLOWUNDO`)로 휴지통 이동 |

출력의 `[...]` 안에 실제로 쓰인 방식이 표시된다. 휴지통 이동은 되돌릴 수 있지만, 폴백(`~/.Trash`, XDG)은 OS의 "원래 위치로 복원"과 연동되지 않을 수 있다.
