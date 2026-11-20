---
name: server-ops
description: Spring Boot + Gradle 프로젝트 전용입니다. 서버를 등록·빌드·구동·종료하고 상태를 조회할 때(WT-10·11) 씁니다. "서버 띄워", "서버 빌드", "서버 종료", "서버 상태", "포트 확인", "서버 등록" 요청이나 새 서버를 띄우기 직전에 사용합니다. 쓰기 전에 gradlew·Spring Boot 플러그인·JDK를 확인하고, 하나라도 맞지 않으면 실행하지 않습니다. 포트가 점유돼 있으면 다른 포트를 고르지 않고 멈춥니다. macOS/Linux/Windows 공용(Windows는 검증하지 않음).
---

# server-ops — 서버 빌드·구동·종료·상태

Spring Boot + Gradle 프로젝트 전용

정본: 12단계 `${CLAUDE_PLUGIN_ROOT}/rules/향상된_AI-DLC_12단계-워크트리사용규칙.md` (WT-10·11).
팀이 서버를 한 번 등록하면, 공용 실행기 하나가 빌드·구동·종료·상태 조회를 맡는다. 프로젝트별 스크립트 파일은 만들지 않는다.

## 쓰기 전에: 적용 판단

스킬을 쓰기 전에 서버 폴더에서 아래 세 가지를 확인한다.

| 확인 | 맞는 경우 |
|---|---|
| Gradle 래퍼 | 서버 폴더에 `gradlew`(Windows는 `gradlew.bat`)가 있다 |
| Spring Boot | `build.gradle` 또는 `build.gradle.kts`에 Spring Boot 플러그인(`org.springframework.boot`)이 있다 |
| JDK | `java -version`이 실행된다 |

- 모두 맞으면 스킬을 쓴다.
- 하나라도 맞지 않으면 스킬을 실행하지 않는다. 사용자에게 "이 스킬은 Spring Boot + Gradle 전용이라, 이 프로젝트에서는 환경 차이로 실행할 수 없다"고 안내하고, 맞지 않은 항목(예: "`gradlew` 없음, `package.json` 있음")을 함께 알린다.
- 다른 빌드·구동 명령(npm, make, maven 등)을 임의로 만들어 대신 실행하지 않는다.
- `init`도 같은 기준으로 자동 확인한다. 맞지 않으면 설정 파일을 만들지 않고, 맞지 않은 항목을 출력한 뒤 종료 코드 2로 끝낸다.

## 실행

```sh
python3 "${CLAUDE_PLUGIN_ROOT}/skills/server-ops/server_ops.py" <하위명령> [<서버>] \
  [--dir <워크트리 경로>] [--port N] [--yes] [--json] [--config <설정 파일>]
```

Windows는 `python3` 대신 설치된 Python 명령(`python`, `py`)을 쓴다. 이때 init이 제안하는 명령도 `gradlew.bat`을 쓴다.

| 하위 명령 | 하는 일 | 상태를 바꾸나 |
|---|---|---|
| `init` | 적용 판단을 자동 확인한다. 맞으면 Gradle 명령 후보를 보여 주고, `--write`일 때만 설정 파일을 만든다 | 설정 파일만 |
| `build <서버>` | 등록된 빌드 명령을 실행한다. 출력은 로그 파일에만 남기고, 실패하면 끝 20줄을 보여 준다 | 빌드 산출물 |
| `start <서버>` | 포트 점유 확인, 메모리 확인, 백그라운드 구동, PID·로그 기록, LISTEN 대기 | 프로세스 시작 |
| `stop <서버>` | 종료 대상(포트·PID·폴더·띄운 시각)만 보여 준다. `--yes`가 있을 때만 종료한다 | `--yes`일 때만 |
| `status [<서버>]` | 서버마다 LISTEN·PID·git·헬스를 본다 | 바꾸지 않음(읽기 전용) |

서버가 하나만 등록돼 있으면 `<서버>`를 생략할 수 있다.

### init

```sh
# 후보만 보기 (파일을 만들지 않는다)
... server_ops.py init --name api --port 8090
# 확정 (설정 파일 쓰기)
... server_ops.py init --name api --port 8090 --write
```

- 대상 폴더는 현재 폴더이고, `--dir`로 바꾼다.
- 설정 파일은 `.claude/harness-servers.json`이다. 팀이 커밋해 공유한다.
- 설정 파일이 이미 있으면 덮어쓰지 않는다. 덮어쓰려면 `--force`를 붙인다.
- 기록 폴더 `.claude/server-ops/`는 커밋하지 않는다. `.gitignore`에 추가한다.

설정 파일 형식은 아래와 같다. `{port}`는 실행할 때 실제 포트로 바뀐다.

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

실행기는 명령을 해석하지 않고 셸로 그대로 실행한다. 그래서 설정 파일을 바꾸는 일은 코드를 바꾸는 일처럼 검토한다.

서버 이름은 영문·숫자·`.`·`_`·`-`만 쓴다(`..`는 안 됨). 기록 파일이 기록 폴더 밖을 가리키지 않게 하기 위해서다.

### 옵션

| 옵션 | 의미 |
|---|---|
| `--dir <경로>` | 워크트리에서 실행한다. 포트는 `port + worktreePortOffset`이 된다. init에서는 대상 폴더다 |
| `--port N` | 포트를 직접 지정한다. 차이값보다 우선한다 |
| `--yes` | `stop`에서 실제로 종료한다 |
| `--json` | `status` 결과를 JSON으로 낸다 |
| `--config <파일>` | 설정 파일 경로(기본 `.claude/harness-servers.json`) |
| `--timeout N` | `start`가 포트 LISTEN을 기다리는 초(기본 120) |
| `--ignore-memcheck` | `start`에서 사람이 승인한 뒤 메모리 경고를 넘긴다 |
| `--name`, `--health`, `--write`, `--force` | `init` 전용 |

### 종료 코드

| 코드 | 뜻 |
|---|---|
| 0 | 정상 |
| 1 | 오류(설정 없음, 서버 이름 불일치, 실행 실패 등) |
| 2 | 적용 불가(`init`의 환경 점검 실패). 인자 오류도 2다 |
| 3 | `start`: 포트 점유로 중단 |
| 4 | `start`: 여유 메모리가 서버 기동 기준 미만이라 중단(사람이 정한다) |
| 5 | `start`: 기동 시간 초과 또는 포트를 열기 전 종료. 시간 초과면 띄우다 만 프로세스를 종료한다 |

`build`는 빌드 명령의 종료 코드를 그대로 낸다.

## 포트가 점유돼 있을 때 (WT-10)

`start`는 포트가 이미 LISTEN 중이면 다른 포트를 고르지 않고 종료 코드 3으로 멈춘다. AI 세션은 아래 순서를 따른다.

1. 어느 세션이 그 포트를 쓰는지 확인한다(`status`, 필요하면 `lsof -i :<포트>`).
2. 그 세션의 사용이 끝났는지 확인한다.
3. 정리가 필요하면 사람에게 확인받는다. 사람이 승인하면 `stop --yes`로 종료한다.

PID 기록이 없는 포트(외부에서 띄운 서버)는 `stop --yes`로도 종료하지 않는다. 사람이 직접 정리한다.

## 기록 파일

`.claude/server-ops/`에 남는다.

- `<서버>-<포트>.pid`: 하네스가 띄운 프로세스의 PID. 파일 수정 시각이 띄운 시각이다
- `<서버>-<포트>.log`: 서버 출력
- `<서버>-build.log`: 빌드 출력

## 메모리 점검

`start`는 같은 스킬 묶음의 `memcheck`(`../memcheck/memcheck.py`)를 부른다. 여유가 서버 기동 기준 미만이면 경고를 내고 종료 코드 4로 멈춘다. `memcheck`가 없거나 읽지 못하면 안내만 하고 계속한다.

## 한계

- Windows에서는 검증하지 않았다. 프로세스 종료는 OS마다 나눠 두었다(POSIX는 프로세스 그룹 종료, Windows는 `taskkill /T`).
- 외부에서 띄운 서버의 PID는 알 수 없다. `status`는 LISTEN 여부만 보여 준다.
