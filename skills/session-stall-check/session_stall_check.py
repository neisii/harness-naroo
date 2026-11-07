# -*- coding: utf-8 -*-
"""
session_stall_check.py — 특정 bg 세션 하나의 "정체(사람 입력 대기) 의심" 여부를 즉시 조회하는 읽기 전용 CLI.

`claude agents --json`의 `state`는 AskUserQuestion 대기 중에도 멈추기 직전 값("working")에 그대로
고정되어 "입력 대기"와 "정상 작업 중"을 구분하지 못한다. 그래서 세션 transcript(jsonl)의 mtime 경과를
추가로 본다.

사용법:
  python -X utf8 session_stall_check.py <세션명>
  python -X utf8 session_stall_check.py <세션명> --threshold-min 15

출력(한 줄): state, transcript 무활동분, 판정.
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import time

CLAUDE_PROJECTS_DIR = os.path.join(os.path.expanduser('~'), '.claude', 'projects')
DEFAULT_THRESHOLD_MIN = 15  


def run_claude_agents_all():
    # `claude`는 Windows에서 .cmd 셈이라 subprocess.run(['claude', ...], shell=False)는 PATHEXT를
    # 못 찾아 FileNotFoundError를 던진다(실측, ops_report.py에서도 같은 버그 발견·수정)
    # — shutil.which로 실제 경로를 찾아 호출한다.
    try:
        claude_exe = shutil.which('claude') or 'claude'
        result = subprocess.run(
            [claude_exe, 'agents', '--all', '--json'],
            capture_output=True, text=True, encoding='utf-8', timeout=30,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
        return json.loads(result.stdout)
    except Exception:
        return []


def transcript_mtime(session_id):
    matches = glob.glob(os.path.join(CLAUDE_PROJECTS_DIR, '*', session_id + '.jsonl'))
    if not matches:
        return None
    return max(os.path.getmtime(m) for m in matches)


def find_agent_record(agents, name):
    """같은 이름이 여러 건이면 pid 있는(살아있는) 것을 먼저 쓰고, 없으면 startedAt이 가장 큰
    것을 쓴다."""
    candidates = [a for a in agents if a.get('name') == name]
    if not candidates:
        return None
    with_pid = [a for a in candidates if a.get('pid')]
    pool = with_pid if with_pid else candidates
    return max(pool, key=lambda a: a.get('startedAt', 0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('session_name')
    ap.add_argument('--threshold-min', type=float, default=DEFAULT_THRESHOLD_MIN,
                     help='입력 대기 의심 판정 기준(분), 기본 %d' % DEFAULT_THRESHOLD_MIN)
    args = ap.parse_args()

    agents = run_claude_agents_all()
    record = find_agent_record(agents, args.session_name)
    if record is None:
        print('세션: %s | 조회 결과: claude agents 목록에 없음(이름 오타 또는 daemon 정리됨)' % args.session_name)
        sys.exit(1)

    state = record.get('state', '(없음)')
    session_id = record.get('sessionId')
    mtime = transcript_mtime(session_id) if session_id else None
    if mtime is None:
        idle_text = 'transcript 없음(확인 불가)'
        idle_min = None
    else:
        idle_min = (time.time() - mtime) / 60
        idle_text = '%.1f분' % idle_min

    if state == 'done':
        verdict = '정상(세션 종료됨)'
    elif idle_min is None:
        verdict = '판정 불가(transcript 없음)'
    elif idle_min >= args.threshold_min:
        verdict = '입력 대기 의심(무활동 %.0f분 >= %.0f분, 정상 대기일 수도 있음)' % (idle_min, args.threshold_min)
    else:
        verdict = '정상(무활동 %.0f분 < %.0f분)' % (idle_min, args.threshold_min)

    print('세션: %s | state: %s | transcript 무활동: %s | 판정: %s' % (
        args.session_name, state, idle_text, verdict))


if __name__ == '__main__':
    main()
