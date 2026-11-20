"""Create a work branch + sparse worktree (AI-DLC step 12: WT-02/WT-03/WT-06).

Cross-platform port of the original Windows `new-worktree.ps1`. Same behavior on
macOS, Linux, and Windows, using only the Python standard library plus `git`.

What it does:
  1.  pre-checks (project is a git repo, base branch, name clashes,
      settings.local.json is git-ignored)
      - --base omitted: "<first segment of --branch>/main" (e.g. team-a/main);
        if that local branch does not exist, falls back to "main" and says so.
  1b. git fetch origin <base> (30 s timeout, no interactive prompt). A fetch
      failure (expired login, no network, no remote) STOPS the script. If the
      local <base> is behind origin/<base> it STOPS too, creating nothing (WT-03).
  1c. repo-local `git config core.longpaths true` (WT-06; harmless off-Windows).
  2.  git branch --no-track <branch> <base>            (local only, no upstream)
  3.  git worktree add --no-checkout <project>/.claude/worktrees/<name> <branch>
  4.  sparse-checkout (non-cone): /*  and  !/docs/     (docs/ is NOT materialized)
  5.  git checkout <branch>
  6.  worktree .claude/settings.local.json  ->  env PRJ_METRICS_DIR (ledger outside repo)
  7.  print verification (branch -vv, sparse list, paths)

It does NOT commit, push, delete anything, create docs, or touch existing
worktrees. On any failure it stops and prints what was left behind; it never
cleans up by itself.

Example:
  new_worktree.py --project buyer-portal --branch team-a/alice_dev/screen-058 --name b-m-x-foo-task
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def fail(msg: str) -> "None":
    print(f"[FAIL] {msg}", file=sys.stderr)
    sys.exit(1)


def git(dir_: Path, *args: str, check: bool = True, timeout=None):
    """Run `git -C <dir> <args>`; on non-zero exit (when check) call fail()."""
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="never")
    try:
        p = subprocess.run(
            ["git", "-C", str(dir_), *args],
            capture_output=True, text=True, env=env, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise
    if check and p.returncode != 0:
        fail("git " + " ".join(args) + " failed:\n" + (p.stderr or p.stdout).strip())
    return p


def branch_exists(proj: Path, ref: str) -> bool:
    return git(proj, "rev-parse", "--verify", "--quiet", f"refs/heads/{ref}",
               check=False).returncode == 0


def main() -> None:
    ap = argparse.ArgumentParser(add_help=True, description="AI-DLC WT-02/03/06 worktree creator")
    ap.add_argument("--project", required=True, help="project directory name under --root")
    ap.add_argument("--branch", required=True, help="new branch name, e.g. team-a/alice_dev/screen-058")
    ap.add_argument("--name", required=True, help="worktree directory name under .claude/worktrees/")
    ap.add_argument("--base", default="", help="base branch; default = '<first segment of --branch>/main' then 'main'")
    ap.add_argument("--root", default=os.environ.get("PRJ_ROOT", os.getcwd()),
                    help="directory that holds the project (default: $PRJ_ROOT or CWD)")
    ap.add_argument("--metrics-root", default=os.path.join(Path.home(), ".prj-ai-metrics"),
                    help="root for the out-of-repo metrics ledger (default: ~/.prj-ai-metrics)")
    ap.add_argument("--no-exclude-docs", action="store_true",
                    help="do not add the '!/docs/' sparse exclusion")
    a = ap.parse_args()

    # ---- 1. pre-checks ----------------------------------------------------
    proj = Path(a.root) / a.project
    if not (proj / ".git").exists():
        fail(f"not a git project root: {proj}")

    explicit_base = bool(a.base)
    base = a.base or f"{a.branch.split('/')[0]}/main"
    if not branch_exists(proj, base):
        if explicit_base:
            fail(f"base branch not found locally: {base}")
        if not branch_exists(proj, "main"):
            fail(f"base branch not found locally: {base} (and no local main). Pass --base explicitly.")
        print(f"[note] local branch {base} does not exist; using main as the base (WT-03).")
        base = "main"
    print(f"[ok] base branch: {base} ({'given by --base' if explicit_base else 'auto'})")

    if branch_exists(proj, a.branch):
        fail(f"branch already exists: {a.branch}")

    wt = proj / ".claude" / "worktrees" / a.name
    if wt.exists():
        fail(f"worktree path already exists: {wt}")

    # Windows 260-char path limit: only enforced on Windows.
    if os.name == "nt":
        files = git(proj, "ls-files").stdout.splitlines()
        longest = max((len(f) for f in files), default=0)
        if len(str(wt)) + 1 + longest >= 255:
            fail(f"path too long: worktree({len(str(wt))}) + longest tracked file({longest}) >= 255. "
                 f"Use a shorter --name.")

    if git(proj, "check-ignore", "-q", ".claude/settings.local.json", check=False).returncode != 0:
        fail(f".claude/settings.local.json is NOT git-ignored in {a.project}. Stopping so the env file "
             f"cannot be committed by accident. Report to the human.")

    # ---- 1b. remote check (WT-03) -----------------------------------------
    try:
        f = git(proj, "fetch", "origin", base, check=False, timeout=30)
    except subprocess.TimeoutExpired:
        fail(f"git fetch did not finish within 30 s. Nothing was created. The login may have expired: "
             f"ask the human to run '! git -C {proj} fetch' once, then run this script again.")
    if f.returncode != 0:
        fail(f"git fetch failed. Nothing was created. If the login expired, ask the human to run "
             f"'! git -C {proj} fetch' once, then run this script again.\n{(f.stderr or f.stdout).strip()}")

    if git(proj, "rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{base}",
           check=False).returncode == 0:
        behind = int(git(proj, "rev-list", "--count", f"{base}..origin/{base}").stdout.strip() or "0")
        if behind > 0:
            fail(f"local {base} is {behind} commit(s) behind origin/{base}. Nothing was created. "
                 f"Do not update the local base branch on your own: ask the human (or qa-master) first (WT-03).")
        print(f"[ok] {base} is not behind origin/{base}")
    else:
        print(f"[note] origin/{base} does not exist; behind-check skipped.")

    # ---- 1c. long paths (WT-06) -------------------------------------------
    git(proj, "config", "core.longpaths", "true")
    print("[ok] core.longpaths=true (repo-local git config)")

    # ---- 2. branch (no upstream) ------------------------------------------
    git(proj, "branch", "--no-track", a.branch, base)
    print(f"[ok] branch created: {a.branch} (from {base})")

    # ---- 3. worktree without checkout -------------------------------------
    git(proj, "worktree", "add", "--no-checkout", str(wt), a.branch)
    print(f"[ok] worktree added (no checkout): {wt}")

    # ---- 4. sparse-checkout -----------------------------------------------
    git(wt, "sparse-checkout", "init", "--no-cone")
    patterns = "/*\n" if a.no_exclude_docs else "/*\n!/docs/\n"
    p = subprocess.run(["git", "-C", str(wt), "sparse-checkout", "set", "--no-cone", "--stdin"],
                       input=patterns, text=True, capture_output=True)
    if p.returncode != 0:
        fail(f"sparse-checkout set failed (branch and worktree were left in place: {wt})\n{p.stderr.strip()}")

    # ---- 5. checkout ------------------------------------------------------
    git(wt, "checkout", a.branch)
    print("[ok] checked out with sparse patterns")

    # ---- 6. settings.local.json (merge, keep existing keys) ---------------
    metrics_dir = Path(a.metrics_root) / a.project
    metrics_dir.mkdir(parents=True, exist_ok=True)
    settings_path = wt / ".claude" / "settings.local.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if settings_path.exists():
        try:
            data = json.loads(settings_path.read_text(encoding="utf-8")) or {}
        except json.JSONDecodeError:
            fail(f"existing {settings_path} is not valid JSON; not overwriting. Report to the human.")
    data.setdefault("env", {})
    data["env"]["PRJ_METRICS_DIR"] = str(metrics_dir)
    settings_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[ok] PRJ_METRICS_DIR={metrics_dir} written to {settings_path}")

    # ---- 7. verification output -------------------------------------------
    print("\n--- git branch -vv (this branch must have NO [origin/...] tracking) ---")
    for line in git(wt, "branch", "-vv").stdout.splitlines():
        if a.branch in line:
            print(line)
    print("--- git sparse-checkout list ---")
    print(git(wt, "sparse-checkout", "list").stdout.rstrip())
    print("--- docs/ present in worktree? (must be False) ---")
    print((wt / "docs").exists())
    print("--- settings.local.json ---")
    print(settings_path.read_text(encoding="utf-8").rstrip())

    up = git(wt, "rev-parse", "--abbrev-ref", f"{a.branch}@{{upstream}}", check=False)
    if up.returncode == 0 and up.stdout.strip():
        print(f"[WARN] upstream is set ({up.stdout.strip()}). Report to the human; do not unset on your own.")

    print(f"\nWORKTREE={wt}")


if __name__ == "__main__":
    main()
