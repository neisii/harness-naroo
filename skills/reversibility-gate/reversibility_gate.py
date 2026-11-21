# -*- coding: utf-8 -*-
# Copyright 2026 Baek Ga-hui (neisii) - https://github.com/neisii/harness-naroo
# SPDX-License-Identifier: Apache-2.0
"""reversibility_gate — 가역성 분류표(07)의 실행 가능한 라우터 + 판정 근거 기록.

AI가 결정 지점에서 기준 4개를 self-assess하면 A/B/C/D로 길을 정하고,
사후 감사용 **판정 근거**를 AG-15 호환 JSON으로 남긴다.

  # 사람이 읽는 판정
  python3 reversibility_gate.py --task "할인율 15% 반영" \
      --reversibility 가역 --rollback 있음 --clarity 명확 --business 사업결정 --scope 외부공유

  # 판정 근거 JSON (장부에 넣거나 파일로 남김)
  python3 reversibility_gate.py --task "..." --reversibility ... --rollback ... --json \
      --session 세션명 --why-business "할인율은 기획이 정할 사업 규칙"

정본 규칙: design-notes/07-가역성분류표.md. 표준 라이브러리만 쓴다.
라우팅: STEP1 거부권(점수 합산 금지) → STEP2 ③ 영향범위 조절. 확신도 '낮음'이면 한 단계 보수적(규칙 4).
"""
import argparse
import datetime
import json
import sys

OUTCOMES = {
    "A": "A 자율 실행",
    "B": "B 사후 검수 + 알림",
    "C": "C 사전 승인",
    "D": "D 보류·질의",
}

# 확신도 '낮음'일 때 한 단계 보수적으로 (A→B→C, D는 그대로)
_MORE_CONSERVATIVE = {"A": "B", "B": "C", "C": "C", "D": "D"}

REVERSIBILITY = ("가역", "비가역")
ROLLBACK = ("있음", "없음")
CLARITY = ("명확", "모호")
BUSINESS = ("해당없음", "사업결정")
SCOPE = ("내구역", "외부공유")
CONFIDENCE = ("높음", "보통", "낮음")


def route(reversibility, rollback, clarity, business, scope):
    """기준 4개 → (결과코드, 이유, 거부권). 점수 합산이 아니라 거부권 먼저, 그다음 ③ 조절."""
    # STEP 1 — 거부권: 하나라도 걸리면 거기서 끝
    if clarity == "모호":
        return "D", "② 뭘 하란 건지 모른다 (거부권) — 옆으로 치우고 다음 일부터.", "②"
    if business == "사업결정":
        return "C", "④ '사람이 정할' 사업 결정 (거부권) — 되돌릴 수 있어도 혼자 못 정한다.", "④"
    if reversibility == "비가역":
        return "C", "① 되돌릴 수 없다 (거부권) — '하고 나서 말하기'는 너무 위험.", "①"
    # STEP 2 — ③ 영향범위로 조절
    if scope == "내구역":
        return "A", "되돌릴 수 있고, 확실하고, 내 구역. 혼자 한다.", "없음"
    if rollback == "없음":
        return "C", "외부·공유인데 되돌릴 방법이 없다 → 보수적으로 멈추고 물어본다.", "없음"
    return "B", "외부·공유지만 되돌릴 수 있고 명확 → 하고 나서 알린다.", "없음"


def decide(reversibility, rollback, clarity, business, scope, confidence="보통"):
    """route + 확신도 보수 조정. (결과코드, 이유, 거부권, 보수조정여부)."""
    code, why, veto = route(reversibility, rollback, clarity, business, scope)
    bumped = False
    if confidence == "낮음":
        new = _MORE_CONSERVATIVE[code]
        if new != code:
            code, bumped = new, True
            why = why + " (확신도 낮음 → 한 단계 보수적으로)"
    return code, why, veto, bumped


def build_record(task, reversibility, rollback, clarity, business, scope,
                 code, why, veto, confidence, bumped, rationales, session, now=None):
    now = now or datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    return {
        "종류": "가역성판정",
        "작업": task,
        "결과": code,
        "판정시각": now,
        "세션": session,
        "기준": {
            "가역성": {"값": reversibility, "롤백경로": rollback, "근거": rationales.get("가역성", "")},
            "기반정보": {"값": clarity, "근거": rationales.get("기반정보", "")},
            "영향범위": {"값": scope, "판정방식": "자가", "근거": rationales.get("영향범위", "")},
            "업무규칙": {"값": business, "근거": rationales.get("업무규칙", "")},
        },
        "확신도": confidence,
        "거부권발동": veto,
        "보수조정": bumped,
        "결정근거": why,
    }


def selftest():
    """07 데모 5개 케이스가 기대대로 라우팅되는지 (구현 정본 보증)."""
    cases = [
        (("가역", "있음", "명확", "해당없음", "내구역"), "A"),
        (("가역", "있음", "명확", "해당없음", "외부공유"), "B"),
        (("가역", "있음", "명확", "사업결정", "외부공유"), "C"),
        (("가역", "있음", "모호", "해당없음", "외부공유"), "D"),
        (("가역", "없음", "명확", "해당없음", "외부공유"), "C"),
        # 내 구역은 워크트리·git이 되돌리는 수단이라 롤백 등록을 따로 묻지 않는다(의도한 동작, 2026-11-21)
        (("가역", "없음", "명확", "해당없음", "내구역"), "A"),
    ]
    for args, expect in cases:
        got = route(*args)[0]
        assert got == expect, "라우팅 불일치: %s → %s (기대 %s)" % (args, got, expect)
    # 확신도 보수 조정
    assert decide("가역", "있음", "명확", "해당없음", "내구역", "낮음")[0] == "B", "보수 조정 실패"
    print("selftest OK")


def main(argv):
    ap = argparse.ArgumentParser(description="가역성 판정 라우터(07) + 판정 근거 기록")
    ap.add_argument("--task", help="무슨 일인지 한 줄")
    ap.add_argument("--reversibility", choices=REVERSIBILITY)
    ap.add_argument("--rollback", choices=ROLLBACK)
    ap.add_argument("--clarity", choices=CLARITY)
    ap.add_argument("--business", choices=BUSINESS)
    ap.add_argument("--scope", choices=SCOPE)
    ap.add_argument("--confidence", choices=CONFIDENCE, default="보통")
    ap.add_argument("--session", default="unknown")
    ap.add_argument("--why-reversibility", default="", dest="why_reversibility")
    ap.add_argument("--why-clarity", default="", dest="why_clarity")
    ap.add_argument("--why-scope", default="", dest="why_scope")
    ap.add_argument("--why-business", default="", dest="why_business")
    ap.add_argument("--json", action="store_true", help="판정 근거 JSON 출력")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except Exception:
            pass

    if a.selftest:
        selftest()
        return 0

    missing = [n for n in ("task", "reversibility", "rollback", "clarity", "business", "scope")
               if getattr(a, n) is None]
    if missing:
        print("[오류] 필수 인자 누락: %s (--selftest로 자기 점검 가능)"
              % ", ".join("--" + m for m in missing), file=sys.stderr)
        return 2

    code, why, veto, bumped = decide(a.reversibility, a.rollback, a.clarity,
                                     a.business, a.scope, a.confidence)
    if a.json:
        rationales = {
            "가역성": a.why_reversibility, "기반정보": a.why_clarity,
            "영향범위": a.why_scope, "업무규칙": a.why_business,
        }
        rec = build_record(a.task, a.reversibility, a.rollback, a.clarity, a.business,
                           a.scope, code, why, veto, a.confidence, bumped, rationales, a.session)
        print(json.dumps(rec, ensure_ascii=False, indent=2))
        if not any(rationales.values()):
            print("경고: 판정 근거(--why-*)가 비었다 — 사후 감사 가치가 낮다.", file=sys.stderr)
    else:
        print("작업: %s" % a.task)
        print("  가역성=%s · 기반정보=%s · 영향범위=%s · 업무규칙=%s · 확신도=%s"
              % (a.reversibility, a.clarity, a.scope, a.business, a.confidence))
        print("  → %s   %s" % (OUTCOMES[code], why))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
