"""gate3 관측용: 세션 대화 기록(jsonl)에서 걸린 시간과 토큰 사용량을 모은다. 읽기 전용.

사용: python3 usage.py [관측 세션 jsonl 경로]
- 시험 세션: ~/.claude/projects/-Users-neisii-Development-gate3-gate3-trial/ 아래 전부(서브에이전트 포함)
- 관측 세션(선택): 인자로 준 파일. 시험 착수(START) 이후 줄만 센다.
"""
import json, sys, glob, os, datetime as dt

TRIAL = os.path.expanduser("~/.claude/projects/-Users-neisii-Development-gate3-gate3-trial")
START = dt.datetime(2026, 11, 21, 17, 41).astimezone()  # 착수 승인 시각(로컬)
KEYS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")


def ts(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone()


def scan(path, since=None):
    seen, tot, first, last, model = set(), dict.fromkeys(KEYS, 0), None, None, set()
    for line in open(path, encoding="utf-8"):
        try:
            e = json.loads(line)
        except Exception:
            continue
        t = e.get("timestamp")
        if not t:
            continue
        t = ts(t)
        if since and t < since:
            continue
        first = first or t
        last = t
        m = e.get("message") or {}
        u = m.get("usage") if isinstance(m, dict) else None
        if e.get("type") != "assistant" or not u:
            continue
        mid = m.get("id") or e.get("uuid")
        if mid in seen:  # 스트리밍으로 같은 메시지가 여러 줄에 나뉘어 기록됨
            continue
        seen.add(mid)
        model.add(m.get("model", "?"))
        for k in KEYS:
            tot[k] += u.get(k, 0) or 0
    return tot, first, last, model, len(seen)


def show(label, tot, first, last, model, n):
    span = (last - first) if first and last else dt.timedelta(0)
    fresh = tot["input_tokens"] + tot["cache_creation_input_tokens"]
    print(f"{label}\n  기간 {first:%H:%M} ~ {last:%H:%M} ({int(span.total_seconds()//60)}분), 응답 {n}개, 모델 {','.join(sorted(model))}")
    print(f"  입력(새로) {fresh:,} · 입력(캐시 읽기) {tot['cache_read_input_tokens']:,} · 출력 {tot['output_tokens']:,}")
    return tot


grand = dict.fromkeys(KEYS, 0)
firsts, lasts = [], []
for p in sorted(glob.glob(f"{TRIAL}/**/*.jsonl", recursive=True)):
    name = os.path.relpath(p, TRIAL)
    r = scan(p)
    if not r[1]:
        continue
    show(name, *r)
    firsts.append(r[1]); lasts.append(r[2])
    for k in KEYS:
        grand[k] += r[0][k]

print("\n== 시험 세션 합계 (게이트웨이·실무자·서브에이전트)")
fresh = grand["input_tokens"] + grand["cache_creation_input_tokens"]
print(f"  입력(새로) {fresh:,} · 입력(캐시 읽기) {grand['cache_read_input_tokens']:,} · 출력 {grand['output_tokens']:,}")
now = dt.datetime.now().astimezone()
print(f"  착수 승인 {START:%H:%M} 부터 지금 {now:%H:%M} 까지 {int((now-START).total_seconds()//60)}분")

if len(sys.argv) > 1:
    r = scan(sys.argv[1], since=START)
    print()
    show("== 관측 세션(착수 이후)", *r)
