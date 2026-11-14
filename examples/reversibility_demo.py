#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""reversibility_demo — "5분 입구" 1부: 가역성 분류표(07)의 실행 가능한 한 조각.

AI가 "이 일을 혼자 해도 되나, 멈추고 사람한테 물어봐야 하나"를 기준 4개로 판정한다.
예시 상황 4개를 돌려 A/B/C/D 결정과 이유를 보여준다.

  python3 examples/reversibility_demo.py

이것은 규칙 07의 **실행 가능한 한 조각**이지 하네스 전체의 5분 요약이 아니다.
정본 설명: design-notes/07-가역성분류표.md
전체 라우터(확신도·"주의 2개 이상" 집계·판정 근거 장부 기록)는 아직 뒤로 미뤄져 있다 —
이 데모는 STEP1 거부권 + STEP2 ③ 조절의 뼈대만 결정론적으로 보여준다. 표준 라이브러리만 쓴다.
"""

# 결과 4가지
A, B, C, D = (
    "A 자율 실행",
    "B 사후 검수 + 알림",
    "C 사전 승인",
    "D 보류·질의",
)


def route(reversible, rollback, clarity, business, scope):
    """기준 4개 → 결과 1개 + 이유. 점수 합산이 아니라 거부권 먼저(STEP1), 그다음 ③ 조절(STEP2)."""
    # STEP 1 — 거부권: 하나라도 걸리면 거기서 끝 (점수로 못 덮는다)
    if clarity == "모호":
        return D, "② 뭘 하란 건지 모른다 (거부권) — 옆으로 치우고 다음 일부터."
    if business == "사업결정":
        return C, "④ '사람이 정할' 사업 결정 (거부권) — 되돌릴 수 있어도 혼자 못 정한다."
    if reversible == "비가역":
        return C, "① 되돌릴 수 없다 (거부권) — '하고 나서 말하기'는 너무 위험."
    # STEP 2 — ③ 영향범위로 조절
    if scope == "내구역":
        return A, "되돌릴 수 있고, 확실하고, 내 구역. 혼자 한다."
    # 외부·공유: B로 가려면 되돌릴 방법이 실제로 등록돼 있어야 한다
    if rollback == "없음":
        return C, "외부·공유인데 되돌릴 방법이 없다 → 보수적으로 멈추고 물어본다."
    return B, "외부·공유지만 되돌릴 수 있고 명확 → 하고 나서 알린다."


# 예시 상황 4개 (A/B/C/D를 각각 하나씩, 그리고 [3]은 '안전해 보이지만 거부권' 함정)
CASES = [
    {
        "title": "내 feature 브랜치에서 변수 오타 수정",
        "reversible": "가역", "rollback": "있음", "clarity": "명확",
        "business": "해당없음", "scope": "내구역",
    },
    {
        "title": "공용 유틸에 디버그 로그 한 줄 추가",
        "reversible": "가역", "rollback": "있음", "clarity": "명확",
        "business": "해당없음", "scope": "외부공유",
    },
    {
        "title": "할인율을 15%로 코드에 반영",
        "reversible": "가역", "rollback": "있음", "clarity": "명확",
        "business": "사업결정", "scope": "외부공유",
    },
    {
        "title": "화면설계서에 '거기 그거 처리'로만 적힌 항목 구현",
        "reversible": "가역", "rollback": "있음", "clarity": "모호",
        "business": "해당없음", "scope": "외부공유",
    },
]

_SCOPE_KO = {"내구역": "내 구역", "외부공유": "외부·공유"}


def main():
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print()
    print("가역성 분류표(07) — 혼자 할까 / 물어볼까를 기준 4개로 정한다.")
    print("=" * 64)
    for i, c in enumerate(CASES, 1):
        result, why = route(c["reversible"], c["rollback"], c["clarity"],
                            c["business"], c["scope"])
        print()
        print("[%d] %s" % (i, c["title"]))
        print("    가역성=%s · 기반정보=%s · 영향범위=%s · 업무규칙=%s"
              % (c["reversible"], c["clarity"], _SCOPE_KO[c["scope"]], c["business"]))
        print("    → %s   %s" % (result, why))
    print()
    print("=" * 64)
    print("핵심은 [3]이다: 되돌릴 수 있고·명확하고·내 일처럼 보여도,")
    print("'할인율'은 사람이 정할 일이라 거부권이 걸려 멈춘다. 점수로 못 덮는다.")
    print("→ 개별 작업의 '성공'이 아니라, 그 결정이 전체를 안 깨뜨리는지를 본다.")
    print()


if __name__ == "__main__":
    main()
