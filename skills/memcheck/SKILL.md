---
name: memcheck
description: 서버 기동·테스트·훅을 돌리기 전에 OS 여유 메모리와 상위 java 프로세스별 메모리를 읽기 전용으로 점검합니다(WT-10 게이트). "메모리 확인", "여유 메모리", "서버 띄워도 돼?", "메모리 부족 점검" 요청이나 새 서버·테스트·훅을 시작하기 직전에 사용합니다. 여유가 서버 기동 기준(기본 2.5GB) 또는 테스트·훅 기준(기본 4.0GB)에 못 미치면 경고하고 진행 여부를 사람에게 확인받게 합니다. macOS/Linux/Windows 공용(원본 memcheck.ps1의 크로스플랫폼 구현).
---

# memcheck — 여유 메모리 점검 (WT-10 게이트)

정본: 12단계 `${CLAUDE_PLUGIN_ROOT}/rules/향상된_AI-DLC_12단계-워크트리사용규칙.md` (WT-10).
이 스크립트는 원본 `memcheck.ps1`의 **크로스플랫폼 구현**이다. PowerShell이 없는 macOS/Linux에서도 같은 기준·같은 경고로 동작한다.
상태를 바꾸지 않는 읽기 전용 도구라 승인·handshake 없이 아무 세션이나 호출할 수 있다.

## 실행

```sh
python3 "${CLAUDE_PLUGIN_ROOT}/skills/memcheck/memcheck.py" \
  [--server-min-gb 2.5] [--test-min-gb 4.0] [--top 10] [--json] [--watch N] [--process-name java]
```

| 옵션 | 의미 |
|---|---|
| `--server-min-gb` | 서버 기동 기준(기본 2.5GB). 여유가 이 값 미만이면 **[경고]** |
| `--test-min-gb` | 테스트·훅 기준(기본 4.0GB). 서버 기준은 충족하나 이 값 미만이면 **[주의]** |
| `--warn-free-gb` | 종전 호출 호환용 — `--server-min-gb`와 같은 뜻 |
| `--top N` | java 프로세스 상위 N개(기본 10) |
| `--json` | JSON 출력(`Summary`, `Processes`) |
| `--watch N` | N초 간격으로 반복 갱신(Ctrl+C 종료) |
| `--process-name` | 목록에 올릴 프로세스 이름(기본 `java`) |

## 판정 규칙 (원본과 동일)

- 여유 < 서버 기준 → `[경고]` : 새 서버를 띄우기 전에 사람(또는 qa-master)에게 진행 여부를 확인받는다. 테스트·훅도 같은 방식이다.
- 서버 기준 ≤ 여유 < 테스트 기준 → `[주의]` : 서버 기동은 가능하지만 테스트·훅 전에 확인받는다.
- 그 외 → 충족.
- **종료 코드는 항상 0이다**(경고는 출력으로만 알린다). 조회 자체가 불가능하면 2. 판정은 출력 문구를 읽고 한다.

## OS별 여유 메모리 산출

| OS | 총량 | 여유 |
|---|---|---|
| macOS | `sysctl -n hw.memsize` | `vm_stat`의 free + inactive + speculative 페이지 |
| Linux | `/proc/meminfo` `MemTotal` | `MemAvailable` (없으면 MemFree+Buffers+Cached) |
| Windows | `GlobalMemoryStatusEx` (ctypes) | `ullAvailPhys` |

플랫폼마다 "여유"의 정의가 조금씩 달라(캐시·standby 포함 여부) 값이 정확히 같지는 않다. 임계값 판정용 근사치로 쓴다.

## 프로세스 목록

- macOS/Linux: `ps`로 `java` 프로세스의 RSS를, `lsof`가 있으면 LISTEN 포트를 보여준다(없으면 포트는 `-`). 이름 열은 명령행의 `-jar` 파일명 → 메인 클래스 순으로 뽑는다.
- Windows: `tasklist`(작업 집합)와 `netstat -ano`(LISTEN 포트)를 쓴다. 명령행 접근이 표준 도구로는 번거로워 이름 열은 `(java)`로 표시한다.
