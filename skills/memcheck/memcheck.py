#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""memcheck — OS 메모리(총량/사용/여유)와 상위 java 프로세스별 메모리를 보여주는 읽기 전용 CLI.

사용법:
  python3 memcheck.py [--server-min-gb 2.5] [--test-min-gb 4.0] [--top 10] [--json] [--watch N]
                      [--process-name java] [--warn-free-gb X]

- 상태를 바꾸지 않는다. 그 순간 OS를 직접 관찰할 뿐이라 누구든 승인 없이 호출할 수 있다.
- 여유 물리메모리가 용도별 기준에 못 미치면 표시한다: 서버 기동 --server-min-gb(기본 2.5GB),
  테스트·훅 --test-min-gb(기본 4.0GB). --warn-free-gb 는 종전 호출 호환용으로 --server-min-gb 와 같은 뜻.
- 종료 코드: 항상 0(경고는 출력으로만 알린다 — 원본 memcheck.ps1과 동일). 조회 자체가 불가능하면 2.
- 여유 메모리 산출: macOS=free+inactive+speculative 페이지(vm_stat), Linux=MemAvailable(/proc/meminfo),
  Windows=GlobalMemoryStatusEx 의 ullAvailPhys. 표준 라이브러리만 사용한다.
"""
import argparse
import ctypes
import json
import os
import re
import shutil
import subprocess
import sys
import time

GB = 1024.0 ** 3


# ---------------------------------------------------------------- 메모리 (OS별)
def _run(args, timeout=15):
    r = subprocess.run(args, capture_output=True, timeout=timeout)
    return r.returncode, (r.stdout or b'').decode('utf-8', errors='replace')


def mem_macos():
    code, out = _run(['sysctl', '-n', 'hw.memsize'])
    total = float(out.strip())
    code, vm = _run(['vm_stat'])
    m = re.search(r'page size of (\d+) bytes', vm)
    page = int(m.group(1)) if m else 4096

    def pages(label):
        mm = re.search(r'^Pages %s:\s+(\d+)\.' % re.escape(label), vm, re.M)
        return int(mm.group(1)) if mm else 0
    free = (pages('free') + pages('inactive') + pages('speculative')) * page
    return total, float(free)


def mem_linux():
    info = {}
    with open('/proc/meminfo', encoding='utf-8') as f:
        for line in f:
            k, _, v = line.partition(':')
            parts = v.split()
            if parts:
                info[k.strip()] = float(parts[0]) * 1024  # kB -> bytes
    total = info['MemTotal']
    if 'MemAvailable' in info:
        free = info['MemAvailable']
    else:  # 아주 오래된 커널 폴백
        free = info.get('MemFree', 0) + info.get('Buffers', 0) + info.get('Cached', 0)
    return total, free


def mem_windows():
    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [('dwLength', ctypes.c_ulong), ('dwMemoryLoad', ctypes.c_ulong),
                    ('ullTotalPhys', ctypes.c_ulonglong), ('ullAvailPhys', ctypes.c_ulonglong),
                    ('ullTotalPageFile', ctypes.c_ulonglong), ('ullAvailPageFile', ctypes.c_ulonglong),
                    ('ullTotalVirtual', ctypes.c_ulonglong), ('ullAvailVirtual', ctypes.c_ulonglong),
                    ('sullAvailExtendedVirtual', ctypes.c_ulonglong)]
    st = MEMORYSTATUSEX()
    st.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
        raise OSError('GlobalMemoryStatusEx 실패')
    return float(st.ullTotalPhys), float(st.ullAvailPhys)


def system_memory():
    if sys.platform == 'darwin':
        return mem_macos()
    if sys.platform.startswith('linux'):
        return mem_linux()
    if sys.platform == 'win32':
        return mem_windows()
    raise OSError('지원하지 않는 OS: ' + sys.platform)


# ---------------------------------------------------------------- 프로세스 (OS별)
def _label_from_cmdline(cmd):
    """java 명령행에서 사람이 알아볼 짧은 이름: -jar 파일명 → 메인 클래스 → '(java)'."""
    toks = cmd.split()
    for i, t in enumerate(toks):
        if t == '-jar' and i + 1 < len(toks):
            return os.path.basename(toks[i + 1].replace('\\', '/'))
    skip_next = False
    for t in toks[1:]:
        if skip_next:
            skip_next = False
            continue
        if t in ('-cp', '-classpath', '--class-path', '-p', '--module-path'):
            skip_next = True
            continue
        if not t.startswith('-'):
            return t
    return '(java)'


def listening_ports_posix():
    """pid -> 가장 작은 LISTEN 포트. lsof 가 없으면 빈 맵."""
    if not shutil.which('lsof'):
        return {}
    try:
        code, out = _run(['lsof', '-nP', '-iTCP', '-sTCP:LISTEN', '-Fpn'], timeout=20)
    except Exception:
        return {}
    ports, pid = {}, None
    for line in out.splitlines():
        if line.startswith('p'):
            pid = int(line[1:])
        elif line.startswith('n') and pid is not None:
            m = re.search(r':(\d+)$', line)
            if m:
                p = int(m.group(1))
                if pid not in ports or p < ports[pid]:
                    ports[pid] = p
    return ports


def procs_posix(name):
    code, out = _run(['ps', '-axo', 'pid=,rss=,command='])
    ports = listening_ports_posix()
    rows = []
    for line in out.splitlines():
        parts = line.strip().split(None, 2)
        if len(parts) < 3 or not parts[0].isdigit():
            continue
        pid, rss_kb, cmd = int(parts[0]), parts[1], parts[2]
        exe = os.path.basename(cmd.split()[0])
        if exe != name:
            continue
        rows.append({'Project': _label_from_cmdline(cmd), 'Port': ports.get(pid),
                     'WorkingSetGB': round(float(rss_kb) * 1024 / GB, 2), 'Pid': pid})
    return rows


def procs_windows(name):
    # tasklist: 이미지 이름/PID/메모리 사용량(작업 집합). 명령행은 표준 도구만으론 얻기 번거로워 라벨은 (java)로 둔다.
    code, out = _run(['tasklist', '/FI', 'IMAGENAME eq %s.exe' % name, '/FO', 'CSV', '/NH'], timeout=30)
    ports = {}
    try:
        code2, ns = _run(['netstat', '-ano', '-p', 'TCP'], timeout=30)
        for line in ns.splitlines():
            f = line.split()
            if len(f) >= 5 and f[3].upper() == 'LISTENING':
                m = re.search(r':(\d+)$', f[1])
                if m:
                    pid, p = int(f[4]), int(m.group(1))
                    if pid not in ports or p < ports[pid]:
                        ports[pid] = p
    except Exception:
        pass
    rows = []
    import csv
    for rec in csv.reader(out.splitlines()):
        if len(rec) < 5 or not rec[1].isdigit():
            continue
        kb = re.sub(r'[^\d]', '', rec[4])
        if not kb:
            continue
        pid = int(rec[1])
        rows.append({'Project': '(%s)' % name, 'Port': ports.get(pid),
                     'WorkingSetGB': round(float(kb) * 1024 / GB, 2), 'Pid': pid})
    return rows


def get_status(a):
    total, free = system_memory()
    used = total - free
    free_gb = round(free / GB, 2)
    summary = {
        'TotalGB': round(total / GB, 2), 'UsedGB': round(used / GB, 2), 'FreeGB': free_gb,
        'UsedPct': round(used / total * 100, 1),
        'ServerMinGB': a.server_min_gb, 'TestMinGB': a.test_min_gb,
        'ServerOk': free_gb >= a.server_min_gb, 'TestOk': free_gb >= a.test_min_gb,
        'Warning': free_gb < a.server_min_gb,  # 서버 기동 기준 미달(종전 Warning 과 같은 뜻)
    }
    try:
        rows = procs_windows(a.process_name) if sys.platform == 'win32' else procs_posix(a.process_name)
    except Exception:
        rows = []
    rows.sort(key=lambda r: r['WorkingSetGB'], reverse=True)
    return {'Summary': summary, 'Processes': rows[:a.top]}


# ---------------------------------------------------------------- 출력
def _c(text, color):
    if not sys.stdout.isatty():
        return text
    code = {'Red': 31, 'Yellow': 33, 'Green': 32, 'Cyan': 36}[color]
    return '\033[%dm%s\033[0m' % (code, text)


def show(a):
    status = get_status(a)
    if a.json:
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return
    s = status['Summary']
    color = 'Red' if not s['ServerOk'] else ('Yellow' if not s['TestOk'] else 'Green')
    print(_c('전체 %sGB / 사용 %sGB (%s%%) / 여유 %sGB' % (s['TotalGB'], s['UsedGB'], s['UsedPct'], s['FreeGB']), color))
    print(_c('서버 기동 기준 %.1fGB 이상: %s / 테스트·훅 기준 %.1fGB 이상: %s' % (
        s['ServerMinGB'], '충족' if s['ServerOk'] else '미달',
        s['TestMinGB'], '충족' if s['TestOk'] else '미달'), color))
    if not s['ServerOk']:
        print(_c('[경고] 여유 메모리가 %sGB로 서버 기동 기준(%.1fGB) 미달입니다. 새 서버를 띄우기 전에 사람(또는 qa-master)에게 '
                 '진행 여부를 확인받으세요. 테스트·훅(기준 %.1fGB)도 같은 방식입니다.' % (
                     s['FreeGB'], s['ServerMinGB'], s['TestMinGB']), 'Red'))
    elif not s['TestOk']:
        print(_c('[주의] 여유 메모리가 %sGB로 테스트·훅 기준(%.1fGB) 미달입니다. 서버 기동은 가능하지만 테스트·훅을 돌리기 전에 '
                 '사람(또는 qa-master)에게 진행 여부를 확인받으세요.' % (s['FreeGB'], s['TestMinGB']), 'Yellow'))
    if status['Processes']:
        print('%-30s %-8s %-13s %s' % ('Project', 'Port', 'WorkingSetGB', 'Pid'))
        for r in status['Processes']:
            print('%-30s %-8s %-13s %s' % (r['Project'][:30], r['Port'] if r['Port'] else '-', r['WorkingSetGB'], r['Pid']))
    else:
        print('(떠 있는 %s 프로세스 없음)' % a.process_name)


def main(argv):
    ap = argparse.ArgumentParser(description='시스템/자바 프로세스 메모리 점검(읽기 전용)')
    ap.add_argument('--server-min-gb', type=float, default=2.5)
    ap.add_argument('--test-min-gb', type=float, default=4.0)
    ap.add_argument('--warn-free-gb', type=float, default=0, help='호환용: 주면 --server-min-gb 로 쓴다')
    ap.add_argument('--top', type=int, default=10)
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--watch', type=int, default=0, help='N초 간격으로 반복(Ctrl+C 종료)')
    ap.add_argument('--process-name', default='java', help='목록에 올릴 프로세스 이름(기본 java)')
    a = ap.parse_args(argv)
    if a.warn_free_gb > 0:
        a.server_min_gb = a.warn_free_gb
    try:
        if a.watch > 0:
            while True:
                if sys.stdout.isatty():
                    sys.stdout.write('\033[2J\033[H')
                print(_c('시스템 메모리 현황 (%s, %d초 간격, Ctrl+C 종료)' % (time.strftime('%H:%M:%S'), a.watch), 'Cyan'))
                show(a)
                sys.stdout.flush()
                time.sleep(a.watch)
        else:
            show(a)
    except KeyboardInterrupt:
        return 0
    except Exception as e:
        print('[오류] 메모리 조회 실패: %r' % e, file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
