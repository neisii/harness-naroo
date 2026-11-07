# 9단계 · 공통코드

> **목적:** 화면에서 쓸 공통코드를 조사하고 사람의 검토를 받는 방법을 정한다.
> **언제 읽나:** 화면에 공통코드(셀렉트/라디오/체크박스 등에 쓰이는 그룹코드 + 코드값)가 필요할 때([00 요약](향상된_AI-DLC_00-핵심규칙요약.md) 2장).

---

## 규칙

### CC-01 · 4곳을 전부 조사한다

| # | 출처 | 위치·내용 | 쓰임 |
|---|---|---|---|
| 1 | TOBE 공통코드 DB | 시스템 공통코드 `sch_c.tbl_049`(그룹코드 예: `SYS001`~`SYS012`), 업무 공통코드 `sch_d.tbl_051`(그룹코드 예: `CD049`·`CD050`·`CD051`~`CD052`·`CD041`·`CD042`·`CD003` 등, 코드마다 참조문자값 `rfrnc_chvl_1`~`5` 보유 가능) | 현재 코드값 |
| 2 | developmentguide | `{본인 경로}\IdeaProjects\<접두사>_docs\developmentguide\11-화면에서-공통코드-연동하기.md` | 프론트 연동 방식(`CommonCode.load()`, `SelectComponent`/`RadioGroupComponent`/`CheckboxGroupComponent`, buy·sell BFF 중계 구조 등). 코드값보다 "어떻게 조회·바인딩하는가"의 표준 근거 |
| 3 | 구현참고자료(ASIS) | `{본인 경로}\IdeaProjects\구현참고자료\`(예: `1. 분석\PRJ_ASIS_공통코드_분석.md`) | TOBE DB에 아직 없는 코드의 유래·의미·과거 코드값 |
| 4 | js/java 하드코딩 | 화면 JS나 백엔드 Java에 상수·배열 등으로 임시 정의한 값 | DB에 정식 등록되지 않은 코드 |

TOBE DB 조회 방법:

- 공통코드 관리 화면, 위 테이블 직접 조회, 또는 범용 API `POST /api/admin/commoncode/searchByGroups`(프론트에서는 `CommonCode.load()`로 호출).
- **최신 정보 CSV(내부망 dev)도 항상 함께 확인한다:** `{본인 경로}\IdeaProjects\project_docs\docs\공통코드\공통코드_내부망_dev_*.csv`
  - 접두어별로 나뉘어 있다(`startwith_CT`, `startwith_EE`, `startwith_MA`, `startwith_DL`, `startwith_TC`, `not_startwith`). 한 파일에 없으면 `*` 전체를 검색한다.
  - 컬럼은 `group_cd, group_cd_nm, group_cd_expln, dtl_cd, dtl_cd_nm`이고 참조문자값(`rfrnc_chvl_1~5`)은 없다. 참조문자값이 필요하면 DB를 직접 조회한다.

> ASIS 참고: ASIS는 `TEMU100`(범용 공통코드)·`TTMU980`(입찰 전용 코드) 2개 테이블을 쓰며, 많은 코드가 테이블에 등록되지 않고 애플리케이션에 하드코딩돼 있다는 문제가 이미 분석돼 있다.

### CC-02 · 하나를 찾아도 나머지를 생략하지 않는다

TOBE DB에 이미 있어 보여도 나머지 3곳까지 확인한다.

> 이유: 출처마다 값이 다르거나 상충할 수 있다.

### CC-03 · 발견한 후보를 모두 제시한다

AI가 임의로 하나만 골라 제시하지 않는다.

### CC-04 · 사람(또는 qa-master)이 결정한다 **[사람 확인]**

- 공통코드는 AI가 임의로 골라 구현하지 않는다. 결정자는 사람이거나 2단계 RL-12 위임에 따른 qa-master다.
- 3단계 RQ-05 선택지 형식(가능하면 `AskUserQuestion`)으로 제시한다.
- 선택지마다 다음을 넣는다.
  - **출처:** TOBE DB / developmentguide / 구현참고자료(ASIS) / js·java 하드코딩 중 어디인지
  - **상세 정보:** 그룹코드, 코드값, 코드명, 참조문자값 등 조회된 그대로
  - **사용 위치:** 필요한 화면ID와 화면 내 영역(예: 어느 화면의 "검수상태" 셀렉트인지)

### CC-05 · 못 찾으면 새로 만들지 않는다

4곳 어디에서도 후보를 찾지 못하면 "찾지 못했다"는 사실과 4곳 각각의 확인 결과를 제시하고 기획 확인을 받는다(기획 확인은 2단계 RL-12 위임에 따라 qa-master가 할 수 있다). 임의로 새 코드값을 만들지 않는다.

---

## 참고: 화면 JS 파일 찾기

화면 JS 파일은 대부분 대응 HTML 파일명을 그대로 따른다(예: `templates/admin/sample/commonLoad.html` ↔ `static/js/admin/sample/commonLoad.js`). 공통코드를 어느 화면 JS에서 쓰는지 조사할 때 같은 이름의 JS 파일을 먼저 확인한다.

---

## 체크리스트

- [ ] CC-01 4곳(TOBE DB, developmentguide, 구현참고자료, js·java 하드코딩)을 전부 조사했는가?
- [ ] CC-01 TOBE DB를 조사할 때 `공통코드_내부망_dev_*.csv`도 함께 확인했는가?
- [ ] CC-02 하나에서 후보를 찾았다고 나머지를 생략하지 않았는가?
- [ ] CC-03 발견한 후보를 빠짐없이 제시했는가?
- [ ] CC-04 각 선택지에 출처·상세 정보·사용 위치가 있고, RQ-05 형식을 따랐는가?
- [ ] CC-05 후보가 없을 때 4곳 결과를 제시하고 기획 확인을 받았는가(새 코드값을 만들지 않았는가)?
