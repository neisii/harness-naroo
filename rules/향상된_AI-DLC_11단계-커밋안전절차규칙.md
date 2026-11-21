# 11단계 · 커밋 안전 절차

> **목적:** AI가 커밋할 때 반드시 거치는 안전 절차와 추적 제외 목록을 정한다. 5단계 CM-13의 "커밋 전 확인"을 구체적인 명령·절차로 정한 문서다.
> **언제 읽나:** 커밋 계획을 만들기 직전([00 요약](향상된_AI-DLC_00-핵심규칙요약.md) 2장).
> **이 문서가 정하지 않는 것:** 커밋 메시지는 [5단계](향상된_AI-DLC_5단계-결과물검토및커밋규칙.md) CM-03~CM-12, push는 [12단계](향상된_AI-DLC_12단계-워크트리사용규칙.md) WT-09가 정본이다.

---

## 규칙

### CS-01 · 모든 커밋은 계획을 먼저 승인받는다 **[사람 확인]**

- 커밋 전에 "커밋 계획"(대상 브랜치명, 파일 목록, 메시지 초안)을 사람에게 제시하고 명시적 승인을 받는다. 예외 없이 모든 커밋에 적용한다. qa-master가 승인한 경우도 승인으로 인정하며(2단계 RL-12), 승인자와 일시를 기록한다.
- 대상 브랜치명은 매번 명시한다. 현재 체크아웃된 브랜치를 가정하고 생략하지 않는다.
- 계획을 만들 때 먼저 CS-09 추적 제외 목록과 대조해, 해당 파일은 처음부터 계획에 넣지 않는다(CS-09 예외로 사람이 지정한 파일은 제외).
- **조직이 소스 식별자 헤더 규칙을 쓰면**(원본 환경 예: `@programId`/`@processId`), 소스 파일이 포함된 커밋은 변경 파일별 헤더 표기 여부와 값의 근거(참조 문서와 항목)를 계획에 함께 제시한다. 둘 중 하나라도 빠진 소스가 있으면 계획을 확정하지 않고 보완한다. 문서에서 못 찾아 `NA`로 적은 항목은 누락이 아니다(규칙은 조직의 소스 식별자 표기 규칙). 그런 규칙이 없는 환경이면 이 항목은 건너뛴다.
- 계획을 제시하지 않았거나 승인을 받지 못했으면 커밋하지 않는다.
- 여러 화면·여러 커밋을 연속으로 진행해도 커밋마다 반복한다. "방금 승인받았으니 괜찮겠지"라며 생략하지 않는다.

> 이 승인은 CS-02(스테이징 대조)보다 앞선 게이트다. 먼저 "무엇을 커밋할지"를 승인받고, 실제 스테이징이 그 계획과 같은지 대조한 뒤 커밋한다.
>
> 이유: 브랜치를 잘못 알고 있었거나 다른 브랜치로 바뀌어 있었을 가능성을 사람이 그 자리에서 확인할 수 있어야 한다.

### CS-02 · 커밋 직전에 스테이징을 승인 목록과 대조한다

- `git diff --cached --stat`(또는 `--name-only`)로 실제 스테이징 내용을 확인하고, 승인받은 목록과 1:1로 대조한다.
- "지정 파일만 add했으니 됐다"며 넘어가지 않는다. 명령으로 직접 확인하기 전에는 커밋하지 않는다.
- 이 단계에서도 CS-09 목록의 경로가 보이면, 사람이 CS-09 예외로 지정한 파일이 아닌 한 이상 신호로 보고 사람에게 확인받는다(2차 안전장치).

### CS-03 · `git add`는 스테이징을 비우지 않는다

- `git add <file>`은 지정 파일을 스테이징에 추가할 뿐이다. 이전 작업에서 남은 staged 잔여물은 그대로 남는다.
- 여러 논리적 변경이 섞인 작업 트리에서 특정 파일만 커밋하려면 먼저 `git restore --staged .`로 스테이징을 비운 뒤 원하는 파일만 다시 add한다.

### CS-04 · 커밋 직후 실제 커밋 내용을 확인한다

- 커밋 직후 `git show --stat HEAD`로 실제로 무엇이 커밋됐는지 확인한다.
- CS-02를 거쳤더라도 생략하지 않는다. 사전 확인이 놓친 것을 잡는 마지막 기회다.

### CS-05 · 복구 커밋도 같은 절차를 거친다

이전 커밋 실수를 고치는 복구·정정 커밋(예: `chore` 커밋)도 CS-02·CS-04를 예외 없이 거친다.

> 이유: 복구 시도 자체가 staged 잔여물 같은 같은 원인으로 새 실수를 반복할 수 있다.

### CS-06 · 되돌리기 어려운 git 명령은 사람 확인 후 실행한다 **[사람 확인]**

- `.git/index.lock` 등 잠금 파일 삭제, `--force`류 옵션, `reset`/`rebase`, `git commit --amend`(커밋 이력을 바꾸는 명령) 등은 근거(타임스탬프, 프로세스 상태 등)가 있어 보여도 AI 판단만으로 실행하지 않는다. 이미 push된 커밋의 amend는 force push가 필요하므로 사람이 한다(사용자 확정 2026-10-25).
- 잠금 파일에 담긴 경고 문구(예: "다른 git 프로세스가 열려 있을 수 있음")를 무시하지 않는다.
- 실행 전에 상황과 근거를 사람에게 알리고 확인받는다.
- Remote push는 위험해 보이는지와 상관없이 기본적으로 사람이 직접 실행한다. AI는 명령문만 제시한다. qa-master 승인 기록이 있는 경우만 예외다(12단계 WT-09, 2단계 RL-12).

### CS-07 · 브랜치 전환용 stash는 범위를 제한한다

- `git stash push -u`(untracked 포함)를 pathspec 없이 쓰지 않는다. 8단계 산출물 폴더(`docs/<팀구분>/<이름약자>/`)는 의도적으로 untracked라서 `-u`가 통째로 쓸어간다(실제로 발생한 사고).
- `.metrics` 원장은 저장소 밖에 기록하므로(12단계 WT-02·WT-13) 보통은 브랜치 전환을 막지 않는다.
- 전환을 막는 파일이 `.metrics/ledger-anon-*.jsonl`(Claude Code 자동 생성 원장)뿐이면 그 파일만 지정한다: `git stash push -u -- .metrics/<파일>`. 전환 작업이 끝나면 같은 stash를 pop한다. 삭제하거나 `.gitignore`에 넣는 것으로 대신하지 않는다.
- stash 대상이 추적 파일뿐이면 `-u` 없이 `git stash push`를 쓴다. `-u`가 꼭 필요하면 `docs/<팀구분>/`를 pathspec에서 빼거나 미리 백업한다.
- 이미 `-u`로 쓸어갔다면 전체 stash를 pop/apply하지 않는다(무관한 변경까지 되살아난다). `git restore --source=<stash>^3 -- docs/<팀구분>/<이름약자>`로 untracked 커밋(세 번째 부모)에서 해당 경로만 복원한다.
- 8단계 산출물 폴더를 git에서 제외해야 하면 팀이 공유하는 `.gitignore`가 아니라 저장소별 `.git/info/exclude`(로컬 전용)에 정확한 팀구분 경로(예: `docs/team2/`)만 등록한다. `docs/` 전체를 등록하지 않는다(커밋 추적되는 다른 `docs/` 하위 내용이 있을 수 있다).

### CS-08 · 브랜치 규칙과 실제 관행이 다르면 계획 제시 때 먼저 확인받는다

- 7단계 브랜치 규칙과 저장소의 실제 관행(예: 특정 유형 변경은 팀 main에 직접 커밋하는 관행)이 다르다는 걸 알게 되면, 사람이 물을 때까지 기다리지 않고 커밋 계획을 제시할 때 먼저 알린다.
- 어느 한쪽을 정답으로 간주하지 않고 차이를 제시해 사람에게 확인받는다(1단계 GL-19).

### CS-09 · 추적 제외 목록

아래 경로·패턴은 모든 <접두사>_* 프로젝트에 공통인 추적 제외 대상이다. 커밋하지 않는다는 뜻이며 파일을 지우라는 뜻이 아니다. 각 프로젝트의 `.gitignore`와 별개의 추가 안전장치라서, `.gitignore`에 없어도 해당하면 제외한다.

> **환경값(이 팀 예시):** 이 절의 구체 파일·경로(`logback-spring.xml`·`application*.yaml`·`gradle.properties`, MyBatis `mapper/`, Flyway `db/migration/`, `static/js/common` 등)는 이 팀 스택(Java·Spring·Gradle·MyBatis·Flyway) 예시다. 핵심 원리는 "빌드 산출물·로컬 설정·비밀·대용량 바이너리를 커밋하지 않는다"이며, 구체 패턴은 내 스택의 대응물로 바꿔 읽는다(`docs/환경값-정의.md` C항목). 목록에 `README.md`·`CLAUDE.md`·`.gitignore`·`.github`·`Dockerfile`·빌드 스크립트처럼 보통 커밋하는 파일이 있는 것은 이 팀이 그 파일들을 따로 관리해서다. 내 저장소의 제외 목록은 환경값 C에 선언하고, 선언이 없으면 핵심 원리에 해당하는 파일만 제외한다.

- 1차 대조: 커밋 계획을 만들 때(CS-01).
- 2차 대조: 스테이징을 확인할 때(CS-02).

**패턴 해석:** `.gitignore`와 같은 문법으로 해석한다.

- `*`는 폴더 경계(`/`)를 넘지 않는다. 중간에 `/`가 있는 패턴은 저장소 루트 기준이다.
- 중간에 `/`가 없는 패턴(`CLAUDE.md`, `*.png`, `gradle` 등)은 어느 깊이에 있든 같은 이름이면 해당한다.
- 폴더를 가리키는 항목(`.claude`, `src/main/resources/static/js/common` 등)은 그 폴더 아래 전체가 해당한다.

| 파일 예 | 해당 여부 |
|---|---|
| `src/main/resources/logback-spring.xml` | 제외 |
| `src/main/resources/application-local.yaml` | 제외 |
| `src/main/resources/mapper/contract/ContractMapper.xml` | 커밋 가능(`*`가 `mapper/`를 넘지 않음) |
| `src/main/resources/db/migration/V1__init.sql` | 커밋 가능 |

**예외 [사람 확인]:** `build`/`ci`/`docs` type 커밋처럼 목록에 있는 파일을 꼭 커밋해야 하면, 사람이 커밋 계획을 승인할 때 그 파일을 명시적으로 지정한 경우에만 포함한다. 계획에는 해당 파일을 "CS-09 해당 — 사람 지정"으로 표시한다. AI가 먼저 포함을 제안할 수는 있지만 스스로 포함하지 않는다. 청사진 승인 때 사람이 그 파일을 원문으로 지정한 예외도 사람 지정으로 보고, 그 작업의 이후 커밋 계획에도 적용한다. 이때 계획에는 "CS-09 해당 — 청사진에서 사람 지정"과 그 원문을 적고, 파일이나 바뀌는 내용이 청사진 때와 다르면 다시 확인받는다. CS-09 예외가 포함된 계획은 qa-master가 CS-01 승인을 하기 전에 사람이 그 예외 지정을 먼저 확인한다(qa-master 승인만으로 예외 지정을 대신하지 않는다).

**<접두사>_* 저장소 밖의 제외 대상:** `<공유문서 저장소>` 아래 파일(인계문서, 스크립트, 통합정리, 지시대기 기록 등)은 커밋 대상이 아니다. 이 폴더를 고친 뒤 커밋 여부를 점검 항목이나 남은 작업으로 올리지 않는다. 단 `<공유문서 루트>\{admin,buy,contract,member,sell}`는 각 `<접두사>_*\docs`로 연결된 junction이라 같은 물리 폴더이며, 그 하위 파일은 아래 `docs/` 항목(93행)을 따른다. 이 항목은 `<공유문서 저장소>` 직속(junction이 아닌 부분)에만 적용한다.

**<접두사>_* 프로젝트 안의 로컬 유지 파일:** 아래는 위 패턴 목록과 별개로 커밋하지 않고 로컬에 그대로 둔다(지우라는 뜻이 아니다).

- `docs/` 아래의 미추적(새로 생긴) 파일: `docs/api/`(API 명세 산출물), `docs/<팀구분>/<이름약자>/`(8단계 AR-01), `docs/menu-roadmap/`, 조사·시연용 `docs/*.md` 등. 이미 추적 중인 `docs/` 파일의 수정은 이 항목의 대상이 아니다.
- 위 패턴 목록의 `.playwright-mcp`(Playwright 임시 출력)와 `gradle.properties`.

**원격에서 바뀐 설정 파일(yaml·properties) 처리:** 위 목록의 설정 파일(`application*.yaml`, `configuration/*.yaml`, `gradle.properties` 등)을 로컬에서 수정해 둔 상태에서 fetch로 원격 변경이 들어오면, **원격 내용을 기본값**으로 한다. 로컬 수정은 통째로 이어 가지 않고, 로컬 서버 구동·구현·검증에 병목이 되는 옵션(예: `NPROTECT_ENABLED`·`ANYID_ENABLED` false, 포트·메모리)만 fetch 뒤에 원격 내용 위에 필요한 줄만 다시 적용한다.

- 원격 내용으로 덮기 전에 로컬 수정 diff를 확인한다. 위 옵션 외의 변경이 있으면 버리기 전에 보고한다.
- 조직 고유 보안 토글(예: NPROTECT·ANYID) false는 2단계 RL-12의 yaml 방식(커밋 제외 yaml에 직접 적용)만 쓴다. 그 밖의 보안 설정 변경은 이 규칙으로 허용되지 않는다.
- 다시 적용한 줄도 CS-09 대상이라 커밋하지 않는다.

```
*.png
.claude
.claudeignore
.gitattributes
.githooks
.github
.gitignore
.gradle
.idea
.mcp.json
.playwright-mcp
.vscode
AGENTS.md
CLAUDE.md
Dockerfile
README.md
bash.exe.stackdump
build.gradle
gradle
gradle.properties
gradlew
gradlew.bat
settings.gradle
specs
src/main/java/kr/<프로젝트 루트>/{도메인}/core
src/main/resources/*.sql
src/main/resources/*.xml
src/main/resources/*.yaml
src/main/resources/configuration
src/main/resources/static/assets
src/main/resources/static/docs
src/main/resources/static/js/bootstrap.bundle.min.js
src/main/resources/static/js/common
src/main/resources/static/js/commons
src/main/resources/static/js/core
src/main/resources/static/js/error
src/main/resources/static/js/guide
src/main/resources/static/js/pages
src/main/resources/static/js/third-party
src/main/resources/static/js/{도메인}/main.js
src/main/resources/static/js/{도메인}/sub.js
src/main/solution
tools
```

### CS-10 · 머지 커밋은 이 작업이 추가한 파일만 대상으로 한다 (사용자 확정 2026-10-25)

기준 브랜치(`<팀구분>/main` 등)를 머지해 들어오는 변경은 이 작업이 추가한 파일이 아니다. 머지 커밋에는 CS-01·CS-02를 아래처럼 적용한다.

- CS-01 계획과 CS-02 대조의 대상은 '이 작업이 추가한 파일', 즉 기준 브랜치(원격) 대비 diff에 나타나는 파일로 한정한다. 머지로 들어오는 기준 브랜치의 파일 수천 개를 계획에 나열하지 않는다.
- CS-09 추적 제외 목록과 CS-02 이상 신호 판정도 같은 범위(원격 기준 브랜치 대비 diff)에 적용한다.
- 머지 커밋의 메시지는 git 기본 머지 메시지를 허용한다(5단계 CM-04의 type(scope) 형식을 강제하지 않는다).
- 계획에는 '머지 커밋', 머지 대상 브랜치, 대조 기준(원격 기준 브랜치 대비 diff)을 명시한다. 승인자와 일시 기록(CS-01)과 커밋 직후 확인(CS-04)은 그대로다.

---

## 체크리스트

- [ ] CS-09 계획을 제시하기 전에 추적 제외 목록과 대조해 해당 파일을 걸러냈는가?
- [ ] CS-01 대상 브랜치명·파일 목록·메시지 초안을 제시하고 사람 또는 qa-master의 명시적 승인을 받았는가?
- [ ] CS-01 소스가 포함된 커밋이면 모든 소스 헤더에 `@programId`/`@processId`가 있고(못 찾은 항목은 `NA`) 근거를 계획에 제시했는가?
- [ ] CS-02 커밋 직전 `git diff --cached --stat`으로 승인 목록과 대조했는가?
- [ ] CS-03 변경이 섞인 상태에서 특정 파일만 커밋할 때 `git restore --staged .`로 먼저 비웠는가?
- [ ] CS-04 커밋 직후 `git show --stat HEAD`로 확인했는가?
- [ ] CS-05 복구·정정 커밋에도 같은 검증을 적용했는가?
- [ ] CS-06 되돌리기 어려운 명령을 사람 확인 없이 실행하지 않았는가?
- [ ] CS-07 stash에 `-u`를 pathspec 없이 쓰지 않았는가?
- [ ] CS-08 규칙과 관행의 차이를 계획 제시 때 먼저 알리고 확인받았는가?
- [ ] CS-09 (2차) 스테이징·커밋 목록에 제외 목록의 경로가 섞여 있지 않은가(사람이 지정한 예외 파일 제외)?
- [ ] CS-10 머지 커밋이면 계획·대조 대상을 원격 기준 브랜치 대비 diff의 파일로 한정하고, 계획에 '머지 커밋'·대상 브랜치·대조 기준을 명시했는가?

---

## 부록: 배경

- 이 문서는 contract 세션이 실제로 여러 차례 커밋 실수(승인받은 목록과 다른 파일을 커밋, 이전 staged 잔여물로 인한 실수 반복, 위험한 git 명령을 임의 판단으로 실행, 브랜치 관행 불일치를 사후에야 언급 등)를 저지른 뒤 자기반성으로 도출한 보완사항을 규칙으로 만든 것이다.
- 5단계의 "커밋 전 체크(변경사항/의도치 않은 파일/임시 코드 확인)"는 원칙만 있고 구체적 절차가 없었다. 이 문서가 그 절차를 정한다.
- CS-06은 되돌리기 어려운 명령에 대한 실행 신중성을 git 내부 파일·명령 수준까지 구체화한 것이다.
