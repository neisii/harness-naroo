# -*- coding: utf-8 -*-
# Copyright 2026 Baek Ga-hui (neisii) - https://github.com/neisii/harness-naroo
# SPDX-License-Identifier: Apache-2.0
"""
session_stall_check.py — 세션 하나가 지금 어떤 상태인지(특히 사람 입력 대기인지) 즉시 조회하는 읽기 전용 CLI.

판정은 `claude agents --all --json`의 세 필드 조합으로 한다(Claude Code agent-view 문서 기준, 2.1.328에서 실측 확인).
- state=blocked 또는 status=waiting: 사람만 풀 수 있는 것(승인·응답·로그인)을 기다린다. pid 유무와 무관하게 먼저 본다.
- pid 있음(살아 있음): status를 믿는다. busy=작업 중 / idle+state=working=턴은 끝났지만 할 일이 남음(/loop 등)
  / 그 밖의 idle=턴을 끝내고 다음 지시 대기(이때 state는 done — done은 '종료'가 아니다).
- pid 없음: 프로세스가 떠 있지 않다(종료·유휴 정리·재시작). 마지막 state(done/failed/stopped)는 참고만.

transcript(jsonl) 수정 시각은 '마지막 기록' 참고값으로만 보인다. 턴이 끝난 뒤에도 자리 비움 요약(away_summary)이
몇 초~몇 분 뒤 자동 기록되므로 실제 마지막 활동보다 조금 최근으로 보인다. busy인데 기록이 오래 안 바뀌면
'오래 걸리는 작업이거나 멈춤 의심'으로 표시한다(--threshold-min).

사용법:
  python -X utf8 session_stall_check.py <세션명>
  python -X utf8 session_stall_check.py <세션명> --threshold-min 15

출력(한 줄): state, status, pid 유무, 마지막 기록 경과, 분류, 판정.
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
    """같은 이름이 여러 건이면 pid 있는(살아있는) 것 가운데 startedAt이 가장 큰 것(실제로 메시지를
    받는 쪽)을 쓰고, pid 있는 게 없으면 전체에서 startedAt이 가장 큰 것을 쓴다."""
    candidates = [a for a in agents if a.get('name') == name]
    if not candidates:
        return None
    with_pid = [a for a in candidates if a.get('pid')]
    pool = with_pid if with_pid else candidates
    return max(pool, key=lambda a: a.get('startedAt', 0))


def categorize(rec):
    """(분류 키, 한국어 라벨). claude-agents-board의 categorize와 같은 순서·기준."""
    state, status = rec.get('state'), rec.get('status')
    if state == 'blocked' or status == 'waiting':
        return 'blocked', '사람 입력 대기'
    if rec.get('pid'):
        if status == 'busy':
            return 'busy', '작업 중'
        if status == 'idle' and state == 'working':
            return 'resident', '할 일 남은 대기(루프·예약 등)'
        return 'idle', '지시 대기'
    if state == 'failed':
        return 'gone_failed', '프로세스 없음(마지막 상태: 실패)'
    if state == 'done':
        return 'gone_done', '프로세스 없음(마지막 상태: 완료)'
    return 'gone_other', '프로세스 없음(마지막 상태: %s)' % (state or '없음')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('session_name')
    ap.add_argument('--threshold-min', type=float, default=DEFAULT_THRESHOLD_MIN,
                    help='작업 중(busy)인데 기록이 이만큼 안 바뀌면 멈춤 의심으로 표시(분), 기본 %d' % DEFAULT_THRESHOLD_MIN)
    args = ap.parse_args()

    agents = run_claude_agents_all()
    record = find_agent_record(agents, args.session_name)
    if record is None:
        print('세션: %s | 조회 결과: claude agents 목록에 없음(이름 오타 또는 기록 정리됨)' % args.session_name)
        sys.exit(1)

    key, label = categorize(record)
    session_id = record.get('sessionId')
    mtime = transcript_mtime(session_id) if session_id else None
    idle_min = None if mtime is None else (time.time() - mtime) / 60
    idle_text = 'transcript 없음' if idle_min is None else '%.0f분 전' % idle_min

    if key == 'blocked':
        verdict = '재요청하지 말고 사람에게 알림(조회 순간 값이라 조치 전 한 번 더 확인)'
    elif key == 'busy':
        if idle_min is not None and idle_min >= args.threshold_min:
            verdict = '작업 중이나 기록이 %.0f분째 그대로 — 오래 걸리는 작업이거나 멈춤 의심, 사람이 확인' % idle_min
        else:
            verdict = '정상 — 끝날 때까지 기다림'
        # busy는 재요청 대상이 아니다(메시지는 다음 턴에 들어간다).
    elif key in ('resident', 'idle'):
        verdict = '정상 — 재요청 가능'
    else:
        verdict = '메시지가 닿지 않음 — 보내려면 session-wake로 먼저 깨움'

    print('세션: %s | state: %s | status: %s | pid: %s | 마지막 기록: %s | 분류: %s | 판정: %s' % (
        args.session_name, record.get('state') or '없음', record.get('status') or '없음',
        '있음' if record.get('pid') else '없음', idle_text, label, verdict))


if __name__ == '__main__':
    main()
