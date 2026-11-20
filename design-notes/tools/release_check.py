# -*- coding: utf-8 -*-
"""release_check.py — 출시 관문 2(약속과 실제가 맞나)를 기계로 한 번에 점검한다.

design-notes/tasks/release-0.2.0/checklist.md의 관문 2가 정본이다. 읽기 전용이다(아무것도 고치지 않는다).

실행(저장소 루트에서):
    python3 design-notes/tools/release_check.py

점검 항목:
  1. 규칙이 부르는 도구가 공개판에 있는가  — rules/의 `*.ps1`과 "`이름` 스킬" 언급을 skills/와 대조
  2. 문서 안의 상대 링크가 깨지지 않았는가 — 저장소의 모든 .md
  3. 서술 린터                            — README·docs·rules·skills (알려진 오탐 제외)
  4. shebang                              — skills/·examples/의 스크립트 첫 줄
  5. 기밀 토큰                            — .git/secret-blocklist가 있으면 추적·신규 파일 전부(토큰 값은 출력하지 않음)
  6. 작업 기록                            — design-notes/tasks/*/에 blueprint.md·completion-report.md, 보고서에 새 맥락 재검증
  7. 플러그인 검증                        — `claude plugin validate .` (명령이 없으면 건너뜀)

각 항목은 통과/실패/건너뜀과 근거를 출력하고, 실패가 하나라도 있으면 종료 코드 1로 끝난다.
"""
import glob
import os
import re
import subprocess
import sys
from urllib.parse import unquote

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))

# 서술 린터의 알려진 오탐: (파일 끝부분, 줄 번호 없이 단어)
KNOWN_LINT_FP = [
    ('04-브랜치전략-이중실적장부.md', '도장'),
    ('05-검증-통합-릴리스결정.md', '분배'),
    ('논제-backlog.md', None),
    ('QUICKSTART.md', None),
    ('README.md', '당신'),
    ('12단계-워크트리사용규칙.md', '조립'),
    ('00-핵심규칙요약.md', '조립'),
    ('seosul-lint/SKILL.md', None),        # 린터가 잡는 단어를 예로 든 문서
    ('6단계-Agent간소통규칙.md', '분해'),   # '구분해'의 부분 일치
    ('pending-status-check/SKILL.md', '분해'),
]


def rel(p):
    return os.path.relpath(p, ROOT)


def read(p):
    with open(p, encoding='utf-8', errors='ignore') as f:
        return f.read()


def git_files():
    def ls(*a):
        r = subprocess.run(['git', '-c', 'core.quotepath=false', '-C', ROOT, *a], capture_output=True, text=True)
        return [x for x in r.stdout.split('\0') if x]
    files = ls('ls-files', '-z') + ls('ls-files', '--others', '--exclude-standard', '-z')
    return sorted({f for f in files if os.path.isfile(os.path.join(ROOT, f))})


# 원본 SI에서 쓰던 도구 이름. 공개판(skills/)에 없으면서 규칙이 부르면, 같은 줄에 "공개판에 없음" 표시가 있어야 한다.
ORIGINAL_TOOLS = ['api-spec-gen', 'effort-ledger', 'ops-report', 'scenario-verify', 'table-spec-convert',
                  'sscheck', 'server-status', 'docs-consolidate', 'blueprint-index', 'index-refresh',
                  'common-code-sync', 'unittest-assemble', 'md2html', 'check_render']
ABSENT_MARK = '공개판에 없음'


def check_tools():
    skills = {d for d in os.listdir(os.path.join(ROOT, 'skills')) if os.path.isdir(os.path.join(ROOT, 'skills', d))}
    found = {}
    for p in sorted(glob.glob(os.path.join(ROOT, 'rules', '*.md'))):
        for i, line in enumerate(read(p).splitlines(), 1):
            if ABSENT_MARK in line:
                continue
            where = '%s:%d' % (os.path.basename(p)[13:30], i)
            for m in re.finditer(r'([A-Za-z0-9_.-]+\.ps1)', line):
                found.setdefault(m.group(1), []).append(where)
            if re.search(r'<공유문서 루트>\\scripts\\[A-Za-z]', line):  # 도구 폴더를 가리킬 때만(일반 위치 규칙 AR-11은 제외)
                found.setdefault('<공유문서 루트>\\scripts\\ 경로', []).append(where)
            for name in ORIGINAL_TOOLS:
                if name not in skills and re.search(r'(?<![\w-])%s(?![\w-])' % re.escape(name), line):
                    found.setdefault(name, []).append(where)
    if not found:
        return True, ['규칙이 부르는 원본 도구는 모두 공개판에 있거나 "공개판에 없음"으로 표시됐다']
    out = ['공개판에 없는데 표시 없이 부르는 것 %d종:' % len(found)]
    for k, v in sorted(found.items()):
        out.append('  %s (%d곳) %s' % (k, len(v), ', '.join(v[:4])))
    return False, out


def check_links(files):
    bad = []
    for f in files:
        if not f.endswith('.md'):
            continue
        p = os.path.join(ROOT, f)
        code = False
        for i, line in enumerate(read(p).splitlines(), 1):
            if line.lstrip().startswith('```'):
                code = not code
                continue
            if code:
                continue
            line = re.sub(r'`[^`]*`', '', line)  # 코드 표기 안의 예시는 링크가 아니다
            for m in re.finditer(r'\]\(([^)\s]+)\)', line):
                t = m.group(1)
                if re.match(r'^[a-z]+:', t) or t.startswith('#'):
                    continue
                t = unquote(t.split('#', 1)[0])
                if not t:
                    continue
                target = os.path.normpath(os.path.join(os.path.dirname(p), t))
                if not os.path.exists(target):
                    bad.append('%s:%d → %s' % (f, i, m.group(1)))
    if not bad:
        return True, ['깨진 상대 링크 없음']
    return False, ['깨진 상대 링크 %d개:' % len(bad)] + ['  ' + b for b in bad[:30]]


def check_lint():
    linter = os.path.join(ROOT, 'skills', 'seosul-lint', 'seosul_lint.py')
    targets = [os.path.join(ROOT, x) for x in ('README.md', 'docs', 'rules', 'skills')]
    r = subprocess.run([sys.executable, linter] + targets, capture_output=True, text=True)
    hits = [l for l in r.stdout.splitlines() if re.match(r'^\S+:\d+ \[', l)]
    real = []
    for h in hits:
        fp = False
        for tail, word in KNOWN_LINT_FP:
            if h.split(':', 1)[0].endswith(tail) and (word is None or '"%s' % word in h):
                fp = True
        if not fp:
            real.append(h)
    if not real:
        return True, ['서술 린터: 알려진 오탐 %d건 외 0건' % len(hits)]
    return False, ['서술 린터 %d건(알려진 오탐 제외):' % len(real)] + ['  ' + os.path.relpath(h, ROOT) if os.path.isabs(h) else '  ' + h for h in real[:30]]


def check_shebang(files):
    bad = [f for f in files if f.startswith(('skills/', 'examples/')) and f.endswith(('.py', '.sh'))
           and read(os.path.join(ROOT, f)).startswith('#!')]
    if not bad:
        return True, ['skills/·examples/ 스크립트에 shebang 없음']
    return False, ['shebang이 있는 파일:'] + ['  ' + b for b in bad]


def check_secrets(files):
    bl = os.path.join(ROOT, '.git', 'secret-blocklist')
    if not os.path.isfile(bl):
        return None, ['.git/secret-blocklist 없음 — 건너뜀(이 PC에 블록리스트를 설치해야 점검된다)']
    toks = [l.strip() for l in read(bl).splitlines() if l.strip() and not l.strip().startswith('#')]
    hit = [f for f in files if any(t in read(os.path.join(ROOT, f)) for t in toks)]
    if not hit:
        return True, ['기밀 토큰 %d개, 파일 %d개 검사 → 0건' % (len(toks), len(files))]
    return False, ['기밀 토큰이 든 파일(토큰 값은 출력하지 않음):'] + ['  ' + h for h in hit]


def check_tasks():
    bad, n = [], 0
    for d in sorted(glob.glob(os.path.join(ROOT, 'design-notes', 'tasks', '*', ''))):
        name = os.path.basename(os.path.dirname(d))
        if name.startswith('release-'):
            continue
        n += 1
        bp, cr = os.path.join(d, 'blueprint.md'), os.path.join(d, 'completion-report.md')
        if not os.path.isfile(bp):
            bad.append('%s: blueprint.md 없음' % name)
        if not os.path.isfile(cr):
            bad.append('%s: completion-report.md 없음' % name)
        elif '새 맥락 재검증' not in read(cr):
            bad.append('%s: 완료보고서에 새 맥락 재검증 기록 없음' % name)
    if not bad:
        return True, ['작업 %d개 모두 청사진·완료보고서·재검증 기록 있음' % n]
    return False, bad


def check_validate():
    try:
        r = subprocess.run(['claude', 'plugin', 'validate', ROOT], capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as e:
        return None, ['claude 명령을 실행하지 못함 — 건너뜀 (%s)' % e]
    last = (r.stdout + r.stderr).strip().splitlines()[-3:]
    return r.returncode == 0, ['claude plugin validate 종료 코드 %d' % r.returncode] + ['  ' + l for l in last]


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass
    files = git_files()
    checks = [
        ('1 규칙이 부르는 도구', check_tools),
        ('2 상대 링크', lambda: check_links(files)),
        ('3 서술 린터', check_lint),
        ('4 shebang', lambda: check_shebang(files)),
        ('5 기밀 토큰', lambda: check_secrets(files)),
        ('6 작업 기록', check_tasks),
        ('7 플러그인 검증', check_validate),
    ]
    failed = 0
    for title, fn in checks:
        ok, lines = fn()
        mark = '통과' if ok else ('건너뜀' if ok is None else '실패')
        if ok is False:
            failed += 1
        print('[%s] %s' % (mark, title))
        for l in lines:
            print('    ' + l)
    print('\n실패 %d개' % failed)
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
