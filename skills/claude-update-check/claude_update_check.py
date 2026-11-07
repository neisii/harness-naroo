#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""claude-update-check — Claude Code 새 버전 점검 + 사용자 결정 기록. 시스템을 바꾸지 않는다(설치·업데이트 없음,
상태 파일에만 기록).

사용법:
  python claude_update_check.py              # 간격(기본 12시간)이 지났을 때만 실제 점검, 아니면 상태 파일만 읽음
  python claude_update_check.py --force      # 간격 무시하고 즉시 점검
  python claude_update_check.py --decide 승인|거부|보류 [--version X.Y.Z]   # 사용자 결정 기록
  python claude_update_check.py --status     # 상태 파일 요약 출력(점검 안 함)

설치·업데이트 명령은 이 스크립트가 절대 실행하지 않는다(`npm install`·`claude update` 호출 코드 없음).
조회는 `claude --version`, `npm view @anthropic-ai/claude-code ...`, 공개 CHANGELOG 읽기뿐이다.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta

# 상태 파일 위치: 환경변수 CLAUDE_UPDATE_CHECK_STATE로 바꿀 수 있고, 기본은 ~/.claude/claude-update-check/state.json
STATE_PATH = os.environ.get('CLAUDE_UPDATE_CHECK_STATE') or os.path.join(
    os.path.expanduser('~'), '.claude', 'claude-update-check', 'state.json')
PKG = '@anthropic-ai/claude-code'
CHANGELOG_URL = 'https://raw.githubusercontent.com/anthropics/claude-code/main/CHANGELOG.md'
CHECK_INTERVAL_H = 12  # 하루 최대 2회 실제 점검
SECURITY_RE = re.compile(r'security|vulnerab|CVE-|exploit|injection|bypass', re.I)
NOW_FMT = '%Y-%m-%d %H:%M'


def now():
    return datetime.now()


def _run(args, timeout=40):
    exe = shutil.which(args[0]) or args[0]
    r = subprocess.run([exe] + args[1:], capture_output=True, timeout=timeout,
                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    return r.returncode, (r.stdout or b'').decode('utf-8', errors='replace').strip()


def vtuple(v):
    m = re.match(r'^(\d+)\.(\d+)\.(\d+)', v or '')
    return tuple(int(x) for x in m.groups()) if m else None


def current_version():
    code, out = _run(['claude', '--version'], timeout=30)
    m = re.match(r'^(\d+\.\d+\.\d+)', out)
    return m.group(1) if m else None


def latest_versions():
    """npm dist-tags(latest·stable)를 돌려준다. 조회 실패 시 None."""
    code, out = _run(['npm', 'view', PKG, 'dist-tags', '--json'], timeout=40)
    if code != 0:
        return None
    try:
        return json.loads(out[out.index('{'):])
    except Exception:
        return None


def release_notes(cur, new, max_sections=3, max_bullets=8, max_len=150):
    """공개 CHANGELOG에서 (cur, new] 버전 절의 앞부분 요약을 만든다. 못 가져오면 (None, False)."""
    try:
        with urllib.request.urlopen(CHANGELOG_URL, timeout=30) as resp:
            text = resp.read().decode('utf-8', errors='replace')
    except Exception:
        return None, False
    cur_t, new_t = vtuple(cur), vtuple(new)
    parts = re.split(r'^## ', text, flags=re.M)[1:]
    out, security = [], False
    count = 0
    for part in parts:
        head, _, body = part.partition('\n')
        vt = vtuple(head.strip())
        if not vt or not (cur_t < vt <= new_t):
            continue
        bullets = [b.strip()[2:] for b in body.splitlines() if b.startswith('- ')]
        if any(SECURITY_RE.search(b) for b in bullets):
            security = True
        if count < max_sections:
            out.append('%s: ' % head.strip() + ' / '.join(
                (b[:max_len] + '…') if len(b) > max_len else b for b in bullets[:max_bullets])
                + (' (외 %d건)' % (len(bullets) - max_bullets) if len(bullets) > max_bullets else ''))
        count += 1
    if count > max_sections:
        out.append('(그 밖에 %d개 버전 생략)' % (count - max_sections))
    return '\n'.join(out) if out else None, security


def load_state():
    if os.path.isfile(STATE_PATH):
        try:
            return json.load(open(STATE_PATH, encoding='utf-8-sig'))
        except Exception:
            pass
    return {}


def save_state(st):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    tmp = STATE_PATH + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(st, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_PATH)


def pending_notice(st):
    """알릴 상태를 돌려준다: None 또는 문장.
    새 버전이 있고 (결정 없음) 또는 (보류 후 한 번 더 알릴 차례) 또는 (승인 후 설치 대기)일 때만 올린다.
    거부한 버전은 다시 올리지 않고, 더 새 버전이 나오면 새 버전으로 올린다."""
    cur, new = st.get('현재버전'), st.get('최신버전')
    if not cur or not new or not (vtuple(new) and vtuple(cur) and vtuple(new) > vtuple(cur)):
        return None
    dec = (st.get('사용자결정') or {})
    if dec.get('버전') == new:
        d = dec.get('결정')
        if d == '거부':
            return None
        if d == '승인':
            return '[Claude Code 업데이트] 승인됨, 설치 대기: 현재 %s → %s — 모든 세션 종료 후 사용자가 직접 설치(claude-update-check 스킬 절차)' % (cur, new)
        if d == '보류':
            if st.get('보류재알림', {}).get(new) == '대기':
                return '[Claude Code 업데이트] 보류했던 버전 재알림(1회): 현재 %s → %s — 승인/거부/보류 결정 필요%s' % (
                    cur, new, ' (보안 수정 포함 가능)' if st.get('보안수정의심') else '')
            return None
    return '[Claude Code 업데이트] 새 버전 %s (현재 %s) — 승인/거부/보류 결정 필요, 설치는 사용자가 직접%s' % (
        new, cur, ' (보안 수정 포함 가능)' if st.get('보안수정의심') else '')


def check(force=False):
    st = load_state()
    last = st.get('확인시각')
    if not force and last:
        try:
            if now() - datetime.strptime(last, NOW_FMT) < timedelta(hours=CHECK_INTERVAL_H):
                return st, False
        except ValueError:
            pass
    cur = current_version()
    tags = latest_versions()
    st['확인시각'] = now().strftime(NOW_FMT)
    if cur:
        st['현재버전'] = cur
    if not tags:
        st['점검결과'] = '조회 실패(npm view) — 이전 값 유지'
    else:
        st['점검결과'] = '정상'
        st['최신버전'] = tags.get('latest')
        st['stable버전'] = tags.get('stable')
        new = st['최신버전']
        if cur and new and vtuple(new) and vtuple(cur) and vtuple(new) > vtuple(cur):
            notes, sec = release_notes(cur, new)
            st['릴리스노트요약'] = notes or '(릴리스 노트를 가져오지 못함)'
            st['보안수정의심'] = bool(sec)
            # 보류한 버전은 실제 다음 점검 때 한 번 더 알린 뒤(대기) 그다음 점검에서 조용히 둔다(완료)
            reminders = st.setdefault('보류재알림', {})
            for v, s in list(reminders.items()):
                if s == '대기':
                    reminders[v] = '완료'
                elif s == '다음점검':
                    reminders[v] = '대기'
        else:
            st['릴리스노트요약'] = None
            st['보안수정의심'] = False
    save_state(st)
    return st, True


def decide(decision, version=None):
    st = load_state()
    version = version or st.get('최신버전')
    if not version:
        print('[오류] 결정할 버전이 없습니다. 먼저 --force로 점검하세요.')
        return 2
    st['사용자결정'] = {'버전': version, '결정': decision, '결정일': now().strftime('%Y-%m-%d')}
    hist = st.setdefault('거부보류버전', {})
    if decision in ('거부', '보류'):
        hist[version] = decision
    else:
        hist.pop(version, None)
    reminders = st.setdefault('보류재알림', {})
    if decision == '보류':
        reminders[version] = '다음점검'
    else:
        reminders.pop(version, None)
    save_state(st)
    print('결정 기록: %s %s' % (version, decision))
    return 0


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--decide', choices=['승인', '거부', '보류'])
    ap.add_argument('--version')
    ap.add_argument('--status', action='store_true')
    a = ap.parse_args(argv)
    if a.decide:
        return decide(a.decide, a.version)
    if a.status:
        st = load_state()
        print(json.dumps(st, ensure_ascii=False, indent=2))
        print(pending_notice(st) or '(알릴 항목 없음)')
        return 0
    st, did = check(a.force)
    print('점검 %s' % ('실행' if did else '생략(간격 미경과)'))
    print(json.dumps(st, ensure_ascii=False, indent=2))
    print(pending_notice(st) or '(알릴 항목 없음)')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
