# -*- coding: utf-8 -*-
# Copyright 2026 Baek Ga-hui (neisii) - https://github.com/neisii/harness-naroo
# SPDX-License-Identifier: Apache-2.0
"""
survey_gen.py — 사람에게 물을 결정을 HTML 설문으로 만들고, 답변을 기록·관리하는 도구.

설문 하나는 폴더 하나다. 상태는 폴더 안 survey.json에서 관리하고, 파일은 옮기지 않는다.

  <설문 루트>/                          (기본 ./docs/surveys/, --root로 바꿈)
    index.md                            설문 목록(미응답 먼저)
    YYYY-MM-DD-NN[-짧은이름]/            설문ID = 폴더 이름
      survey.json                       입력 + 관리 칸(status·createdAt·answeredAt·closedAt·closeNote)
      survey.html                       사람이 여는 설문 화면
      answers.md                        record가 만드는 답변 기록

하위 명령:
  new    --input <질문.json>                 검증 후 폴더·survey.json·survey.html 생성
  record <설문ID> --input <답변.txt>         답변 텍스트를 읽어 answers.md 저장, 상태 "응답됨"
  close  <설문ID> --note "<반영한 곳>"        상태 "반영 완료"
  index                                      index.md 다시 만들기(다른 명령은 자동으로 함께 갱신)

상태 흐름: 미응답 -> 응답됨(record) -> 반영 완료(close)

입력 JSON(질문.json):
  title(필수) / note(선택) / slug(선택, 폴더 이름에 붙일 짧은 이름)
  items[]: id, title, background, options[{key,label}] (2개 이상),
           recommend(선택, options의 key 중 하나), recommendReason(선택),
           hold(선택), movedTo(선택, 이 문항을 옮긴 설문ID)
  관리 칸(status 이하)은 도구가 채우므로 입력에 넣지 않는다.

Python 표준 라이브러리만 쓴다. macOS/Linux/Windows 공용.
"""
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = SCRIPT_DIR / 'template.html'
PLACEHOLDER = '__SURVEY_DATA_JSON__'
DEFAULT_ROOT = Path('docs') / 'surveys'

SURVEY_JSON = 'survey.json'
SURVEY_HTML = 'survey.html'
ANSWERS_MD = 'answers.md'
INDEX_MD = 'index.md'

STATUS_OPEN = '미응답'
STATUS_ANSWERED = '응답됨'
STATUS_CLOSED = '반영 완료'

# 관리 칸: 입력 JSON에는 없고, 도구가 채운다.
MANAGED_KEYS = ('status', 'createdAt', 'answeredAt', 'closedAt', 'closeNote')

ID_RE = re.compile(r'^(\d{4}-\d{2}-\d{2})-(\d{2})(?:-(.+))?$')
NO_CHOICE = '(선택 없음)'


# ---------------------------------------------------------------- 공통

def read_text(path):
    with open(path, encoding='utf-8-sig') as f:
        return f.read()


def write_text(path, content):
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(content)


def now_str():
    return datetime.now().strftime('%Y-%m-%d %H:%M')


def load_survey(folder):
    return json.loads(read_text(folder / SURVEY_JSON))


def save_survey(folder, data):
    write_text(folder / SURVEY_JSON, json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def fail(msg, code=1):
    print(msg)
    raise SystemExit(code)


def find_survey_folder(root, survey_id):
    """설문ID(폴더 이름)로 폴더를 찾는다. 경로 조각이 섞이면 거부한다."""
    if not survey_id or survey_id != Path(survey_id).name or not ID_RE.match(survey_id):
        fail('설문ID 형식이 아닙니다: %s (예: 2026-11-20-01-짧은이름)' % survey_id)
    folder = root / survey_id
    if not (folder / SURVEY_JSON).is_file():
        fail('설문을 찾을 수 없습니다: %s' % (folder / SURVEY_JSON))
    return folder


# ---------------------------------------------------------------- 검증

def validate(data):
    errors = []
    if not isinstance(data, dict):
        return ['최상위가 JSON 객체가 아님']
    if not data.get('title'):
        errors.append('title 없음')
    items = data.get('items')
    if not items or not isinstance(items, list):
        errors.append('items 없음(또는 빈 배열)')
        return errors
    seen_ids = set()
    for i, it in enumerate(items):
        if not isinstance(it, dict):
            errors.append('items[%d]: 객체가 아님' % i)
            continue
        where = 'items[%d](id=%s)' % (i, it.get('id'))
        if not it.get('id'):
            errors.append('%s: id 없음' % where)
        elif it['id'] in seen_ids:
            errors.append('%s: id 중복' % where)
        else:
            seen_ids.add(it['id'])
        if not it.get('title'):
            errors.append('%s: title 없음' % where)
        if not it.get('background'):
            errors.append('%s: background 없음' % where)
        opts = it.get('options')
        if not opts or not isinstance(opts, list) or len(opts) < 2:
            errors.append('%s: options가 2개 미만(선택지는 최소 2개)' % where)
            opts = None
        else:
            keys = [o.get('key') if isinstance(o, dict) else None for o in opts]
            if len(set(keys)) != len(keys):
                errors.append('%s: options key 중복' % where)
            for o in opts:
                if not isinstance(o, dict) or not o.get('key') or not o.get('label'):
                    errors.append('%s: options 항목에 key/label 누락' % where)
        rec = it.get('recommend')
        if rec and opts and rec not in [o.get('key') for o in opts if isinstance(o, dict)]:
            errors.append('%s: recommend(%s)가 options key에 없음' % (where, rec))
    return errors


# ---------------------------------------------------------------- 폴더·순번

def sanitize_slug(slug):
    """폴더 이름에 쓸 수 없는 글자를 걷어 낸다. 다 걷히면 빈 문자열."""
    s = re.sub(r'[\\/:*?"<>|\s]+', '-', str(slug or '').strip())
    return s.strip('-.')


def next_survey_id(root, date_str, slug):
    max_n = 0
    if root.is_dir():
        for p in root.iterdir():
            m = ID_RE.match(p.name)
            if m and m.group(1) == date_str:
                max_n = max(max_n, int(m.group(2)))
    n = max_n + 1
    if n > 99:
        fail('같은 날 설문이 99개를 넘었습니다(순번은 2자리).')
    sid = '%s-%02d' % (date_str, n)
    return sid + ('-' + slug if slug else '')


def render_html(data):
    template = read_text(TEMPLATE_PATH)
    if PLACEHOLDER not in template:
        raise RuntimeError('template.html에 %s 자리표시자가 없음(템플릿이 바뀐 것 같다)' % PLACEHOLDER)
    # 화면에는 입력 필드만 넣는다(관리 칸 제외).
    view = {k: v for k, v in data.items() if k not in MANAGED_KEYS}
    data_json = json.dumps(view, ensure_ascii=False, indent=2)
    data_json = data_json.replace('</', '<\\/')  # <script> 안에서 태그가 닫히지 않게
    if template.count(PLACEHOLDER) != 1:
        raise RuntimeError('template.html에 %s 자리표시자가 정확히 한 번 있어야 함(템플릿이 바뀐 것 같다)' % PLACEHOLDER)
    return template.replace(PLACEHOLDER, data_json)


# ---------------------------------------------------------------- new

def cmd_new(args, root):
    try:
        data = json.loads(read_text(args.input))
    except (OSError, ValueError) as e:
        fail('입력 파일을 읽지 못함: %s (%s)' % (args.input, e))
    if isinstance(data, dict) and isinstance(data.get('items'), list):
        # 번호는 문자열로 맞춘다. 답변 텍스트에서 읽은 번호는 늘 문자열이라, 정수로 두면 대조가 어긋난다.
        for it in data['items']:
            if isinstance(it, dict) and it.get('id') is not None and not isinstance(it.get('id'), str):
                it['id'] = str(it['id'])
    errors = validate(data)
    if errors:
        print('입력 오류 — 생성하지 않음:')
        for e in errors:
            print('  - ' + e)
        raise SystemExit(1)

    slug = sanitize_slug(data.get('slug'))
    sid = next_survey_id(root, datetime.now().strftime('%Y-%m-%d'), slug)
    folder = root / sid

    data = {k: v for k, v in data.items() if k not in MANAGED_KEYS}
    data['status'] = STATUS_OPEN
    data['createdAt'] = now_str()
    data['answeredAt'] = ''
    data['closedAt'] = ''
    data['closeNote'] = ''

    html = render_html(data)  # 템플릿 문제는 폴더를 만들기 전에 드러나게 한다
    folder.mkdir(parents=True, exist_ok=False)
    save_survey(folder, data)
    write_text(folder / SURVEY_HTML, html)

    print('생성: %s' % folder)
    print('  설문ID: %s' % sid)
    print('  설문 화면: %s' % (folder / SURVEY_HTML))
    print('문항 %d개. 사람에게 survey.html 경로를 전달하세요.' % len(data['items']))
    build_index(root)


# ---------------------------------------------------------------- record

_HEADER_RE = re.compile(r'^\[(.*) 응답\]\s*$')
_FOOTER_RE = re.compile(r'^미응답:\s*(.*?)\s*$')
_CHOICE_RE = re.compile(r'^(\S+?)\.\s+(.*)$')


def _split_choice(tail):
    """'A. 라벨' 또는 '(선택 없음)'을 (key, label)로. 선택 없음이면 (None, '')."""
    tail = tail.strip()
    if tail == NO_CHOICE:
        return None, ''
    m = _CHOICE_RE.match(tail)
    if m:
        return m.group(1), m.group(2)
    return tail, ''


def parse_answer_text(text, survey):
    """템플릿 build()가 만드는 답변 텍스트를 읽는다.
    돌려주는 값: (제목 or None, {id: {'title','key','label','memo'}}, 순서, 미응답 id 목록 or None)"""
    known = {it['id']: it for it in survey['items']}
    title = None
    entries = {}
    order = []
    footer = None
    cur = None
    pending_blank = 0

    for raw in text.replace('\r\n', '\n').replace('\r', '\n').split('\n'):
        line = raw.rstrip()
        if line.startswith('   ') and cur is not None:
            body = line[3:]
            if pending_blank:
                cur['memo_lines'].extend([''] * pending_blank)
                pending_blank = 0
            if not cur['memo_lines'] and body.startswith('메모:'):
                body = body[3:].lstrip()
            cur['memo_lines'].append(body)
            continue
        if not line.strip():
            if cur is not None and cur['memo_lines']:
                pending_blank += 1
            continue
        pending_blank = 0

        m = _HEADER_RE.match(line)
        if m and title is None and not entries:
            title = m.group(1)
            cur = None
            continue
        m = _FOOTER_RE.match(line)
        if m:
            val = m.group(1)
            footer = [] if val in ('', '없음') else [x.strip() for x in val.split(',') if x.strip()]
            cur = None
            continue

        # 문항 줄. 알려진 문항은 "<id>. <제목> → " 접두로 먼저 찾는다(제목·라벨에 화살표가 있어도 안전).
        found = None
        for iid, it in known.items():
            prefix = '%s. %s → ' % (iid, it['title'])
            if line.startswith(prefix):
                found = (iid, it['title'], line[len(prefix):])
                break
        if found is None:
            m = re.match(r'^(\S+?)\.\s+(.*) → (.*)$', line)
            if m:
                found = (m.group(1), m.group(2), m.group(3))
        if found is None:
            cur = None
            continue
        iid, ititle, tail = found
        key, label = _split_choice(tail)
        cur = {'id': iid, 'title': ititle, 'key': key, 'label': label, 'memo_lines': []}
        if iid not in entries:
            order.append(iid)
        entries[iid] = cur

    for e in entries.values():
        e['memo'] = '\n'.join(e.pop('memo_lines')).strip()
    return title, entries, order, footer


def render_answers_md(survey, sid, entries, footer, warnings):
    lines = ['# %s — 답변' % survey['title'], '',
             '- 설문ID: %s' % sid,
             '- 기록 시각: %s' % now_str(), '']
    for it in survey['items']:
        e = entries.get(it['id'])
        lines.append('## %s. %s' % (it['id'], it['title']))
        lines.append('')
        if e and e['key']:
            opt = next((o for o in it['options'] if o['key'] == e['key']), None)
            label = opt['label'] if opt else e['label']
            suffix = '' if opt else ' (선택지에 없는 답)'
            lines.append('- 선택: **%s. %s**%s' % (e['key'], label, suffix) if label
                         else '- 선택: **%s**%s' % (e['key'], suffix))
        else:
            lines.append('- 선택: %s' % NO_CHOICE)
        memo = e['memo'] if e else ''
        if memo:
            lines.append('- 메모:')
            for ml in memo.split('\n'):
                lines.append('  > %s' % ml if ml else '  >')
        lines.append('')
    if warnings:
        lines.append('## 대조 경고')
        lines.append('')
        for w in warnings:
            lines.append('- %s' % w)
        lines.append('')
    return '\n'.join(lines)


def cmd_record(args, root):
    folder = find_survey_folder(root, args.survey_id)
    survey = load_survey(folder)
    if survey.get('status') == STATUS_CLOSED:
        fail('이미 "%s" 상태라 다시 기록하지 않습니다: %s' % (STATUS_CLOSED, args.survey_id))
    try:
        text = read_text(args.input)
    except OSError as e:
        fail('답변 파일을 읽지 못함: %s (%s)' % (args.input, e))

    title, entries, order, footer = parse_answer_text(text, survey)
    if not entries and footer is None:
        fail('읽을 수 있는 답변이 없습니다. 설문 화면의 "답변 생성"으로 만든 텍스트를 그대로 넣어 주세요.')

    warnings = []
    if title is not None and title != survey['title']:
        warnings.append('설문 제목이 다름: 답변 "%s" / 설문 "%s"' % (title, survey['title']))
    elif title is None:
        warnings.append('첫 줄([제목 응답])을 찾지 못해 제목은 대조하지 못함')

    known = {it['id']: it for it in survey['items']}
    for iid in order:
        if iid not in known:
            warnings.append('설문에 없는 문항 번호: %s' % iid)
    footer_ids = set(footer or [])
    for iid in footer_ids:
        if iid not in known:
            warnings.append('"미응답"에 적힌 번호가 설문에 없음: %s' % iid)
    for iid in order:
        e = entries[iid]
        if iid in known and e['key']:
            keys = [o['key'] for o in known[iid]['options']]
            if e['key'] not in keys:
                warnings.append('문항 %s: 선택 "%s"가 선택지(%s)에 없음' % (iid, e['key'], ', '.join(keys)))
    for it in survey['items']:
        iid = it['id']
        e = entries.get(iid)
        if e is None and iid not in footer_ids:
            warnings.append('문항 %s: 답변 텍스트에 없음(빠짐)' % iid)
        elif (e is None or not e['key']) or iid in footer_ids:
            warnings.append('문항 %s: 미응답(선택 없음)' % iid)

    write_text(folder / ANSWERS_MD, render_answers_md(survey, args.survey_id, entries, footer, warnings))
    prev_status = survey.get('status') or STATUS_OPEN
    survey['status'] = STATUS_ANSWERED
    survey['answeredAt'] = now_str()
    save_survey(folder, survey)

    print('기록: %s' % (folder / ANSWERS_MD))
    print('상태: %s -> %s' % (prev_status, STATUS_ANSWERED))
    if warnings:
        print('경고 %d건:' % len(warnings))
        for w in warnings:
            print('  - ' + w)
    else:
        print('경고 없음.')
    build_index(root)


# ---------------------------------------------------------------- close

def cmd_close(args, root):
    folder = find_survey_folder(root, args.survey_id)
    survey = load_survey(folder)
    if survey.get('status') == STATUS_OPEN:
        print('경고: 아직 답변이 기록되지 않은(%s) 설문입니다. 그래도 닫습니다.' % STATUS_OPEN)
    survey['status'] = STATUS_CLOSED
    survey['closedAt'] = now_str()
    survey['closeNote'] = args.note or ''
    save_survey(folder, survey)
    print('상태: %s (%s)' % (STATUS_CLOSED, args.survey_id))
    if survey['closeNote']:
        print('반영한 곳: %s' % survey['closeNote'])
    build_index(root)


# ---------------------------------------------------------------- index

def _cell(text):
    return str(text).replace('|', '\\|').replace('\r', ' ').replace('\n', ' ')


def scan_surveys(root):
    entries = []
    if not root.is_dir():
        return entries
    for p in root.iterdir():
        m = ID_RE.match(p.name)
        if not m or not (p / SURVEY_JSON).is_file():
            continue
        try:
            data = load_survey(p)
        except (OSError, ValueError) as e:
            print('경고: %s를 읽지 못해 인덱스에서 뺍니다 (%s)' % (p / SURVEY_JSON, e), file=sys.stderr)
            continue
        moved = {}
        for it in data.get('items', []):
            if it.get('movedTo'):
                moved.setdefault(it['movedTo'], []).append(str(it.get('id')))
        notes = ['문항 %s -> %s로 이동' % (', '.join(ids), dst) for dst, ids in moved.items()]
        if data.get('closeNote'):
            notes.append('반영: %s' % data['closeNote'])
        entries.append({
            'id': p.name,
            'sortkey': (m.group(1), int(m.group(2))),
            'status': data.get('status', STATUS_OPEN),
            'title': data.get('title', ''),
            'count': len(data.get('items', [])),
            'date': m.group(1),
            'hasAnswers': (p / ANSWERS_MD).is_file(),
            'note': '; '.join(notes),
        })
    # 미응답 먼저, 그 안과 나머지는 날짜·순번 내림차순
    entries.sort(key=lambda e: e['sortkey'], reverse=True)
    entries.sort(key=lambda e: 0 if e['status'] == STATUS_OPEN else 1)
    return entries


def render_index_md(entries):
    counts = {STATUS_OPEN: 0, STATUS_ANSWERED: 0, STATUS_CLOSED: 0}
    for e in entries:
        counts[e['status']] = counts.get(e['status'], 0) + 1
    lines = [
        '# 설문 인덱스',
        '',
        'survey-gen이 관리하는 설문의 현재 상태를 모은 표다. 미응답을 맨 위에 두고, 나머지는 만든 날·순번 내림차순이다. '
        '직접 고치지 않는다(`survey_gen.py index`가 다시 만든다).',
        '',
        '갱신 시각: %s' % now_str(),
        '',
        '| 상태 | 제목 | 문항 수 | 만든 날 | 설문 링크 | 답변 링크 | 비고 |',
        '|---|---|---|---|---|---|---|',
    ]
    for e in entries:
        # 규칙 AR-12: 사람이 읽는 md의 로컬 링크는 한글을 퍼센트 인코딩한다.
        href = quote(e['id'])
        survey_link = '[%s](%s/%s)' % (SURVEY_HTML, href, SURVEY_HTML)
        answer_link = '[%s](%s/%s)' % (ANSWERS_MD, href, ANSWERS_MD) if e['hasAnswers'] else '-'
        lines.append('| %s | %s | %d | %s | %s | %s | %s |' % (
            e['status'], _cell(e['title']), e['count'], e['date'], survey_link, answer_link, _cell(e['note'])))
    lines.append('')
    lines.append('합계: %s %d · %s %d · %s %d' % (
        STATUS_OPEN, counts[STATUS_OPEN], STATUS_ANSWERED, counts[STATUS_ANSWERED],
        STATUS_CLOSED, counts[STATUS_CLOSED]))
    lines.append('')
    return '\n'.join(lines)


_TIME_LINE_RE = re.compile(r'^갱신 시각:.*$', re.M)


def write_if_changed(path, content):
    """갱신 시각 줄을 뺀 내용이 같으면 쓰지 않는다. 쓰면 True."""
    if path.is_file():
        old = read_text(path)
        if _TIME_LINE_RE.sub('', old) == _TIME_LINE_RE.sub('', content):
            return False
    write_text(path, content)
    return True


def build_index(root):
    entries = scan_surveys(root)
    path = root / INDEX_MD
    if not entries and not path.is_file():
        print('인덱스: 설문이 없어 만들지 않음')
        return
    root.mkdir(parents=True, exist_ok=True)
    if write_if_changed(path, render_index_md(entries)):
        print('인덱스 갱신: %s (%d건)' % (path, len(entries)))
    else:
        print('인덱스 변경 없음(내용 동일, 쓰기 생략): %d건' % len(entries))


def cmd_index(args, root):
    build_index(root)


# ---------------------------------------------------------------- main

def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8')
        except (AttributeError, ValueError):
            pass

    ap = argparse.ArgumentParser(description='사람에게 물을 결정을 설문으로 만들고 답변을 기록·관리한다.')
    ap.add_argument('--root', default=None, help='설문 루트(기본 ./docs/surveys/)')
    sub = ap.add_subparsers(dest='cmd', required=True)
    # --root는 하위 명령 뒤에 둬도 받는다.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument('--root', dest='sub_root', default=None, help='설문 루트(기본 ./docs/surveys/)')

    p = sub.add_parser('new', help='설문 만들기', parents=[common])
    p.add_argument('--input', required=True, help='질문 JSON 파일')
    p.set_defaults(func=cmd_new)

    p = sub.add_parser('record', help='답변 텍스트 기록', parents=[common])
    p.add_argument('survey_id', help='설문ID(폴더 이름)')
    p.add_argument('--input', required=True, help='답변 텍스트 파일')
    p.set_defaults(func=cmd_record)

    p = sub.add_parser('close', help='반영 완료 처리', parents=[common])
    p.add_argument('survey_id', help='설문ID(폴더 이름)')
    p.add_argument('--note', default='', help='결정을 반영한 곳(커밋·문서)')
    p.set_defaults(func=cmd_close)

    p = sub.add_parser('index', help='index.md 다시 만들기', parents=[common])
    p.set_defaults(func=cmd_index)

    args = ap.parse_args()
    root_arg = args.sub_root or args.root
    root = Path(root_arg) if root_arg else DEFAULT_ROOT
    args.func(args, root)


if __name__ == '__main__':
    main()
