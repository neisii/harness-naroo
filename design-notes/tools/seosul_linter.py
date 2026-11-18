#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""seosul_linter — design-notes 전용 얇은 shim.

실제 구현은 공개 플러그인 스킬로 승격됐다: `skills/seosul-lint/seosul_lint.py`.
이 shim 은 그 스킬을 design-notes 기본값(사전·제외 파일)으로 호출만 한다 — 구현은 한 곳,
드리프트 없음. design-notes 안에서는 예전 그대로 쓰면 된다:

  python3 design-notes/tools/seosul_linter.py            # design-notes/ 최상위 *.md
  python3 design-notes/tools/seosul_linter.py design-notes/   # 하위까지
  python3 design-notes/tools/seosul_linter.py --selftest

- 사전: design-notes/번역투-교정사전.md (정본). 스킬 쪽 사전은 이걸 떠 담은 배포용 사본이다.
- 제외: 사전 + 쉬운-글쓰기-기준.md · 08-서술규칙.md · HANDOFF.md · CLAUDE.md (서술 규칙 정본·사전류; CLAUDE.md는 '자주 새는 목록'에 금칙어를 예시로 담음).
"""
import importlib.util
import os
import sys

NOTES_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(NOTES_DIR)
SKILL_SCRIPT = os.path.join(REPO_ROOT, 'skills', 'seosul-lint', 'seosul_lint.py')

if not os.path.isfile(SKILL_SCRIPT):
    print('[오류] 스킬 구현을 찾지 못했습니다: %s' % SKILL_SCRIPT, file=sys.stderr)
    sys.exit(2)

spec = importlib.util.spec_from_file_location('seosul_lint', SKILL_SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

inject = [
    '--dict', os.path.join(NOTES_DIR, '번역투-교정사전.md'),
    '--skip', '쉬운-글쓰기-기준.md,08-서술규칙.md,HANDOFF.md,CLAUDE.md',
]
user_args = sys.argv[1:]
# 인자를 하나도 안 주면 예전 기본(=design-notes/ 최상위 *.md)을 이어간다.
if not user_args:
    user_args = sorted(os.path.join(NOTES_DIR, n) for n in os.listdir(NOTES_DIR)
                       if n.lower().endswith('.md') and os.path.isfile(os.path.join(NOTES_DIR, n)))

sys.exit(mod.main(inject + user_args))
