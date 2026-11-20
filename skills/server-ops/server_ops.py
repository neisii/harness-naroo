"""server-ops: Spring Boot + Gradle 서버의 빌드·구동·종료·상태 조회 공용 실행기.

사용:
  python3 server_ops.py init [--dir <폴더>] [--name 이름 --port N [--health URL]] [--write] [--force]
  python3 server_ops.py build  <서버> [--dir <워크트리>] [--config <파일>]
  python3 server_ops.py start  <서버> [--dir <워크트리>] [--port N] [--timeout 120] [--ignore-memcheck]
  python3 server_ops.py stop   <서버> [--dir <워크트리>] [--port N] [--yes]
  python3 server_ops.py status [<서버>] [--dir <워크트리>] [--port N] [--json]

종료 코드: 0 정상, 1 오류(설정·인자·실행 실패), 2 적용 불가(init의 환경 점검 실패),
          3 포트 점유로 중단, 4 메모리 경고로 중단, 5 기동 시간 초과.
          build는 빌드 명령의 종료 코드를 그대로 돌려준다.
Python 표준 라이브러리만 쓴다. macOS/Linux/Windows 공용(Windows는 검증하지 않음).
"""
import argparse
import json
import re
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request

IS_WIN = os.name == 'nt'
CONFIG_REL = os.path.join('.claude', 'harness-servers.json')
RECORD_REL = os.path.join('.claude', 'server-ops')
NOT_APPLICABLE_MSG = ('이 스킬은 Spring Boot + Gradle 전용이라, '
                      '이 프로젝트에서는 환경 차이로 실행할 수 없다.')


def out(msg=''):
    print(msg)
    sys.stdout.flush()


# ---------- 공용 도구 ----------

def tail_lines(path, n=20):
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            return f.read().splitlines()[-n:]
    except OSError:
        return []


def port_listening(port, timeout=1.0):
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=timeout):
            return True
    except OSError:
        return False


def pid_alive(pid):
    if IS_WIN:
        try:
            r = subprocess.run(['tasklist', '/FI', 'PID eq %d' % pid, '/NH'],
                               capture_output=True, text=True, timeout=10)
            return any(len(c) > 1 and c[1] == str(pid) for c in (ln.split() for ln in r.stdout.splitlines()))
        except (OSError, subprocess.SubprocessError):
            return False
    try:
        os.waitpid(pid, os.WNOHANG)  # 우리가 띄운 자식이면 좀비를 거둔다
    except (ChildProcessError, OSError):
        pass
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def process_command(pid):
    """PID의 명령 줄을 돌려준다. 확인하지 못하면 빈 문자열."""
    try:
        if IS_WIN:
            r = subprocess.run(['tasklist', '/FI', 'PID eq %d' % pid, '/V', '/FO', 'CSV', '/NH'],
                               capture_output=True, text=True, timeout=10)
        else:
            r = subprocess.run(['ps', '-o', 'command=', '-p', str(pid)],
                               capture_output=True, text=True, timeout=10)
        return r.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ''


def kill_tree(pid, grace=10):
    """프로세스 그룹(트리)을 종료한다. 종료됐으면 True."""
    if IS_WIN:
        subprocess.run(['taskkill', '/PID', str(pid), '/T', '/F'],
                       capture_output=True, text=True)
    else:
        try:
            os.killpg(pid, signal.SIGTERM)
        except ProcessLookupError:
            return True
        except PermissionError:
            return False
        end = time.time() + grace
        while time.time() < end and pid_alive(pid):
            time.sleep(0.3)
        if pid_alive(pid):
            try:
                os.killpg(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            time.sleep(0.5)
    return not pid_alive(pid)


def run_text(args, cwd=None, timeout=10):
    try:
        r = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                           encoding='utf-8', errors='replace', timeout=timeout)
        return r.returncode, (r.stdout or '') + (r.stderr or '')
    except (OSError, subprocess.SubprocessError) as e:
        return -1, str(e)


def fmt_time(ts):
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ts))


# ---------- 적용 판단 (청사진 0절) ----------

def applicability(folder):
    """[(항목, 통과 여부, 상세)] 를 돌려준다."""
    res = []
    gw = 'gradlew.bat' if IS_WIN else 'gradlew'
    found = [n for n in ('gradlew', 'gradlew.bat') if os.path.isfile(os.path.join(folder, n))]
    ok = os.path.isfile(os.path.join(folder, gw))
    res.append(('Gradle 래퍼', ok,
                '`%s` 있음' % gw if ok else '`%s` 없음%s' % (
                    gw, (' (`%s`는 있음)' % ', '.join(found)) if found else '')))
    sb_ok, sb_detail = False, '`build.gradle`·`build.gradle.kts` 없음'
    for n in ('build.gradle', 'build.gradle.kts'):
        p = os.path.join(folder, n)
        if os.path.isfile(p):
            try:
                with open(p, 'r', encoding='utf-8', errors='replace') as f:
                    txt = f.read()
            except OSError:
                txt = ''
            if 'org.springframework.boot' in txt:
                sb_ok, sb_detail = True, '`%s`에 org.springframework.boot 있음' % n
                break
            sb_detail = '`%s`에 org.springframework.boot 없음' % n
    if not sb_ok:
        others = [n for n in ('package.json', 'pom.xml', 'Makefile') if os.path.isfile(os.path.join(folder, n))]
        if others:
            sb_detail += ' (`%s` 있음)' % ', '.join(others)
    res.append(('Spring Boot', sb_ok, sb_detail))
    code, o = run_text(['java', '-version'])
    first = o.strip().splitlines()[0] if o.strip() else ''
    res.append(('JDK', code == 0, first if code == 0 else '`java -version` 실행 안 됨'))
    return res


# ---------- 설정 ----------

class ConfigError(Exception):
    pass


def find_config(args):
    if args.config:
        return os.path.abspath(args.config)
    cand = [os.path.join(os.getcwd(), CONFIG_REL)]
    if args.dir:
        cand.append(os.path.join(os.path.abspath(args.dir), CONFIG_REL))
    for c in cand:
        if os.path.isfile(c):
            return c
    return cand[0]


def load_config(args):
    path = find_config(args)
    if not os.path.isfile(path):
        raise ConfigError('설정 파일이 없다: %s\n먼저 `init`으로 서버를 등록한다.' % path)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
    except (OSError, ValueError) as e:
        raise ConfigError('설정 파일을 읽지 못했다: %s (%s)' % (path, e))
    if not isinstance(cfg.get('servers'), dict) or not cfg['servers']:
        raise ConfigError('설정 파일에 servers가 없다: %s' % path)
    return path, cfg


def project_root_of(cfg_path):
    # <루트>/.claude/harness-servers.json 이면 루트, 아니면 설정 파일이 있는 폴더
    d = os.path.dirname(cfg_path)
    return os.path.dirname(d) if os.path.basename(d) == '.claude' else d


class Target:
    """서버 한 건의 실행 맥락(폴더·포트·기록 파일 경로)."""

    def __init__(self, name, spec, args, cfg, cfg_path):
        if not re.match(r'^[A-Za-z0-9._-]+$', name or '') or '..' in name:
            raise ConfigError('서버 이름 "%s"을 쓸 수 없다. 영문·숫자·`.`·`_`·`-`만 쓰고 `..`은 쓰지 않는다.' % name)
        self.name, self.spec = name, spec
        root = project_root_of(cfg_path)
        self.worktree = bool(args.dir)
        base = os.path.abspath(args.dir) if args.dir else root
        self.workdir = os.path.normpath(os.path.join(base, spec.get('dir', '.')))
        try:
            self.base_port = int(spec['port'])
        except (KeyError, ValueError, TypeError):
            raise ConfigError('서버 "%s"에 정수 port가 없다.' % name)
        offset = int(cfg.get('worktreePortOffset', 0) or 0)
        if args.port:
            self.port = args.port
        elif self.worktree:
            self.port = self.base_port + offset
        else:
            self.port = self.base_port
        self.records = os.path.join(root, RECORD_REL)
        self.pid_file = os.path.join(self.records, '%s-%d.pid' % (name, self.port))
        self.log_file = os.path.join(self.records, '%s-%d.log' % (name, self.port))
        self.build_log = os.path.join(self.records, '%s-build.log' % name)
        rec = os.path.realpath(self.records)
        for p in (self.pid_file, self.log_file, self.build_log):
            if os.path.dirname(os.path.realpath(p)) != rec:
                raise ConfigError('기록 파일이 기록 폴더(%s) 밖을 가리킨다.' % self.records)

    def sub(self, text):
        return (text or '').replace('{port}', str(self.port))

    def read_pid(self):
        try:
            with open(self.pid_file, 'r', encoding='utf-8') as f:
                return int(f.read().split()[0])
        except (OSError, ValueError, IndexError):
            return None


def pick_targets(args, names_all):
    if args.server:
        if args.server not in names_all:
            raise ConfigError('등록되지 않은 서버: %s (등록: %s)' % (args.server, ', '.join(names_all)))
        return [args.server]
    return list(names_all)


def make_targets(args, need_one):
    cfg_path, cfg = load_config(args)
    names = list(cfg['servers'].keys())
    if need_one and not args.server:
        if len(names) == 1:
            args.server = names[0]
        else:
            raise ConfigError('서버 이름을 준다. 등록: %s' % ', '.join(names))
    return [Target(n, cfg['servers'][n], args, cfg, cfg_path) for n in pick_targets(args, names)]


# ---------- init ----------

def cmd_init(args):
    folder = os.path.abspath(args.dir or os.getcwd())
    checks = applicability(folder)
    out('적용 판단 (%s)' % folder)
    for name, ok, detail in checks:
        out('  [%s] %s: %s' % ('통과' if ok else '실패', name, detail))
    failed = [c for c in checks if not c[1]]
    if failed:
        out('')
        out(NOT_APPLICABLE_MSG)
        out('맞지 않은 항목: ' + ', '.join('%s(%s)' % (c[0], c[2]) for c in failed))
        out('설정 파일을 만들지 않았다. 다른 빌드·구동 명령을 임의로 만들어 대신 실행하지 않는다.')
        return 2
    if not args.name or not args.port:
        out('')
        out('적용 판단을 통과했다. 서버 이름(--name)과 포트(--port)를 주면 설정 후보를 보여 준다.')
        out('예: init --name api --port 8090 [--health URL] [--write]')
        return 0
    gw = 'gradlew.bat' if IS_WIN else './gradlew'
    arg_q = '"--server.port={port}"' if IS_WIN else "'--server.port={port}'"
    spec = {
        'dir': '.',
        'build': '%s clean build -x test' % gw,
        'start': '%s bootRun --args=%s' % (gw, arg_q),
        'port': args.port,
        'health': args.health or 'http://127.0.0.1:{port}/actuator/health',
    }
    cfg_path = os.path.join(folder, CONFIG_REL)
    cfg = {'worktreePortOffset': 10000, 'servers': {args.name: spec}}
    exists = os.path.isfile(cfg_path)
    if exists:  # 기존 설정이 있으면 병합 후보를 만든다(덮어쓰기는 --force일 때만)
        try:
            with open(cfg_path, 'r', encoding='utf-8') as f:
                old = json.load(f)
        except (OSError, ValueError):
            old = None
        if args.write and not args.force:
            out('')
            out('설정 파일이 이미 있어 덮어쓰지 않았다: %s (덮어쓰려면 --force)' % cfg_path)
            return 1
        if isinstance(old, dict) and isinstance(old.get('servers'), dict) and args.force:
            old['servers'][args.name] = spec
            cfg = old
    text = json.dumps(cfg, ensure_ascii=False, indent=2)
    out('')
    out('설정 후보 (%s):' % cfg_path)
    out(text)
    if not args.write:
        out('')
        out('파일은 만들지 않았다. 확정하려면 같은 명령에 --write를 붙인다.')
        return 0
    os.makedirs(os.path.dirname(cfg_path), exist_ok=True)
    with open(cfg_path, 'w', encoding='utf-8') as f:
        f.write(text + '\n')
    out('')
    out('설정 파일을 썼다: %s' % cfg_path)
    out('기록 폴더 `.claude/server-ops/`는 커밋하지 않는다. .gitignore에 `.claude/server-ops/`를 추가한다.')
    return 0


# ---------- build ----------

def cmd_build(args):
    t = make_targets(args, True)[0]
    cmd = t.sub(t.spec.get('build'))
    if not cmd:
        raise ConfigError('서버 "%s"에 build 명령이 없다.' % t.name)
    if not os.path.isdir(t.workdir):
        raise ConfigError('작업 폴더가 없다: %s' % t.workdir)
    os.makedirs(t.records, exist_ok=True)
    out('빌드: %s' % cmd)
    out('폴더: %s' % t.workdir)
    with open(t.build_log, 'wb') as lf:
        try:
            rc = subprocess.call(cmd, shell=True, cwd=t.workdir, stdout=lf,
                                 stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
        except OSError as e:
            raise ConfigError('빌드 명령을 실행하지 못했다: %s' % e)
    out('로그: %s' % t.build_log)
    if rc == 0:
        out('빌드 성공')
    else:
        out('빌드 실패 (종료 코드 %d). 로그 끝부분:' % rc)
        for ln in tail_lines(t.build_log, 20):
            out('  ' + ln)
    return rc


# ---------- start ----------

def memcheck_gate(args):
    """경고면 True(멈춰야 함). memcheck가 없거나 실패하면 알리고 통과."""
    here = os.path.dirname(os.path.abspath(__file__))
    mc = os.path.normpath(os.path.join(here, '..', 'memcheck', 'memcheck.py'))
    if not os.path.isfile(mc):
        out('참고: memcheck를 찾지 못해 메모리 점검을 건너뛴다 (%s)' % mc)
        return False
    code, o = run_text([sys.executable, mc, '--json'], timeout=60)
    try:
        s = json.loads(o)['Summary']
    except (ValueError, KeyError, TypeError):
        out('참고: memcheck 결과를 읽지 못해 메모리 점검을 건너뛴다 (종료 코드 %s)' % code)
        return False
    if s.get('Warning'):
        out('[경고] 여유 메모리 %.2fGB가 서버 기동 기준 %.1fGB에 못 미친다.' % (
            s.get('FreeGB', 0), s.get('ServerMinGB', 0)))
        out('서버를 띄우지 않았다. 진행 여부는 사람이 정한다.')
        out('사람이 진행을 승인하면 --ignore-memcheck를 붙여 다시 실행한다.')
        return True
    out('메모리 점검 통과 (여유 %.2fGB)' % s.get('FreeGB', 0))
    return False


def cmd_start(args):
    t = make_targets(args, True)[0]
    cmd = t.sub(t.spec.get('start'))
    if not cmd:
        raise ConfigError('서버 "%s"에 start 명령이 없다.' % t.name)
    if not os.path.isdir(t.workdir):
        raise ConfigError('작업 폴더가 없다: %s' % t.workdir)
    # (1) 포트 점유
    if port_listening(t.port):
        pid = t.read_pid()
        out('포트 %d에 이미 LISTEN 중인 프로세스가 있다. 다른 포트를 고르지 않고 멈춘다.' % t.port)
        if pid and pid_alive(pid):
            out('이 하네스가 띄운 프로세스일 수 있다 (PID %d, 기록: %s).' % (pid, t.pid_file))
        else:
            out('이 하네스가 띄운 프로세스가 아니다 (PID 기록 없음).')
        out('규칙 WT-10 절차를 따른다.')
        out('  1) 어느 세션이 이 포트를 쓰는지 확인한다.')
        out('  2) 그 세션의 사용이 끝났는지 확인한다.')
        out('  3) 그래도 정리가 필요하면 사람에게 확인받는다 (종료는 `stop --yes`).')
        return 3
    # (2) 메모리
    if not args.ignore_memcheck and memcheck_gate(args):
        return 4
    # (3) 구동
    os.makedirs(t.records, exist_ok=True)
    lf = open(t.log_file, 'wb')
    kw = {}
    if IS_WIN:
        kw['creationflags'] = (getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0x200)
                               | getattr(subprocess, 'DETACHED_PROCESS', 0x8))
    else:
        kw['start_new_session'] = True
    try:
        proc = subprocess.Popen(cmd, shell=True, cwd=t.workdir, stdout=lf,
                                stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, **kw)
    except OSError as e:
        lf.close()
        raise ConfigError('구동 명령을 실행하지 못했다: %s' % e)
    lf.close()
    with open(t.pid_file, 'w', encoding='utf-8') as f:
        f.write('%d\n' % proc.pid)
    out('구동: %s' % cmd)
    out('폴더: %s / 포트: %d / PID: %d' % (t.workdir, t.port, proc.pid))
    out('로그: %s' % t.log_file)
    # (4) LISTEN 대기
    end = time.time() + args.timeout
    while time.time() < end:
        if port_listening(t.port):
            out('포트 %d LISTEN 확인 (%.0f초)' % (t.port, args.timeout - (end - time.time())))
            return 0
        if proc.poll() is not None:
            out('프로세스가 포트를 열기 전에 종료했다 (종료 코드 %s). 로그 끝부분:' % proc.returncode)
            for ln in tail_lines(t.log_file, 20):
                out('  ' + ln)
            _rm(t.pid_file)
            return 5
        time.sleep(1)
    out('%d초 안에 포트 %d에서 LISTEN이 시작되지 않았다. 로그 끝부분:' % (args.timeout, t.port))
    for ln in tail_lines(t.log_file, 20):
        out('  ' + ln)
    killed = kill_tree(proc.pid)
    try:
        proc.wait(timeout=1)
    except subprocess.SubprocessError:
        pass
    _rm(t.pid_file)
    out('띄우다 만 프로세스를 종료했다.' if killed else '프로세스 종료를 확인하지 못했다. PID %d를 직접 확인한다.' % proc.pid)
    return 5


def _rm(p):
    try:
        os.remove(p)
    except OSError:
        pass


# ---------- stop ----------

def cmd_stop(args):
    t = make_targets(args, True)[0]
    pid = t.read_pid()
    listening = port_listening(t.port)
    if pid is None:
        if listening:
            out('포트 %d: LISTEN 중이나 PID 기록이 없다 (외부에서 띄운 것으로 보인다).' % t.port)
            out('PID를 알 수 없어 종료하지 않는다. 사람이 확인해 직접 정리한다.')
        else:
            out('포트 %d: LISTEN 중이 아니고 PID 기록도 없다. 종료할 대상이 없다.' % t.port)
        return 0
    alive = pid_alive(pid)
    out('종료 대상: 서버 %s / 포트 %d (%s) / PID %d (%s) / 폴더 %s / 띄운 시각 %s' % (
        t.name, t.port, 'LISTEN' if listening else '닫힘', pid,
        '실행 중' if alive else '프로세스 없음', t.workdir, fmt_time(os.path.getmtime(t.pid_file))))
    if alive:
        out('PID %d의 명령: %s' % (pid, process_command(pid) or '(확인하지 못함)'))
    if alive and not listening:
        # 서버 포트는 닫혔는데 PID만 살아 있다 = 기록이 낡았고 PID가 다른 프로세스에 재사용됐을 수 있다.
        out('포트가 닫혀 있는데 PID %d 프로세스는 살아 있다. 이 프로세스가 이 서버가 아닐 수 있어 종료하지 않는다(--yes여도 같다).' % pid)
        out('사람이 위 명령을 확인해 이 서버가 맞으면 직접 정리하고, 아니면 PID 기록(%s)만 지운다.' % t.pid_file)
        return 1
    if not args.yes:
        out('종료하지 않았다. 종료하려면 --yes를 붙인다.')
        return 0
    if alive:
        ok = kill_tree(pid)
        out('종료했다.' if ok else 'PID %d 종료를 확인하지 못했다. 직접 확인한다.' % pid)
        if not ok:
            return 1
    else:
        out('프로세스가 이미 없어 PID 기록만 지운다.')
    _rm(t.pid_file)
    time.sleep(0.5)
    if port_listening(t.port):
        out('경고: 프로세스를 종료했으나 포트 %d에서 아직 LISTEN 중이다 (다른 프로세스가 쥐고 있을 수 있다).' % t.port)
        return 1
    return 0


# ---------- status ----------

def git_info(folder):
    if not os.path.isdir(folder):
        return None
    c, o = run_text(['git', '-C', folder, 'rev-parse', '--abbrev-ref', 'HEAD'])
    if c != 0:
        return None
    branch = o.strip()
    _, head = run_text(['git', '-C', folder, 'rev-parse', '--short', 'HEAD'])
    _, st = run_text(['git', '--no-optional-locks', '-C', folder, 'status', '--porcelain'])
    return {'branch': branch, 'head': head.strip(),
            'uncommitted': len([x for x in st.splitlines() if x.strip()])}


def health_get(url):
    try:
        with urllib.request.urlopen(url, timeout=3) as r:
            return {'status': r.status, 'error': None}
    except urllib.error.HTTPError as e:
        return {'status': e.code, 'error': None}
    except Exception as e:  # 연결 거부·시간 초과 등
        return {'status': None, 'error': str(getattr(e, 'reason', e))}


def status_of(t):
    pid = t.read_pid()
    listening = port_listening(t.port)
    r = {'server': t.name, 'dir': t.workdir, 'port': t.port, 'expectedPort': t.port,
         'basePort': t.base_port, 'worktree': t.worktree, 'listening': listening,
         'pid': pid, 'pidAlive': (pid_alive(pid) if pid else None),
         'git': git_info(t.workdir), 'health': None, 'warnings': []}
    hurl = t.sub(t.spec.get('health', ''))
    if hurl:
        r['healthUrl'] = hurl
        r['health'] = health_get(hurl) if listening else {'status': None, 'error': '포트가 닫혀 있어 요청하지 않음'}
    if pid and r['pidAlive'] is False:
        r['warnings'].append('PID 파일(%d)은 있으나 프로세스가 없다 (낡은 기록).' % pid)
    # 기대 포트와 다른 포트에서 이 서버로 띄운 프로세스가 LISTEN 중인지
    try:
        names = os.listdir(t.records)
    except OSError:
        names = []
    for n in names:
        if n.startswith(t.name + '-') and n.endswith('.pid'):
            mid = n[len(t.name) + 1:-4]
            if mid.isdigit() and int(mid) != t.port and port_listening(int(mid)):
                r['warnings'].append('기대 포트(%d)와 다른 포트(%s)에서 이 서버의 기록이 LISTEN 중이다.' % (t.port, mid))
    if t.worktree and t.base_port != t.port and port_listening(t.base_port):
        r['warnings'].append('워크트리 기대 포트는 %d인데 기본 포트 %d에서 LISTEN 중이다 (본 폴더 서버일 수 있다).' % (
            t.port, t.base_port))
    if listening and pid is None:
        r['warnings'].append('포트는 LISTEN 중이나 이 하네스가 띄운 기록이 없다.')
    return r


def cmd_status(args):
    targets = make_targets(args, False)
    results = [status_of(t) for t in targets]
    if args.json:
        out(json.dumps(results, ensure_ascii=False, indent=2))
        return 0
    for r in results:
        out('서버 %s' % r['server'])
        out('  폴더: %s' % r['dir'])
        out('  포트: %d (%s)%s' % (r['port'], 'LISTEN' if r['listening'] else '닫힘',
                                   ' [워크트리 기대 포트, 기본 %d]' % r['basePort'] if r['worktree'] and r['port'] != r['basePort'] else ''))
        if r['pid']:
            out('  PID: %d (%s)' % (r['pid'], '실행 중' if r['pidAlive'] else '프로세스 없음'))
        else:
            out('  PID: 알 수 없음(외부에서 띄움)' if r['listening'] else '  PID: 기록 없음')
        g = r['git']
        out('  git: %s' % ('브랜치 %s / HEAD %s / 미커밋 %d건' % (g['branch'], g['head'], g['uncommitted']) if g else 'git 저장소 아님'))
        h = r['health']
        if h is not None:
            out('  헬스: %s' % ('HTTP %d' % h['status'] if h['status'] else '실패 (%s)' % h['error']))
        for w in r['warnings']:
            out('  경고: ' + w)
    return 0


# ---------- 진입 ----------

def build_parser():
    ap = argparse.ArgumentParser(prog='server_ops.py', description='Spring Boot + Gradle 서버 실행기')
    ap.add_argument('sub', choices=['init', 'build', 'start', 'stop', 'status'])
    ap.add_argument('server', nargs='?')
    ap.add_argument('--dir', help='워크트리(또는 init 대상) 폴더')
    ap.add_argument('--port', type=int, help='포트 직접 지정(차이값보다 우선)')
    ap.add_argument('--yes', action='store_true', help='stop: 실제로 종료')
    ap.add_argument('--json', action='store_true', help='status: JSON 출력')
    ap.add_argument('--config', help='설정 파일 경로')
    ap.add_argument('--timeout', type=int, default=120, help='start: LISTEN 대기 초(기본 120)')
    ap.add_argument('--ignore-memcheck', action='store_true', help='start: 사람이 승인한 뒤 메모리 경고를 넘긴다')
    ap.add_argument('--name', help='init: 서버 이름')
    ap.add_argument('--health', help='init: 헬스 URL')
    ap.add_argument('--write', action='store_true', help='init: 설정 파일 쓰기')
    ap.add_argument('--force', action='store_true', help='init: 기존 설정 덮어쓰기')
    return ap


def main(argv):
    args = build_parser().parse_args(argv)
    try:
        return {'init': cmd_init, 'build': cmd_build, 'start': cmd_start,
                'stop': cmd_stop, 'status': cmd_status}[args.sub](args)
    except ConfigError as e:
        out('오류: %s' % e)
        return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
