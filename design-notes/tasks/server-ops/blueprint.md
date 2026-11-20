# server-ops 청사진

> 상태: 승인됨 (2026-11-20 작성, 같은 날 사용자 지적으로 0절·전용 명시 추가, 같은 날 사용자 승인)
> 양식: 규칙 3단계 RQ-07의 6개 항목. 작업 단위가 화면이 아니라 스킬이라, 환경값 E에 따라 "화면 → 동작", "API → 명령 인터페이스"로 바꿔 읽는다.

## 배경

- 규칙 12단계 WT-10·11은 "서버는 팀의 기존 스크립트로 빌드·구동하고, 상태는 `server-status`로 본다"고 정한다.
- 그 스크립트(`build.ps1`, `start.ps1`, `server-stop.ps1`, `server-status.ps1`)는 원본 SI 전용이라 공개판에 없다. 공개판을 설치한 사람이 규칙을 따르면 없는 도구를 찾게 된다.
- 해결: 각 팀이 자기 서버를 등록하면, 공용 실행기 하나가 빌드·구동·종료·상태 조회를 맡는다.
- **전제: Spring Boot + Gradle 전용.** 원본 SI는 Spring Boot + Gradle 구성이었다. 이 스킬도 그 구성 전용으로 만들고, 스킬 설명(SKILL.md의 `description`과 본문 첫머리)에 "Spring Boot + Gradle 프로젝트 전용"이라고 명시한다. `init`이 제안하는 명령과 검증은 Gradle만 다룬다.
- 설정 파일의 `build`·`start`에는 실제로 실행할 명령을 그대로 적으므로, 서식 자체는 빌더에 묶이지 않는다. 다만 Gradle이 아닌 빌더(npm, make, maven 등)를 공식으로 지원할지, 지원할 필요가 있는지는 검토한 뒤 정한다(backlog T11, 0.2.0 공개 뒤 논의).

## 0. 적용 판단 (스킬을 쓰기 전에)

AI 세션은 이 스킬을 쓰기 전에 사용자의 프로젝트 구성을 대조한다. SKILL.md에 이 절차를 가이드로 넣는다.

| 확인 | 맞는 경우 |
|---|---|
| Gradle 래퍼 | 서버 폴더에 `gradlew`(Windows는 `gradlew.bat`)가 있다 |
| Spring Boot | `build.gradle` 또는 `build.gradle.kts`에 Spring Boot 플러그인(`org.springframework.boot`)이 있다 |
| JDK | `java -version`이 실행된다 |

- **모두 맞으면** 스킬을 쓴다.
- **하나라도 맞지 않으면** 스킬을 실행하지 않는다. 사용자에게 "이 스킬은 Spring Boot + Gradle 전용이라, 이 프로젝트에서는 환경 차이로 실행할 수 없다"고 안내하고, 맞지 않은 항목(예: "`gradlew` 없음, `package.json` 있음")을 함께 알린다. 다른 빌드·구동 명령을 임의로 만들어 대신 실행하지 않는다.
- `init`도 같은 기준으로 자동 확인한다. 맞지 않으면 설정 파일을 만들지 않고, 맞지 않은 항목을 출력한 뒤 종료 코드 2로 끝낸다.

## 1. 동작

| 하위 명령 | 하는 일 | 상태를 바꾸나 |
|---|---|---|
| `init` | 0절의 적용 판단을 자동으로 확인한다. 맞으면 Gradle 명령으로 서버 후보를 제안하고, 사용자가 확정한 값으로 설정 파일을 만든다. 맞지 않으면 설정 파일을 만들지 않고 환경 차이를 안내한다 | 설정 파일만 만든다 |
| `build <서버>` | 등록된 빌드 명령을 실행하고, 출력은 로그 파일에만 남긴다 | 빌드 산출물 |
| `start <서버>` | 포트 점유 확인 → 메모리 확인 → 백그라운드 구동 → PID·로그 기록 | 프로세스 시작 |
| `stop <서버>` | 기본은 종료 대상(포트·PID·작업 폴더·띄운 시각)만 보여 준다. `--yes`가 있을 때만 종료한다 | `--yes`일 때만 |
| `status [<서버>]` | 등록된 서버마다 아래 표의 항목을 본다 | 바꾸지 않음(읽기 전용) |

`status`가 보여 주는 것:

| 항목 | 보는 법 |
|---|---|
| 포트 LISTEN 여부 | `127.0.0.1:<포트>`에 연결 시도 |
| PID | `start`가 남긴 PID 파일. 하네스가 띄우지 않은 프로세스는 "알 수 없음(외부에서 띄움)" |
| 작업 폴더의 브랜치·HEAD·미커밋 건수 | `git -C <폴더>` |
| 헬스 | 등록된 헬스 URL에 GET 1회 |
| 기대 포트와 다름 | 로컬 포트, 또는 워크트리면 로컬 포트 + 차이값과 비교해 경고 |

`start`의 순서와 멈추는 지점:

1. 포트가 점유돼 있으면 **다른 포트를 고르지 않고 멈춘다.** 점유한 쪽을 확인하는 일은 규칙 WT-10의 절차(점유 세션 확인 → 사용 완료 확인 → 사람 확인)를 따른다.
2. `memcheck` 스킬을 부른다. 여유 메모리가 기준 미만이면 경고를 내고 멈춘다. 진행 여부는 사람이 정한다.
3. 구동한 뒤 포트가 LISTEN 상태가 될 때까지 정해진 시간만 기다린다. 시간을 넘기면 로그 끝부분을 보여 주고 실패로 끝낸다.

## 2. 데이터 (설정과 기록 파일)

**설정 파일** `.claude/harness-servers.json` — 팀이 커밋해 공유한다.

```json
{
  "worktreePortOffset": 10000,
  "servers": {
    "api": {
      "dir": ".",
      "build": "./gradlew clean build -x test",
      "start": "./gradlew bootRun --args='--server.port={port}'",
      "port": 8090,
      "health": "http://127.0.0.1:{port}/actuator/health"
    }
  }
}
```

- `{port}`는 실행할 때 실제 포트로 바꾼다. 워크트리에서 띄우면 `port + worktreePortOffset`이 된다.
- 명령은 팀이 쓰는 그대로 적는다. 실행기는 명령을 해석하지 않고 그대로 실행한다. 위 예시처럼 Gradle 명령을 기준으로 한다.

**기록 파일** `.claude/server-ops/` — 커밋하지 않는다(`.gitignore`에 추가 안내).
- `<서버>-<포트>.pid`, `<서버>-<포트>.log`, `<서버>-build.log`

## 3. 명령 인터페이스

```sh
python3 "${CLAUDE_PLUGIN_ROOT}/skills/server-ops/server_ops.py" <하위명령> [<서버>] \
  [--dir <워크트리 경로>] [--port N] [--yes] [--json] [--config <설정 파일>]
```

- Windows는 `python3` 대신 설치된 Python 명령(`python`, `py`)을 쓴다.
- `--dir`를 주면 워크트리 실행으로 보고 포트에 차이값을 더한다. `--port`가 있으면 그 값이 우선한다.
- `--json`은 `status`의 결과를 기계가 읽는 형식으로 낸다.
- Python 표준 라이브러리만 쓴다(다른 공개 스킬과 같은 조건).

## 4. 변경 범위

```
skills/server-ops/
 ├─ SKILL.md          (새로)
 └─ server_ops.py     (새로)
rules/향상된_AI-DLC_12단계-워크트리사용규칙.md
 └─ WT-10·11: sscheck·server-status.ps1·server-stop.ps1·build.ps1·start.ps1 언급을 server-ops로 교체.
    gradlew 예시는 "이 팀 예시"로 남긴다.
rules/향상된_AI-DLC_00-핵심규칙요약.md
 └─ WT-11 줄: "기존 스크립트" → "server-ops"
docs/환경값-정의.md
 └─ C(스택·빌드·서버): 서버 등록 파일이 환경값이라는 줄 추가
```

## 5. 결정사항 (2026-11-20 사용자 결정)

- 공용 실행기 하나가 설정 파일을 읽어 실행한다. 프로젝트별 스크립트 파일은 만들지 않는다.
- 스킬은 하나(`server-ops`)에 하위 명령을 둔다.
- `stop`은 기본으로 대상만 보여 주고, `--yes`가 있을 때만 종료한다.

## 6. 미확정사항

- **다른 빌더 지원:** 지원 방식과 필요성을 검토한 뒤 정한다(backlog T11, 0.2.0 공개 뒤).

- **Windows 검증:** 작업 환경이 macOS라 Windows에서는 검증하지 않는다. 완료보고서에 "Windows에서는 검증하지 않았다"고 적는다. 프로세스 종료 방식은 OS마다 코드를 나눠 둔다(POSIX는 프로세스 그룹 종료, Windows는 `taskkill /T`).
- **외부에서 띄운 서버의 PID:** 하네스가 띄우지 않은 서버는 표준 라이브러리만으로 PID를 알 방법이 OS마다 다르다. 첫 판은 "포트 LISTEN 여부만 보이고 PID는 알 수 없음"으로 둔다. 필요해지면 OS 명령(`lsof`, `netstat`)을 붙인다.

## 검증 계획

- 최소 Spring Boot + Gradle 예제 프로젝트로 `init`이 적용 판단을 통과하고 Gradle 명령 후보를 제안하는지 확인한다.
- `gradlew`가 없는 폴더, Spring Boot 플러그인이 없는 Gradle 프로젝트에서 `init`이 설정 파일을 만들지 않고 환경 차이를 안내하는지 확인한다.
- 이 PC(macOS)에서 실행기 동작(start → status → stop 대상만 → stop `--yes` → status)을 확인한다. 이 PC에 JDK·Gradle이 없으면 실제 Gradle 빌드·구동은 검증하지 못한 것으로 적고, 실행기 동작은 가짜 서버(`python3 -m http.server {port}`)로 확인한다.
- 포트 점유 상태에서 start가 다른 포트를 고르지 않고 멈추는지 확인한다.
- `--dir`로 워크트리 실행 시 포트에 차이값이 더해지는지 확인한다.
- 완료 전 새 맥락 재검증(`dlc-gate`의 독립 재검증)을 거친다.
