# -*- coding: utf-8 -*-
# Copyright 2026 Baek Ga-hui (neisii) - https://github.com/neisii/harness-naroo
# SPDX-License-Identifier: Apache-2.0
"""reversibility_demo — "5분 입구" 1부: 가역성 분류표(07)를 예시 4~5개로 보여준다.

라우팅 구현은 스킬이 정본이다: skills/reversibility-gate/reversibility_gate.py.
이 데모는 그 `route()`를 그대로 불러 예시 상황에 돌린다 — 구현 1곳, 드리프트 없음.

  python3 examples/reversibility_demo.py

정본 설명: design-notes/07-가역성분류표.md. 표준 라이브러리만 쓴다.
"""
import importlib.util
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GATE = os.path.join(REPO_ROOT, "skills", "reversibility-gate", "reversibility_gate.py")

if not os.path.isfile(GATE):
    print("[오류] 라우터 구현을 찾지 못했습니다: %s" % GATE, file=sys.stderr)
    sys.exit(2)

_spec = importlib.util.spec_from_file_location("reversibility_gate", GATE)
_gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_gate)
route, OUTCOMES = _gate.route, _gate.OUTCOMES

# 예시 상황: A/B/C/D를 각각 하나씩, [3]은 '안전해 보이지만 거부권' 함정, [5]는 '롤백 없음→B가 C로'
CASES = [
    ("내 feature 브랜치에서 변수 오타 수정", "가역", "있음", "명확", "해당없음", "내구역"),
    ("공용 유틸에 디버그 로그 한 줄 추가", "가역", "있음", "명확", "해당없음", "외부공유"),
    ("할인율을 15%로 코드에 반영", "가역", "있음", "명확", "사업결정", "외부공유"),
    ("화면설계서에 '거기 그거 처리'로만 적힌 항목 구현", "가역", "있음", "모호", "해당없음", "외부공유"),
    ("공유 스테이징 DB에 샘플 데이터 일괄 삽입 (되돌리는 스크립트는 아직 없음)",
     "가역", "없음", "명확", "해당없음", "외부공유"),
]

_SCOPE_KO = {"내구역": "내 구역", "외부공유": "외부·공유"}


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print()
    print("가역성 분류표(07) — 혼자 할까 / 물어볼까를 기준 4개로 정한다.")
    print("=" * 64)
    for i, (title, rev, rb, clar, biz, scope) in enumerate(CASES, 1):
        code, why, _veto = route(rev, rb, clar, biz, scope)
        print()
        print("[%d] %s" % (i, title))
        print("    가역성=%s · 롤백=%s · 기반정보=%s · 영향범위=%s · 업무규칙=%s"
              % (rev, rb, clar, _SCOPE_KO[scope], biz))
        print("    → %s   %s" % (OUTCOMES[code], why))
    print()
    print("=" * 64)
    print("핵심은 [3]이다: 되돌릴 수 있고·명확하고·내 일처럼 보여도,")
    print("'할인율'은 사람이 정할 일이라 거부권이 걸려 멈춘다. 점수로 못 덮는다.")
    print("→ 개별 작업의 '성공'이 아니라, 그 결정이 전체를 안 깨뜨리는지를 본다.")
    print()
    print("판정 근거를 JSON으로 남기려면: skills/reversibility-gate/reversibility_gate.py --help")
    print()


if __name__ == "__main__":
    main()
