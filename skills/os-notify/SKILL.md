---
name: os-notify
description: 순찰·알림 스킬이 호출하는 OS 알림을 띄우는 범용 프리미티브입니다. Windows/macOS/Linux에서 네이티브 알림을 표시하며, 알림 수단이 없으면 stdout으로 폴백합니다.
---

# os-notify — OS 알림 프리미티브

OS 알림을 띄우는 범용 헬퍼입니다. 순찰·알림 스킬이 호출하여 현재 플랫폼의 네이티브 알림(트레이 아이콘, 팝업 등)을 표시합니다. 알림 수단이 없으면 stdout으로 폴백합니다(에러 대신).

**크로스플랫폼 구현**: 원본 `os-notify.ps1`(Windows 전용)의 동작을 macOS/Linux에서도 수행합니다. 각 OS에서 사용 가능한 네이티브 알림을 우선하고, 모두 실패하면 텍스트로 폴백합니다.

## 실행

```sh
python3 "${CLAUDE_PLUGIN_ROOT}/skills/os-notify/os_notify.py" \
  --title <제목> \
  --message <본문> \
  [--level Info|Warning|Error] \
  [--duration <초>] \
  [--test]
```

예:
```sh
python3 "${CLAUDE_PLUGIN_ROOT}/skills/os-notify/os_notify.py" \
  --title "작업 완료" \
  --message "스캔 작업이 끝났습니다." \
  --level Info \
  --duration 5

python3 "${CLAUDE_PLUGIN_ROOT}/skills/os-notify/os_notify.py" --test
```

- `--level`: `Info`(기본값), `Warning`, `Error` 중 하나
- `--duration`: 표시 시간(초). 기본값 8초
- `--test`: 테스트 알림을 표시하고 나머지 인자 무시

## OS별 동작

| OS | 알림 방식 | 실패 시 폴백 |
|---|---------|-----------|
| Windows | PowerShell Toast 알림 또는 `msg` 명령 | stdout |
| macOS | `osascript` + 네이티브 알림 센터 | stdout |
| Linux | `notify-send`(D-Bus) | stdout |

모든 플랫폼에서 알림 수단이 없으면(예: 헤드리스 서버, 데스크톱 없음) stdout에 `[level] title: message` 형식으로 출력하고 **에러를 발생시키지 않습니다.**

## 플랫폼 메모

- 표준 라이브러리만 사용. 추가 패키지 필요 없음.
- Windows: PowerShell이 PATH에 있으면 네이티브 Toast 시도. 없으면 `msg` 사용.
- macOS: `osascript`(항상 사용 가능).
- Linux: `notify-send` 패키지 필요(Ubuntu/Debian: `sudo apt install libnotify-bin`). 없으면 stdout 폴백.
- 타임아웃(5초) 내에 응답 없으면 다음 방식 시도.
