# -*- coding: utf-8 -*-
"""patrol-notify — "사람 응답 대기" 항목을 백오프 간격으로 OS 알림(os-notify)으로 알리는 결정론적 스크립트.

상태 JSON(대기 장부 집계 결과)을 --status-json <파일> 또는 stdin 으로 받는다(스키마는 SKILL.md 참고).

사용법:
  python3 patrol_notify.py --status-json status.json            # 평소 — 순찰 루프 틱마다 호출
  cat status.json | python3 patrol_notify.py                    # stdin 입력
  python3 patrol_notify.py --status-json status.json --dry-run  # 알림·상태 갱신 없이 due 항목만 출력
  python3 patrol_notify.py --mark-sent KEY [KEY ...]            # 회신추정 항목 발송 기록(상태 JSON 불필요)
  옵션: --state-path <파일>  (기본 ~/.claude/patrol-notify/state.json, 환경변수 PATROL_NOTIFY_STATE)

종료 코드: 0 정상(알림 실패 경고 포함 — 원본과 동일하게 백오프만 진행하지 않음), 2 입력 오류.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime

GAPS = (120, 240, 480, 960)  # 분. 이후는 1440(24h)씩
LATER_GAP = 1440
SHOW_MAX = 3
OS_NOTIFY = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, 'os-notify', 'os_notify.py')


def now_str(fmt='%Y-%m-%d %H:%M'):
    return datetime.now().strftime(fmt)


def item_key(item):
    return '%s::%s' % (item.get('세션'), item.get('요지'))


def reply_id(k):
    """회신추정 항목의 발송 기록 키: sha1 앞 10자(요지에 공백·따옴표가 있어도 인자로 안전)."""
    return hashlib.sha1(k.encode('utf-8')).hexdigest()[:10]


def threshold_min(count):
    """count = 이미 보낸 알림 횟수(0=아직 없음). 누적 임계값(분)."""
    total = 0
    for i in range(count + 1):
        total += GAPS[i] if i < len(GAPS) else LATER_GAP
    return total


def default_state_path():
    return os.environ.get('PATROL_NOTIFY_STATE') or os.path.join(
        os.path.expanduser('~'), '.claude', 'patrol-notify', 'state.json')


def load_state(path):
    state, reply = {}, {}
    if os.path.isfile(path):
        try:
            with open(path, encoding='utf-8-sig') as f:
                loaded = json.load(f)
            for k, v in (loaded.get('항목') or {}).items():
                state[k] = {'알림횟수': int(v.get('알림횟수', 0)), '마지막알림시각': v.get('마지막알림시각')}
            for k, v in (loaded.get('회신추정확인') or {}).items():
                reply[k] = {'발송시각': v.get('발송시각')}
        except Exception as e:
            # 읽기 실패해도 막지 않고 빈 상태로 새로 시작 — 알림이 중복될 수는 있어도 영원히 안 가는 것보다 안전
            print('경고: 상태 파일 파싱 실패, 새로 시작합니다: %r' % e)
            state, reply = {}, {}
    return state, reply


def save_state(path, state, reply):
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump({'갱신시각': now_str('%Y-%m-%d %H:%M:%S'), '항목': state, '회신추정확인': reply},
                  f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def read_status(path):
    try:
        if path and path != '-':
            with open(path, encoding='utf-8-sig') as f:
                data = json.load(f)
        else:
            if sys.stdin is None or sys.stdin.isatty():
                print('[오류] --status-json <파일>을 주거나 stdin 으로 상태 JSON 을 넘기세요.', file=sys.stderr)
                return None
            data = json.loads(sys.stdin.read().lstrip('﻿'))
    except Exception as e:
        print('[오류] 상태 JSON 을 읽지 못했습니다: %r' % e, file=sys.stderr)
        return None
    if not isinstance(data, dict):
        print('[오류] 상태 JSON 최상위는 객체여야 합니다.', file=sys.stderr)
        return None
    return data


def send_os_notify(title, message, level):
    """os-notify 를 호출한다. 인자는 리스트로 직접 넘기므로 따옴표·줄바꿈이 있어도 쪼개지지 않는다."""
    script = os.path.normpath(OS_NOTIFY)
    if not os.path.isfile(script):
        raise FileNotFoundError('os-notify 스크립트를 찾을 수 없음: ' + script)
    r = subprocess.run([sys.executable, script, '--title', title, '--message', message, '--level', level],
                       capture_output=True, timeout=60)
    if r.returncode == 3:
        # os-notify 가 알림 수단을 못 찾아 stdout 폴백만 함 = 네이티브 미전달.
        raise RuntimeError('os-notify 가 알림 수단을 찾지 못해 stdout 폴백만 했습니다(네이티브 미전달)')
    if r.returncode != 0:
        err = (r.stderr or r.stdout or b'').decode('utf-8', errors='replace').strip()
        raise RuntimeError('os-notify 종료 코드 %d: %s' % (r.returncode, err))


def main(argv):
    ap = argparse.ArgumentParser(description='사람 응답 대기 백오프 알림')
    ap.add_argument('--status-json', help='대기 현황 상태 JSON 파일(생략하면 stdin)')
    ap.add_argument('--state-path', default=None, help='백오프 상태 파일(기본 ~/.claude/patrol-notify/state.json)')
    ap.add_argument('--dry-run', action='store_true', help='알림·상태 갱신 없이 무엇이 due 인지만 출력')
    ap.add_argument('--mark-sent', nargs='+', metavar='KEY', help='회신추정 항목 발송 기록')
    a = ap.parse_args(argv)
    state_path = a.state_path or default_state_path()

    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding='utf-8')
        except Exception:
            pass

    state, reply_state = load_state(state_path)

    if a.mark_sent:
        for k in a.mark_sent:
            reply_state[k] = {'발송시각': now_str()}
        if not a.dry_run:
            save_state(state_path, state, reply_state)
        print('회신추정 발송 기록: %d건%s' % (len(a.mark_sent), ' (dry-run - 저장 안 함)' if a.dry_run else ''))
        return 0

    data = read_status(a.status_json)
    if data is None:
        return 2
    waiting = [x for x in (data.get('사람응답대기항목') or []) if isinstance(x, dict)]

    # 막힌 건수 계산용: 묶음별 전체 보류·재개대기 건수(사람 응답 대기 포함)
    bundle_counts = {}
    for hd in (data.get('보류재개대기항목') or []):
        b = hd.get('묶음') if isinstance(hd, dict) else None
        if b:
            bundle_counts[b] = bundle_counts.get(b, 0) + 1

    due = []
    for item in waiting:
        elapsed = item.get('경과분')
        if elapsed is None:  # 보낸시각 없어 경과분 계산 불가 — 추측하지 않고 건너뜀
            continue
        key = item_key(item)
        count = state[key]['알림횟수'] if key in state else 0
        if elapsed >= threshold_min(count):
            blocked = 0
            if item.get('묶음') and item['묶음'] in bundle_counts:
                blocked = bundle_counts[item['묶음']] - 1
            due.append({'Key': key, 'Item': item, 'Count': count, 'Elapsed': elapsed, 'Blocked': max(0, blocked)})

    # 해소된(더 이상 대기 목록에 없는) 항목은 상태에서 뺀다 — 알릴 게 없는 틱이라도 한다.
    live_keys = {item_key(x) for x in waiting}
    pruned = {k: v for k, v in state.items() if k in live_keys}

    if not waiting:
        print('사람 응답 대기 항목 없음.')
    elif not due:
        print('사람 응답 대기 %d건, 알림 임계값 도달 0건.' % len(waiting))
    else:
        due.sort(key=lambda d: d['Elapsed'], reverse=True)
        shown, rest = due[:SHOW_MAX], len(due) - SHOW_MAX
        lines = []
        for d in shown:
            hours = '%g' % round(d['Elapsed'] / 60, 1)
            blocked_txt = ', 같은 묶음 %d건 대기' % d['Blocked'] if d['Blocked'] > 0 else ''
            lines.append('%s(%s) - %sh 경과%s' % (d['Item'].get('요지'), d['Item'].get('세션'), hours, blocked_txt))
        message = '\n'.join(lines)
        if rest > 0:
            message += '\n...외 %d 건' % rest
        max_count = max(d['Count'] for d in due)
        level = 'Error' if max_count >= 3 else ('Warning' if max_count >= 1 else 'Info')
        title = '[사람 응답 대기] %d건' % len(due)

        print('DUE: %s (%s)' % (title, level))
        print(message)

        if a.dry_run:
            print('(dry-run — 알림·상태 갱신 안 함)')
        else:
            notified = False
            try:
                send_os_notify(title, message, level)
                notified = True
            except Exception as e:
                print('경고: 알림 미전달 - 백오프 진행 안 함: %s' % e, file=sys.stderr)
            if notified:
                for d in due:
                    pruned[d['Key']] = {'알림횟수': d['Count'] + 1, '마지막알림시각': now_str()}

    # 회신추정 3T 항목: 사람 에스컬레이션 대신 qa-master 정보 알림 + 요청자에게 '장부 종결 여부 확인'(정보 전달).
    # 스크립트는 세션에 메시지를 보낼 수 없으므로 발송 대상·문안을 출력하고, 순찰 세션이 보낸 뒤 --mark-sent 로 기록한다.
    reply_items = [x for x in (data.get('열린항목') or [])
                   if isinstance(x, dict) and isinstance(x.get('사전확인'), dict) and x['사전확인'].get('판정') == '회신추정']
    live_reply, pending_send = set(), []
    for r in reply_items:
        rk = reply_id('%s::%s::%s' % (r.get('세션'), r.get('요지'), r.get('보낸시각')))
        live_reply.add(rk)
        if rk not in reply_state:
            pending_send.append((rk, r))
    pruned_reply = {k: v for k, v in reply_state.items() if k in live_reply}
    if pending_send:
        print('회신추정 3T 항목 %d건 - 아래 문안을 보내고 항목마다 patrol_notify.py --mark-sent <KEY> 로 기록한다'
              '(같은 항목에 반복 발송 금지).' % len(pending_send))
        for rk, i in pending_send:
            basis = i['사전확인'].get('근거')
            print('  KEY: %s' % rk)
            print("  SEND-TO %s: [순찰 정보] '%s'에게 보낸 요청 '%s'(보낸시각 %s)에 수신자 회신 흔적이 있습니다(%s). "
                  "장부 종결 여부를 확인해 주세요. (정보 전달, 구현·결정 요청 아님)" % (
                      i.get('요청자'), i.get('수신자'), i.get('요지'), i.get('보낸시각'), basis))
            print("  SEND-TO qa-master: [순찰 정보] 3T 초과 항목 '%s'(%s -> %s)는 수신자 회신 흔적이 있어 사람 에스컬레이션 대신 "
                  "정보로 낮췄습니다(%s). 요청자에게 장부 종결 확인을 보냈습니다." % (
                      i.get('요지'), i.get('요청자'), i.get('수신자'), basis))

    if not a.dry_run:
        save_state(state_path, pruned, pruned_reply)
        print('상태 갱신: %s' % state_path)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
