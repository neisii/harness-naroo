# -*- coding: utf-8 -*-
"""pending-status-check — AG-15 대기 장부(*.json) 전체를 읽기 전용으로 집계해 텍스트(기본) 또는 --json 으로 출력한다.

사용법:
  python3 pending_status_check.py [--ledger-dir DIR] [--json] [--now "YYYY-MM-DD HH:MM[:SS]"]

장부 폴더 우선순위: --ledger-dir > 환경변수 AIDLC_LEDGER_DIR > QA_INBOX_LEDGER_DIR > ~/.claude/qa-inbox/ledger
쓰기 없음(읽기 전용). 종료 코드는 항상 0이다(폴더 없음·읽기 문제도 출력으로만 알린다).
표준 라이브러리만 사용한다.
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime

DATE_RE = re.compile(r'^\s*(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}(:\d{2})?)')
STRICT_RE = re.compile(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$')
PRECHECK_PREFIX_LEN = 20
HEAVY_NOACK_MIN = 10
ARTIFACT_EXT = r'(?:md|html|csv|txt|sql|json|xlsx|png)'
# 요지에 적힌 절대경로 토큰: Windows 드라이브 경로, POSIX 절대경로, ~/ 경로 (URL 조각은 제외)
ARTIFACT_RE = re.compile(
    r'(?:(?<![A-Za-z0-9])[A-Za-z]:[\\/]|(?<![\w.:/~\\-])~?/)[^\s"\'`<>|*?()\[\]]+\.' + ARTIFACT_EXT + r'(?![\w])')

_NOW = None


def now():
    return _NOW or datetime.now()


# ------------------------------------------------------------------ 파싱 헬퍼
def get_field(obj, ko, en=None):
    """한글 키 우선, 없으면 영문 키 폴백. (값, 영문폴백여부)를 돌려준다. 빈 값/None 은 없는 것으로 본다."""
    if not isinstance(obj, dict):
        return None, False
    v = obj.get(ko)
    if v is not None and v != '':
        return v, False
    if en:
        v = obj.get(en)
        if v is not None and v != '':
            return v, True
    return None, False


def item_text(obj, ko, en=None):
    v = get_field(obj, ko, en)[0]
    return '' if v is None else str(v)


def parse_ledger_date(raw):
    if raw is None or not str(raw).strip():
        return None
    m = DATE_RE.match(str(raw))
    if not m:
        return None
    cand = '%s %s' % (m.group(1), m.group(2))
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'):
        try:
            return datetime.strptime(cand, fmt)
        except ValueError:
            pass
    return None


def strict_format(raw):
    """AG-15: 시각은 정확히 'YYYY-MM-DD HH:MM'. 비어 있으면 위반이 아니다(선택 필드일 수 있음)."""
    if raw is None or not str(raw).strip():
        return True
    return bool(STRICT_RE.match(str(raw)))


def severity_label(ratio):
    if ratio < 1.0:
        return '정상'
    if ratio < 1.5:
        return '1T 초과'
    if ratio < 2.0:
        return '1.5T 초과'
    if ratio < 3.0:
        return '2T 초과'
    return '3T 초과(심각)'


def load_json_file(path):
    with open(path, encoding='utf-8-sig') as f:
        return json.load(f)


# ------------------------------------------------------------------ 3T 사전확인
# AG-15 순찰 3T 판정 순서: ① 요청자 장부 재조회(이미 닫힘=요청자처리됨) ② 같은 수신자·같은 요지 접두의 더 늦은 open(=재요청됨)
# ③ 수신자 회신 흔적(수신자 장부의 요청자 앞 항목, 또는 요지에 적힌 절대경로 파일이 보낸시각 이후 수정=회신추정)
# ④ 확인 불가/흔적 없음은 기존 3T 에스컬레이션 유지(fail-open). 읽기 전용, 세션 활동 여부는 증거로 쓰지 않는다.
def new_precheck(verdict, reason):
    return {'판정': verdict, '근거': reason, '확인시각': now().strftime('%Y-%m-%d %H:%M')}


def read_ledger_items(ledger_dir, session):
    # 세션명이 경로 구분자를 포함하면(장부 내용에서 온 값) 폴더 밖을 읽지 않도록 거부한다.
    if not session or session != os.path.basename(session) or session in ('.', '..'):
        return False, [], '장부 파일 없음: %s.json' % session
    path = os.path.join(ledger_dir, session + '.json')
    if not os.path.isfile(path):
        return False, [], '장부 파일 없음: %s.json' % session
    try:
        root = load_json_file(path)
        items = get_field(root, '항목', 'items')[0]
        if items is None:
            return False, [], '항목 목록 없음: %s.json' % session
        return True, list(items) if isinstance(items, list) else [items], ''
    except Exception as e:
        return False, [], '읽기 실패 %s.json: %s' % (session, e)


def summary_prefix_match(a, b):
    a1, b1 = a.strip(), b.strip()
    if not a1 or not b1:
        return False
    n = min(PRECHECK_PREFIX_LEN, len(a1), len(b1))
    return a1[:n] == b1[:n]


def artifact_paths(summary):
    found = []
    for m in ARTIFACT_RE.finditer(summary or ''):
        p = os.path.expanduser(m.group(0)) if m.group(0).startswith('~') else m.group(0)
        if p not in found:
            found.append(p)
    return found


def precheck_3t(ledger_dir, row):
    try:
        sent_at = parse_ledger_date(row['보낸시각'])
        if not sent_at:
            return new_precheck('확인불가', '보낸시각 파싱 실패')

        ok, items, err = read_ledger_items(ledger_dir, row['세션'])
        if not ok:
            return new_precheck('확인불가', err)
        cur = None
        for o in items:
            if (item_text(o, '요청자', 'requester') == row['요청자'] and item_text(o, '수신자', 'recipient') == row['수신자']
                    and item_text(o, '보낸시각', 'sentAt') == row['보낸시각'] and item_text(o, '요지', 'summary') == row['요지']):
                cur = o
                break
        if cur is None:
            return new_precheck('확인불가', '요청자 장부에서 같은 항목을 찾지 못함')
        st = item_text(cur, '상태', 'status')
        rp = item_text(cur, '회신시각', 'replyAt')
        if (st and st != 'open') or rp:
            return new_precheck('요청자처리됨', '요청자 장부 재조회: 상태=%s 회신시각=%s' % (st, rp))

        for o in items:
            if o is cur:
                continue
            os_ = item_text(o, '상태', 'status')
            if os_ and os_ != 'open':
                continue
            if item_text(o, '수신자', 'recipient') != row['수신자']:
                continue
            o_raw = item_text(o, '보낸시각', 'sentAt')
            o_sent = parse_ledger_date(o_raw)
            if not o_sent or o_sent <= sent_at:
                continue
            if summary_prefix_match(item_text(o, '요지', 'summary'), row['요지']):
                return new_precheck('재요청됨', '더 늦은 open 항목 있음(보낸시각 %s)' % o_raw)

        rok, ritems, _ = read_ledger_items(ledger_dir, row['수신자'])
        if rok:
            for o in ritems:
                if item_text(o, '수신자', 'recipient') != row['요청자']:
                    continue
                o_raw = item_text(o, '보낸시각', 'sentAt')
                o_sent = parse_ledger_date(o_raw)
                if o_sent and o_sent >= sent_at:
                    return new_precheck('회신추정', '수신자 장부에 요청자 앞 회신 항목 있음(보낸시각 %s)' % o_raw)
        for p in artifact_paths(row['요지']):
            if os.path.isfile(p):
                mt = datetime.fromtimestamp(os.path.getmtime(p))
                if mt >= sent_at:
                    return new_precheck('회신추정', '산출물 파일이 보낸시각 이후 존재: %s (수정 %s)' % (p, mt.strftime('%Y-%m-%d %H:%M')))
        return new_precheck('흔적없음', '회신 흔적을 찾지 못함 - 기존 3T 유지')
    except Exception as e:
        return new_precheck('확인불가', '예외: %s' % e)


# ------------------------------------------------------------------ 집계
def collect(ledger_dir):
    all_open, hold_deferred = [], []
    file_issues, format_warnings, file_memos = [], [], []
    closed_counts = {}
    session_read_issues, session_format_warnings = {}, {}
    fmt_total, fmt_bad = {}, {}

    def add_format_check(label, raw):
        if raw is None or not str(raw).strip():
            return
        fmt_total.setdefault(label, 0)
        fmt_bad.setdefault(label, 0)
        fmt_total[label] += 1
        if not strict_format(raw):
            fmt_bad[label] += 1

    for fname in sorted(f for f in os.listdir(ledger_dir) if f.lower().endswith('.json')):
        fpath = os.path.join(ledger_dir, fname)
        if not os.path.isfile(fpath):
            continue
        label = fname[:-5]
        closed_counts[label] = 0
        try:
            root = load_json_file(fpath)
        except Exception as e:
            file_issues.append('읽기 문제: %s — JSON 파싱 실패: %s' % (fname, e))
            continue

        if isinstance(root, dict) and root.get('메모'):
            file_memos.append('[%s] %s' % (label, root['메모']))

        items, used_en = get_field(root, '항목', 'items')
        if items is None:
            file_issues.append('읽기 문제: %s — 항목 목록 없음(항목/items 키 없음)' % fname)
            continue
        if used_en:
            file_issues.append("읽기 문제: %s — 최상위가 영문 키(items)로 읽힘(정본은 한글 키 '항목')" % fname)

        missing = english_fb = open_fmt_bad = closed_reply_missing = closed_reply_fmt_bad = hd_missing = 0

        for it in (items if isinstance(items, list) else [items]):
            status = get_field(it, '상태', 'status')[0]

            # 보류·재개대기: open/closed 분기에서 완전히 분리(기한 계산·심각도·에스컬레이션 제외)
            if status in ('hold', 'deferred'):
                req = get_field(it, '요청자', 'requester')[0]
                rec = get_field(it, '수신자', 'recipient')[0]
                summ = get_field(it, '요지', 'summary')[0]
                memo = get_field(it, '메모', 'memo')[0]
                sent = get_field(it, '보낸시각')[0]
                cond = get_field(it, '재개조건')[0]
                owner = get_field(it, '재개주체')[0]
                decider = get_field(it, '결정자')[0]
                decided = get_field(it, '결정일')[0]
                bundle = get_field(it, '묶음')[0]
                missing_keys = [k for k, v in (('재개조건', cond), ('재개주체', owner), ('결정자', decider), ('결정일', decided)) if not v]
                hd_missing += len(missing_keys)
                elapsed_hd = None
                if sent:
                    sent_at = parse_ledger_date(sent)
                    if sent_at:
                        elapsed_hd = round((now() - sent_at).total_seconds() / 60, 1)
                hold_deferred.append({
                    '세션': label, '상태': status, '요청자': req, '수신자': rec, '요지': summ, '보낸시각': sent,
                    '경과분': elapsed_hd, '재개조건': cond, '재개주체': owner, '결정자': decider, '결정일': decided,
                    '묶음': bundle, '메모': memo, '필수키결측': missing_keys})
                continue

            if status and status != 'open':
                closed_counts[label] += 1
                reply = get_field(it, '회신시각', 'replyAt')[0]
                if reply:
                    if not parse_ledger_date(reply):
                        closed_reply_missing += 1
                    else:
                        if not strict_format(reply):
                            closed_reply_fmt_bad += 1
                        add_format_check(label, reply)
                continue

            req, req_en = get_field(it, '요청자', 'requester')
            rec, rec_en = get_field(it, '수신자', 'recipient')
            sent, sent_en = get_field(it, '보낸시각', 'sentAt')
            due, due_en = get_field(it, '약속시각', 'dueAt')
            summ = get_field(it, '요지', 'summary')[0]
            memo = get_field(it, '메모', 'memo')[0]
            ack = get_field(it, '수신확인시각')[0]
            rtype = get_field(it, '요청유형')[0]
            kind = get_field(it, '종류')[0] or '일반'

            if req_en or rec_en or sent_en or due_en:
                english_fb += 1
            if not (req and rec and sent and due):
                missing += 1
                continue
            sent_at, due_at = parse_ledger_date(sent), parse_ledger_date(due)
            if not sent_at or not due_at:
                missing += 1
                continue
            if not strict_format(sent) or not strict_format(due) or not strict_format(ack):
                open_fmt_bad += 1
            add_format_check(label, sent)
            add_format_check(label, due)
            if ack:
                add_format_check(label, ack)

            elapsed = (now() - sent_at).total_seconds() / 60
            promised = (due_at - sent_at).total_seconds() / 60
            ratio = 999 if promised <= 0 else elapsed / promised

            pre_reply = None
            if ack:
                ack_at = parse_ledger_date(ack)
                if ack_at:
                    pre_reply = round((ack_at - sent_at).total_seconds() / 60, 1)

            heavy_warn = (rtype == '무거움') and (not ack) and (elapsed >= HEAVY_NOACK_MIN)

            all_open.append({
                '세션': label, '요청자': req, '수신자': rec, '보낸시각': sent, '약속시각': due,
                '경과분': round(elapsed, 1), '약속분': round(promised, 1), '배수': round(ratio, 2),
                '심각도': severity_label(ratio), '요지': summ, '메모': memo, '요청유형': rtype,
                '수신확인시각': ack, '무거움수신확인경고': heavy_warn, '선회신분': pre_reply, '종류': kind})

        issue_cnt = warn_cnt = 0
        if missing:
            file_issues.append('읽기 문제: %s — 필수 필드 결측/날짜 파싱 실패로 제외된 open 항목 %d 건' % (fname, missing))
            issue_cnt += missing
        if english_fb:
            file_issues.append('읽기 문제: %s — open 항목 중 %d 건이 영문 키 폴백으로 읽힘' % (fname, english_fb))
            issue_cnt += english_fb
        if open_fmt_bad:
            format_warnings.append("형식 경고: %s — open 항목 중 %d 건이 'YYYY-MM-DD HH:MM' 분 단위 형식이 아님(괄호 주석·초 단위 등, 계산엔 지장 없으나 AG-15 형식 규칙 위반)" % (fname, open_fmt_bad))
            warn_cnt += open_fmt_bad
        if closed_reply_missing:
            file_issues.append('읽기 문제: %s — closed 항목 중 %d 건의 회신시각이 날짜만 있거나 문장형이라 시각을 전혀 알 수 없음(AG-15 위반, 소요시간 분석 불가)' % (fname, closed_reply_missing))
            issue_cnt += closed_reply_missing
        if closed_reply_fmt_bad:
            format_warnings.append('형식 경고: %s — closed 항목 중 %d 건의 회신시각이 분 단위 형식이 아님(초 단위·괄호 주석 등)' % (fname, closed_reply_fmt_bad))
            warn_cnt += closed_reply_fmt_bad
        if hd_missing:
            file_issues.append('읽기 문제: %s — 보류·재개대기(hold/deferred) 항목 중 필수 키(재개조건/재개주체/결정자/결정일) 결측 %d 건' % (fname, hd_missing))
            issue_cnt += hd_missing
        if issue_cnt:
            session_read_issues[label] = issue_cnt
        if warn_cnt:
            session_format_warnings[label] = warn_cnt

    format_rate = {s: round((1 - fmt_bad[s] / fmt_total[s]) * 100, 1) for s in fmt_total if fmt_total[s] > 0}
    return dict(all_open=all_open, hold_deferred=hold_deferred, file_issues=file_issues, format_warnings=format_warnings,
                closed_counts=closed_counts, file_memos=file_memos, session_read_issues=session_read_issues,
                session_format_warnings=session_format_warnings, format_rate=format_rate)


def build_result(ledger_dir):
    c = collect(ledger_dir)
    opens = sorted(c['all_open'], key=lambda r: r['배수'], reverse=True)
    for row in opens:
        if row['심각도'] == '3T 초과(심각)' and row['종류'] != '보고':
            row['사전확인'] = precheck_3t(ledger_dir, row)
        else:
            row['사전확인'] = new_precheck('해당없음', '3T 초과 에스컬레이션 대상 아님')
    hd = sorted(c['hold_deferred'], key=lambda r: (r['묶음'] if r['묶음'] else 'zzz_묶음없음', r['세션']))
    person = [r for r in hd if r['재개주체'] == '사람']
    return {
        '조회시각': now().strftime('%Y-%m-%d %H:%M:%S'),
        '열린항목': opens,
        '닫힌건수': sum(c['closed_counts'].values()),
        '세션별닫힌건수': c['closed_counts'],
        '보류건수': sum(1 for r in hd if r['상태'] == 'hold'),
        '재개대기건수': sum(1 for r in hd if r['상태'] == 'deferred'),
        '보류재개대기항목': hd,
        '사람응답대기건수': len(person),
        '사람응답대기항목': person,
        '읽기문제': c['file_issues'],
        '형식경고': c['format_warnings'],
        '세션별읽기문제': c['session_read_issues'],
        '세션별형식경고': c['session_format_warnings'],
        '세션별형식준수율': c['format_rate'],
        '장부메모': c['file_memos'],
    }


# ------------------------------------------------------------------ 텍스트 출력
COLORS = {'Red': 31, 'Yellow': 33, 'Green': 32, 'Gray': 90}


def paint(text, color=None):
    if color and sys.stdout.isatty():
        return '\033[%dm%s\033[0m' % (COLORS[color], text)
    return text


def print_text(r):
    print('=== 대기현황 조회 (%s) ===' % r['조회시각'])
    print()
    if r['읽기문제']:
        print(paint('[읽기 문제]', 'Yellow'))
        for x in r['읽기문제']:
            print(paint('  - ' + x, 'Yellow'))
        print()
    if r['형식경고']:
        print(paint('[형식 경고]', 'Yellow'))
        for x in r['형식경고']:
            print(paint('  - ' + x, 'Yellow'))
        print()
    if r['장부메모']:
        print('[장부 메모]')
        for x in r['장부메모']:
            print('  - ' + x)
        print()

    per = ', '.join('%s %d' % (k, v) for k, v in r['세션별닫힌건수'].items() if v)
    print('열린 항목 %d건 (닫힌 항목 %d 건%s, 표시 생략)' % (len(r['열린항목']), r['닫힌건수'], ': ' + per if per else ''))
    print()

    hd = r['보류재개대기항목']
    if hd:
        print('[보류·재개대기] 보류 %d 건 / 재개대기 %d 건 (에스컬레이션 제외)' % (r['보류건수'], r['재개대기건수']))
        cur = None
        for row in hd:
            bl = row['묶음'] or '(묶음 없음)'
            if bl != cur:
                print('  ・' + bl)
                cur = bl
            sl = '보류' if row['상태'] == 'hold' else '재개대기'
            tag = ' [사람 응답 대기]' if row['재개주체'] == '사람' else ''
            print('    [%s]%s %s: %s' % (sl, tag, row['세션'], row['요지']))
            et = ' (등록 후 %s분 경과)' % row['경과분'] if row['경과분'] is not None else ''
            print('      재개조건: %s / 재개주체: %s / 결정자: %s / 결정일: %s%s' % (
                row['재개조건'], row['재개주체'], row['결정자'], row['결정일'], et))
            if row['필수키결측']:
                print(paint('      [읽기 문제] 필수 키 결측: %s' % ', '.join(row['필수키결측']), 'Yellow'))
        print()

    prop = [x for x in r['열린항목'] if x['종류'] == '규칙전파']
    if prop:
        print('[규칙전파 미회신] %d건' % len(prop))
        for x in prop:
            print('  - %s (%s)' % (x['수신자'], x['요지']))
        print()

    if not r['열린항목']:
        print('열린 대기 항목이 없습니다.')
        return
    colors = {'정상': 'Green', '1T 초과': 'Yellow', '1.5T 초과': 'Yellow', '2T 초과': 'Red', '3T 초과(심각)': 'Red'}
    for row in r['열린항목']:
        ts = ' [%s]' % row['요청유형'] if row['요청유형'] else ''
        ks = ' [규칙전파]' if row['종류'] == '규칙전파' else ''
        col = colors.get(row['심각도'])
        print(paint('[%s]%s%s %s: %s → %s  %s' % (row['심각도'], ts, ks, row['세션'], row['요청자'], row['수신자'], row['요지']), col))
        print('  보낸시각 %s / 약속시각 %s / 경과 %s분 (T=%s분, %s배)' % (
            row['보낸시각'], row['약속시각'], row['경과분'], row['약속분'], row['배수']))
        if row['수신확인시각']:
            pre = ' (선회신 %s분)' % row['선회신분'] if row['선회신분'] is not None else ''
            print('  수신확인시각: %s%s' % (row['수신확인시각'], pre))
        if row['무거움수신확인경고']:
            print(paint('  [경고] 무거움 요청, 보낸 지 10분 지났는데 수신확인시각 없음 — 수신자 상태를 ListAgents(또는 session-stall-check)로 확인하세요', 'Red'))
        pc = row['사전확인']
        if pc and pc['판정'] != '해당없음':
            print('  3T 사전확인: %s - %s' % (pc['판정'], pc['근거']))
        if row['메모']:
            print('  메모: %s' % row['메모'])
        print()


def resolve_ledger_dir(arg):
    d = arg or os.environ.get('AIDLC_LEDGER_DIR') or os.environ.get('QA_INBOX_LEDGER_DIR') \
        or os.path.join(os.path.expanduser('~'), '.claude', 'qa-inbox', 'ledger')
    return os.path.expanduser(d)


def main(argv):
    global _NOW
    ap = argparse.ArgumentParser(description='AG-15 대기 장부 집계(읽기 전용)')
    ap.add_argument('--ledger-dir', help='장부 폴더(기본: env AIDLC_LEDGER_DIR → QA_INBOX_LEDGER_DIR → ~/.claude/qa-inbox/ledger)')
    ap.add_argument('--json', action='store_true', help='JSON 출력(파싱용)')
    ap.add_argument('--now', help='현재 시각 고정 "YYYY-MM-DD HH:MM[:SS]" (테스트용)')
    a = ap.parse_args(argv)
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding='utf-8')
        except Exception:
            pass
    if a.now:
        _NOW = parse_ledger_date(a.now)
        if _NOW is None:
            print('[오류] --now 형식이 잘못되었습니다: %s' % a.now, file=sys.stderr)
            return 2

    ledger_dir = resolve_ledger_dir(a.ledger_dir)
    if not os.path.isdir(ledger_dir):
        if a.json:
            print(json.dumps({'error': 'LedgerDir not found', 'path': ledger_dir}, ensure_ascii=False, indent=2))
        else:
            print('장부 폴더가 없습니다: %s (아직 아무 세션도 장부를 안 쓴 상태일 수 있습니다)' % ledger_dir)
        return 0

    result = build_result(ledger_dir)
    if a.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_text(result)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
