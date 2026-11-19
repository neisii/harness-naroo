#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""session-wake — 이름으로 bg 세션을 복사본 없이 깨운다.

사용법: python session_wake.py <세션명> [--dry-run]

동작:
1. `claude agents --all --json`(배열)에서 이름이 같은 레코드를 모으고 startedAt이 가장 큰 것을 고른다.
2. 같은 이름 레코드 중 `pid`가 있는 것이 있으면 resume하지 않고 "이미 떠 있음"을 출력한다.
3. 없으면 그 레코드의 전체 sessionId·cwd로 `claude --bg --resume <전체 sessionId>`를 실행한다(짧은 id 금지).
4. 출력에 `started a copy as <newId>`가 있으면 그 복사본을 `claude stop <newId>`로 즉시 종료하고,
   원본 이름으로 SendMessage하라고 안내한다.
5. 마지막에 같은 이름 레코드 수를 다시 조회해 보고한다.

프로세스 직접 종료는 하지 않는다(`claude stop`만 쓴다). 종료 코드: 0 정상(이미 떠 있음·깨움·복사본 정리),
2 사용법·입력 오류, 3 이름 없음(신규 기동 필요), 4 재개 실패.
"""
import json
import os
import re
import shutil
import subprocess
import sys

UUID_RE = re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')
COPY_RE = re.compile(r'started a copy as\s+([0-9A-Za-z-]+)')


def _claude():
    return shutil.which('claude') or 'claude'


def _run(args, cwd=None, timeout=90):
    r = subprocess.run([_claude()] + args, capture_output=True, cwd=cwd, timeout=timeout,
                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    out = (r.stdout or b'').decode('utf-8', errors='replace') + (r.stderr or b'').decode('utf-8', errors='replace')
    return r.returncode, out


def list_agents():
    """`claude agents --all --json` 결과를 레코드 배열로 돌려준다(배열 또는 배열을 감싼 객체 모두 허용)."""
    code, out = _run(['agents', '--all', '--json'], timeout=30)
    start = out.find('[')
    data = json.loads(out[start:]) if start >= 0 else []
    if isinstance(data, dict):
        data = next((v for v in data.values() if isinstance(v, list)), [])
    return data


def same_name(records, name):
    return [r for r in records if r.get('name') == name]


def main(argv):
    dry = '--dry-run' in argv
    args = [a for a in argv if a != '--dry-run']
    if len(args) != 1:
        print('사용법: python session_wake.py <세션명> [--dry-run]')
        return 2
    name = args[0]

    recs = same_name(list_agents(), name)
    if not recs:
        print('[없음] 이름이 "%s"인 레코드가 없습니다. 완전히 새 세션이므로 `claude --bg`로 신규 기동하세요.' % name)
        return 3
    recs.sort(key=lambda r: r.get('startedAt') or 0)
    latest = recs[-1]
    print('같은 이름 레코드 %d건, 선택: id=%s sessionId=%s state=%s pid=%s' % (
        len(recs), latest.get('id'), latest.get('sessionId'), latest.get('state'), latest.get('pid', '없음')))

    live = [r for r in recs if r.get('pid')]
    if live:
        r = live[-1]
        print('[이미 떠 있음] %s (id=%s, pid=%s) — resume하지 않습니다. 이 세션에 SendMessage로 바로 지시하세요.' % (
            name, r.get('id'), r.get('pid')))
        if len(recs) > 1:
            print('주의: 같은 이름 레코드가 %d건입니다(복사본 잔존 가능). 모호하면 SendMessage가 막힐 수 있습니다.' % len(recs))
        return 0

    sid, cwd = latest.get('sessionId') or '', latest.get('cwd') or ''
    if not UUID_RE.match(sid):
        print('[오류] sessionId가 전체 UUID가 아닙니다(%r). 짧은 id로는 resume하지 않습니다.' % sid)
        return 2
    if not os.path.isdir(cwd):
        print('[오류] 레코드의 cwd를 찾을 수 없습니다: %s' % cwd)
        return 2
    if dry:
        print('[dry-run] 실행 예정: claude --bg --resume %s (cwd=%s)' % (sid, cwd))
        return 0

    code, out = _run(['--bg', '--resume', sid], cwd=cwd)
    print('--- claude --bg --resume 출력 ---')
    print(out.strip())
    print('---------------------------------')
    if code != 0:
        print('[재개 실패] 종료 코드 %d — 위 출력을 확인하세요(프로세스를 직접 종료하지 않았습니다).' % code)
        return 4

    m = COPY_RE.search(out)
    if m:
        new_id = m.group(1)
        print('[복사본 감지] 원본이 실제로는 살아 있어 복사본 %s가 생겼습니다. claude stop %s 실행.' % (new_id, new_id))
        scode, sout = _run(['stop', new_id], timeout=60)
        print((sout.strip() or '(출력 없음)') + ' (종료 코드 %d)' % scode)
        print('다음: 원본 "%s"에 SendMessage로 지시하세요(복사본에는 보내지 않습니다).' % name)
    else:
        print('[재개 완료] 복사본 없이 %s가 같은 id·이름으로 복귀했습니다. 기본 시작 프롬프트는 다시 넣지 않고, --disallowedTools 등 최초 기동 옵션은 Claude Code가 저장된 값으로 다시 적용합니다(위 note 참고).' % name)

    final = same_name(list_agents(), name)
    print('최종 같은 이름 레코드: %d건 %s' % (
        len(final), ['%s(%s%s)' % (r.get('id'), r.get('state'), ',pid' if r.get('pid') else '') for r in final]))
    if len(final) != 1:
        print('경고: 1건이 아닙니다. 종료된 복사본 레코드가 남아 있을 수 있으니 SendMessage 전에 이름이 유일하게 해석되는지 확인하세요.')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
