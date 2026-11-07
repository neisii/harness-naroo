#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""safe_delete — 삭제 도구(기본은 휴지통 이동). `rm -rf` 대신 이걸 쓴다.

사용법:
  python3 safe_delete.py <삭제할 파일 또는 폴더>                 # 휴지통 이동(기본)
  python3 safe_delete.py <경로> --permanent                      # 영구 삭제(사람 확인 후에만)
  python3 safe_delete.py <경로> --force                          # 보호 대상 거부를 무시(사람 확인 후에만)
  python3 safe_delete.py <경로> --protect <폴더> [--protect ...] # 이번 호출에 보호 폴더 추가

보호 대상(공용 산출 폴더 '자체'; 그 하위 폴더는 허용):
  - 환경변수 SAFE_DELETE_PROTECTED (OS 경로 구분자로 여러 개: Unix ':' / Windows ';')
  - --protect 인자
  - 항상 보호: 파일시스템 루트, 홈 디렉터리
  새 공용 산출 폴더가 생기면 SAFE_DELETE_PROTECTED 에 추가한다.

종료 코드: 0 성공(또는 대상 없음), 1 보호 대상 거부, 2 삭제 실패.
OS별 휴지통: macOS=Finder(osascript), 실패 시 ~/.Trash 이동 / Linux=gio trash, 없으면 XDG 휴지통 /
Windows=SHFileOperation(FOF_ALLOWUNDO). 표준 라이브러리만 사용한다.
"""
import argparse
import ctypes
import datetime
import os
import shutil
import subprocess
import sys
import urllib.parse


def _norm(p):
    return os.path.normcase(os.path.abspath(p)).rstrip('\\/') or os.path.normcase(os.path.abspath(p))


def protected_set(extra):
    items = list(extra or [])
    env = os.environ.get('SAFE_DELETE_PROTECTED', '')
    items += [x for x in env.split(os.pathsep) if x.strip()]
    prot = set()
    for it in items:
        prot.add(_norm(it))
        prot.add(os.path.normcase(os.path.realpath(it)).rstrip('\\/'))
    # 항상 보호
    home = os.path.expanduser('~')
    for it in (home, os.path.abspath(os.sep)):
        prot.add(_norm(it))
        prot.add(os.path.normcase(os.path.realpath(it)).rstrip('\\/') or os.path.normcase(os.path.realpath(it)))
    return prot


def count_files(d):
    n = 0
    for _r, _d, files in os.walk(d):
        n += len(files)
    return n


def permanent_delete(path):
    if os.path.islink(path) or os.path.isfile(path):
        os.remove(path)
    else:
        shutil.rmtree(path)


# ---------------------------------------------------------------- 휴지통 (OS별)
def _unique(dest_dir, name):
    cand, i = os.path.join(dest_dir, name), 1
    stem, ext = os.path.splitext(name)
    while os.path.lexists(cand):
        cand = os.path.join(dest_dir, '%s %d%s' % (stem, i, ext))
        i += 1
    return cand


def trash_macos(path):
    script = ['on run argv', 'tell application "Finder" to delete (POSIX file (item 1 of argv) as alias)', 'end run']
    cmd = ['osascript']
    for line in script:
        cmd += ['-e', line]
    try:
        r = subprocess.run(cmd + [path], capture_output=True, timeout=60)
        if r.returncode == 0 and not os.path.lexists(path):
            return 'Finder 휴지통'
    except Exception:
        pass
    trash = os.path.join(os.path.expanduser('~'), '.Trash')
    os.makedirs(trash, exist_ok=True)
    shutil.move(path, _unique(trash, os.path.basename(path)))
    return '~/.Trash (osascript 실패로 폴백)'


def trash_linux(path):
    gio = shutil.which('gio')
    if gio:
        r = subprocess.run([gio, 'trash', '--', path], capture_output=True, timeout=60)
        if r.returncode == 0 and not os.path.lexists(path):
            return 'gio trash'
    base = os.environ.get('XDG_DATA_HOME') or os.path.join(os.path.expanduser('~'), '.local', 'share')
    files_dir, info_dir = os.path.join(base, 'Trash', 'files'), os.path.join(base, 'Trash', 'info')
    os.makedirs(files_dir, exist_ok=True)
    os.makedirs(info_dir, exist_ok=True)
    dest = _unique(files_dir, os.path.basename(path))
    name = os.path.basename(dest)
    info = ('[Trash Info]\nPath=%s\nDeletionDate=%s\n' % (
        urllib.parse.quote(os.path.abspath(path)), datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')))
    with open(os.path.join(info_dir, name + '.trashinfo'), 'w', encoding='utf-8') as f:
        f.write(info)
    shutil.move(path, dest)
    return 'XDG 휴지통 (%s)' % os.path.join(base, 'Trash')


def trash_windows(path):
    from ctypes import wintypes
    pack = 8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 1

    # LPCWSTR 필드는 이중 널 종료 문자열을 다루지 못하므로 포인터를 c_void_p 로 직접 넣는다.
    class SHFILEOPSTRUCTW(ctypes.Structure):
        _pack_ = pack
        _fields_ = [('hwnd', wintypes.HWND), ('wFunc', wintypes.UINT), ('pFrom', ctypes.c_void_p),
                    ('pTo', ctypes.c_void_p), ('fFlags', ctypes.c_ushort), ('fAnyOperationsAborted', wintypes.BOOL),
                    ('hNameMappings', ctypes.c_void_p), ('lpszProgressTitle', ctypes.c_void_p)]
    FO_DELETE, FOF_SILENT, FOF_NOCONFIRMATION, FOF_ALLOWUNDO = 0x3, 0x4, 0x10, 0x40
    buf = ctypes.create_unicode_buffer(os.path.abspath(path) + '\0\0')  # pFrom 은 이중 널 종료
    raw = SHFILEOPSTRUCTW()
    raw.wFunc = FO_DELETE
    raw.pFrom = ctypes.addressof(buf)
    raw.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT
    rc = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(raw))
    if rc != 0 or raw.fAnyOperationsAborted:
        raise OSError('SHFileOperation 실패(코드 %d, 중단=%s)' % (rc, bool(raw.fAnyOperationsAborted)))
    return '휴지통'


def move_to_trash(path):
    if sys.platform == 'darwin':
        return trash_macos(path)
    if sys.platform == 'win32':
        return trash_windows(path)
    return trash_linux(path)


def main(argv):
    ap = argparse.ArgumentParser(description='삭제 도구(기본 휴지통 이동)')
    ap.add_argument('path')
    ap.add_argument('--permanent', action='store_true', help='영구 삭제(사람 확인 후에만)')
    ap.add_argument('--force', action='store_true', help='보호 대상 거부 무시(사람 확인 후에만)')
    ap.add_argument('--protect', action='append', default=[], help='보호할 공용 폴더 추가(반복 가능)')
    a = ap.parse_args(argv)

    if not os.path.lexists(a.path):  # glob 해석 없이 문자 그대로 검사(파일명의 [ ] * ? 안전)
        print('대상이 없습니다(이미 삭제됐거나 경로가 틀림): %s' % a.path)
        return 0
    resolved = os.path.abspath(a.path)

    if not a.force and (_norm(resolved) in protected_set(a.protect)
                        or os.path.normcase(os.path.realpath(resolved)).rstrip('\\/') in protected_set(a.protect)):
        print("거부: '%s'는 보호 대상(공용 산출 폴더 자체·홈·루트)입니다. 그 아래 하위 폴더만 지정하세요." % resolved)
        print('정말 이 폴더 자체를 지워야 하면(흔치 않음) 사람 확인 후 --force를 쓰세요.')
        return 1

    if os.path.isdir(resolved) and not os.path.islink(resolved):
        print("대상: 폴더 '%s' (파일 %d 개)" % (resolved, count_files(resolved)))
    else:
        print("대상: 파일 '%s'" % resolved)

    try:
        if a.permanent:
            print('영구 삭제 — 사람 확인을 받은 뒤에만 이 옵션을 쓰세요.')
            permanent_delete(resolved)
            print('영구 삭제 완료: %s' % resolved)
            return 0
        where = move_to_trash(resolved)
        print('휴지통으로 이동 완료 [%s]: %s' % (where, resolved))
        return 0
    except Exception as e:
        print('[실패] 삭제하지 못했습니다: %r' % e, file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
