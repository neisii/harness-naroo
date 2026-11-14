#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""seosul_lint — 서술 규칙 위반을 찾는 읽기 전용 린터(한국어 글쓰기용).

번역투·과장 용어, 이모지, 2인칭('당신')을 Markdown에서 찾아 보고한다.
무엇을 "번역투"로 볼지는 사전 파일(기본: 이 스크립트 옆의 '번역투-교정사전.md')이 정한다.
사전만 바꾸면 다른 팀의 금칙어·대치어에도 그대로 쓸 수 있다.

사용법:
  python3 seosul_lint.py [경로 ...] [--json] [--strict] [--dict 사전.md] [--skip a.md,b.md] [--selftest]

- 경로: 파일 또는 폴더(폴더는 하위까지 *.md). 생략하면 현재 폴더 최상위의 *.md.
- 사전 파일 자체는 언제나 스캔에서 제외한다. --skip 으로 더 제외할 수 있다(파일명, 쉼표 구분).
- 탐지 범주: (a) 번역투/과장 용어 (b) 이모지 (c) 시점 드리프트(2인칭 '당신')
- 종료 코드: 기본 0(보고만). --strict 이면 발견 시 1. 파일은 읽기만 한다. 표준 라이브러리만 사용.

용어 사전: 사전 파일의 '## 사전' 아래 표(`| N | **용어** (설명) | 대안 | 메모 |`)에서
2번째 셀의 첫 **볼드**를 꺼내 괄호 설명을 지우고 '/'·'·' 로 쪼갠 것이 검색어, 3번째 셀이 대안이다.

매칭 규칙(오탐 줄이기):
- 2글자 이상 명사형 검색어: 글자열이 그대로 들어 있으면 잡는다(예: '재조립' 의 '조립').
- 1글자 명사형 검색어(예: '축'): 앞이 한글/영숫자가 아니고, 뒤가 한글이 아니거나 조사(을·는·으로…)일 때만
  잡는다('축소'·'구축'·'수축' 은 안 잡는다).
- '~다' 로 끝나는 동사형 검색어(예: '박다'): 어간(박) 에 활용 어미(다·는·아·았·은·고…)가 붙은 꼴을 잡는다
  (박는다·박았다·못박아·박아넣는다). 어간이 1글자면 앞 경계도 요구해 '박스'·'박물관' 은 안 잡는다.
"""
import argparse
import json
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DICT = os.path.join(SCRIPT_DIR, '번역투-교정사전.md')
EXCLUDE_DIRS = {'.git', 'node_modules', '.svn', '.hg'}

CAT_TERM, CAT_EMOJI, CAT_POV = '번역투', '이모지', '시점'

HANGUL = '가-힣'
PARTICLES = r'(?:으로|에서|에게|까지|부터|마다|처럼|보다|조차|이라|라는|이란|은|는|을|를|이|가|의|에|도|만|과|와|로|나|란)'
VERB_ENDINGS = r'(?:다|는|아|어|았|었|은|을|고|지|며|면|게|기|음|으|히|혀)'
SECOND_PERSON = re.compile(r'(?<![%s])당신' % HANGUL)


# ------------------------------------------------------------------ 사전 파싱
def parse_dictionary(path):
    """사전 표를 읽어 [{'terms': [...], 'suggestion': str, 'row': int}] 를 돌려준다."""
    with open(path, encoding='utf-8') as f:
        lines = f.read().split('\n')
    start = None
    for i, line in enumerate(lines):
        if line.startswith('## 사전'):
            start = i + 1
            break
    if start is None:
        raise ValueError('"## 사전" 헤딩을 찾지 못했습니다: ' + path)
    entries = []
    in_table = False
    for line in lines[start:]:
        s = line.strip()
        if s.startswith('## '):
            break
        if not s.startswith('|'):
            if in_table:
                break
            continue
        in_table = True
        cells = [c.strip() for c in s.strip('|').split('|')]
        if len(cells) < 3 or not cells[0].isdigit():
            continue  # 헤더·구분선
        m = re.search(r'\*\*(.+?)\*\*', cells[1])
        if not m:
            continue
        raw = re.sub(r'[\(（][^\)）]*[\)）]', '', m.group(1))  # 괄호 설명 제거 먼저
        terms = [t.strip() for t in re.split(r'[/·]', raw) if t.strip()]
        suggestion = cells[2].replace('**', '').strip()
        if terms:
            entries.append({'terms': terms, 'suggestion': suggestion, 'row': int(cells[0])})
    return entries


def build_matchers(entries):
    """(정규식, 검색어, 대안) 목록."""
    out = []
    for e in entries:
        for t in e['terms']:
            esc = re.escape(t)
            if len(t) >= 2 and t.endswith('다'):
                stem = re.escape(t[:-1])
                if len(t) - 1 == 1:  # 어간 1글자: 앞 경계 + 활용 어미
                    pat = r'(?<![%s0-9A-Za-z])%s%s' % (HANGUL, stem, VERB_ENDINGS)
                else:
                    pat = stem
            elif len(t) == 1:
                pat = r'(?<![%s0-9A-Za-z])%s(?:(?![%s])|%s)' % (HANGUL, esc, HANGUL, PARTICLES)
            else:
                pat = esc
            out.append((re.compile(pat), t, e['suggestion']))
    return out


# ------------------------------------------------------------------ 이모지
_EMOJI_RANGES = [
    (0x1F300, 0x1FAFF), (0x1F1E6, 0x1F1FF), (0x1F004, 0x1F004), (0x1F0CF, 0x1F0CF),
    (0x2614, 0x2615), (0x2648, 0x2653), (0x267F, 0x267F), (0x2693, 0x2693), (0x26A1, 0x26A1),
    (0x26AA, 0x26AB), (0x26BD, 0x26BE), (0x26C4, 0x26C5), (0x26CE, 0x26CE), (0x26D4, 0x26D4),
    (0x26EA, 0x26EA), (0x26F2, 0x26F3), (0x26F5, 0x26F5), (0x26FA, 0x26FA), (0x26FD, 0x26FD),
    (0x2705, 0x2705), (0x270A, 0x270B), (0x2728, 0x2728), (0x274C, 0x274C), (0x274E, 0x274E),
    (0x2753, 0x2755), (0x2757, 0x2757), (0x2795, 0x2797), (0x27B0, 0x27B0), (0x27BF, 0x27BF),
    (0x2B1B, 0x2B1C), (0x2B50, 0x2B50), (0x2B55, 0x2B55), (0x231A, 0x231B), (0x23E9, 0x23EC),
    (0x23F0, 0x23F0), (0x23F3, 0x23F3),
    (0x26A0, 0x26A0), (0x2764, 0x2764),  # ⚠ ❤ : 기본은 텍스트형이지만 실사용은 이모지
]
_VS16, _KEYCAP, _ZWJ = 0xFE0F, 0x20E3, 0x200D


def _is_emoji_char(ch):
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in _EMOJI_RANGES)


def find_emoji(line):
    """이모지 덩어리(연속된 이모지 + ZWJ/VS16/keycap)의 (시작 인덱스, 문자열) 목록.
    ✓ ✗ → ← ↔ · 같은 텍스트 기호는 이모지 범위에 없으므로 잡히지 않는다(VS16 이 붙은 경우만 예외)."""
    res = []
    i, n = 0, len(line)
    while i < n:
        ch = line[i]
        nxt = ord(line[i + 1]) if i + 1 < n else 0
        if _is_emoji_char(ch) or nxt == _VS16 or nxt == _KEYCAP:
            j = i + 1
            while j < n and (_is_emoji_char(line[j]) or ord(line[j]) in (_VS16, _KEYCAP, _ZWJ)):
                j += 1
            res.append((i, line[i:j]))
            i = j
        else:
            i += 1
    return res


# ------------------------------------------------------------------ 탐지
def scan_line(line, matchers):
    """한 줄의 위반 [(col0, 범주, 매치, 용어, 대안)] (같은 위치·범주 중복 제거)."""
    hits, seen = [], set()
    for rx, term, sugg in matchers:
        for m in rx.finditer(line):
            key = (m.start(), CAT_TERM, term)
            if key in seen:
                continue
            seen.add(key)
            hits.append((m.start(), CAT_TERM, m.group(0), term, sugg))
    for pos, s in find_emoji(line):
        hits.append((pos, CAT_EMOJI, s, None, None))
    for m in SECOND_PERSON.finditer(line):
        hits.append((m.start(), CAT_POV, m.group(0), None, None))
    hits.sort(key=lambda h: h[0])
    return hits


def scan_file(path, matchers):
    findings = []
    with open(path, encoding='utf-8') as f:
        for lineno, line in enumerate(f, 1):
            line = line.rstrip('\n')
            for col0, cat, match, term, sugg in scan_line(line, matchers):
                findings.append({'file': path, 'line': lineno, 'col': col0 + 1, 'category': cat,
                                 'match': match, 'term': term, 'suggestion': sugg})
    return findings


def collect_files(paths, skip_names):
    files = []
    for p in paths:
        if os.path.isdir(p):
            for root, dirs, names in os.walk(p):
                dirs[:] = sorted(d for d in dirs if d not in EXCLUDE_DIRS)
                for n in sorted(names):
                    if n.lower().endswith('.md'):
                        files.append(os.path.join(root, n))
        elif os.path.isfile(p):
            files.append(p)
        else:
            print('경고: 경로를 찾을 수 없음: %s' % p, file=sys.stderr)
    return [f for f in files if os.path.basename(f) not in skip_names]


def default_paths():
    return sorted(os.path.join('.', n) for n in os.listdir('.')
                  if n.lower().endswith('.md') and os.path.isfile(n))


# ------------------------------------------------------------------ 자기 테스트
def selftest(matchers):
    def cats(s):
        return {h[1] for h in scan_line(s, matchers)}
    assert CAT_TERM in cats('축을 기준으로'), '(a) 번역투 미탐지'
    assert CAT_POV in cats('이건 당신 거'), '(c) 시점 미탐지'
    assert CAT_EMOJI in cats('좋아요😀'), '(b) 이모지 미탐지'
    # 오탐 방지
    assert not cats('✓ ✗ → ← ↔ · 가능'), '텍스트 기호 오탐'
    for ok in ('축소', '구축', '수축 현상', '박스', '박물관', '부당신고'):
        assert not cats(ok), '오탐: ' + ok
    for bad in ('못박는다', '규칙으로 박는다', '박았다', '박아넣는다', '재조립', '하네스 지배', '축은'):
        assert CAT_TERM in cats(bad), '미탐지: ' + bad
    assert CAT_EMOJI in cats('경고 ⚠️'), 'VS16 이모지 미탐지'
    print('selftest OK')


def main(argv):
    ap = argparse.ArgumentParser(description='서술 규칙 린터(읽기 전용)')
    ap.add_argument('paths', nargs='*', help='파일/폴더(생략하면 현재 폴더 최상위 *.md)')
    ap.add_argument('--json', action='store_true', help='구조화 JSON 출력')
    ap.add_argument('--strict', action='store_true', help='위반이 있으면 종료 코드 1')
    ap.add_argument('--dict', default=DEFAULT_DICT, help='번역투 사전 경로(기본: 스크립트 옆 번역투-교정사전.md)')
    ap.add_argument('--skip', default='', help='추가로 제외할 파일명(쉼표 구분)')
    ap.add_argument('--selftest', action='store_true', help='샘플로 자기 점검')
    a = ap.parse_args(argv)
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding='utf-8')
        except Exception:
            pass

    try:
        matchers = build_matchers(parse_dictionary(a.dict))
    except Exception as e:
        print('[오류] 사전을 읽지 못했습니다: %s' % e, file=sys.stderr)
        return 2
    if a.selftest:
        selftest(matchers)
        return 0

    skip_names = {os.path.basename(a.dict)}
    skip_names.update(n.strip() for n in a.skip.split(',') if n.strip())

    files = collect_files(a.paths or default_paths(), skip_names)
    findings = []
    for f in files:
        findings.extend(scan_file(f, matchers))
    for x in findings:
        x['file'] = os.path.relpath(x['file'])

    if a.json:
        by_cat = {}
        for x in findings:
            by_cat[x['category']] = by_cat.get(x['category'], 0) + 1
        print(json.dumps({'total': len(findings), 'by_category': by_cat, 'files_scanned': len(files),
                          'findings': findings}, ensure_ascii=False, indent=2))
    else:
        for x in findings:
            tail = ' → %s' % x['suggestion'] if x['suggestion'] else ''
            print('%s:%d [%s] "%s"%s' % (x['file'], x['line'], x['category'], x['match'], tail))
        print('총 %d건 (파일 %d개 검사)' % (len(findings), len(files)))
    return 1 if (a.strict and findings) else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
