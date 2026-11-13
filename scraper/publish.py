"""Move scraper output to and from the ``data`` branch (used by .github/workflows/scrape.yml).

``fetch-state``  copies the published files of the ``data`` branch into a folder, so the next
                 run can merge with them. A missing branch means "first run", not an error.
``publish``      writes an output folder to the ``data`` branch as a single parentless commit
                 and force-pushes it, so the branch never accumulates history.

Git plumbing with a throwaway index is used instead of a second clone: the checkout's own
credentials push, and the working tree of ``main`` is never touched.

Exit codes of ``publish`` follow the scraper's: 0 published; 1 not published (scraper exit
1, unknown exit code or output too large) or published after a scraper exit 2, so the job
turns red while the data still goes out.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
from collections.abc import Sequence
from enum import Enum
from pathlib import Path

DATA_BRANCH = "data"
DEFAULT_REMOTE = "origin"
# GitHub Pages refuses sites over 1 GB; stay far below to leave room for growth.
MAX_OUTPUT_BYTES = 500 * 1024 * 1024
BOT_NAME = "github-actions[bot]"
BOT_EMAIL = "41898282+github-actions[bot]@users.noreply.github.com"


class Decision(Enum):
    PUBLISH = "publish"
    PUBLISH_THEN_FAIL = "publish-then-fail"
    SKIP = "skip"


def decide(scraper_exit_code: int) -> Decision:
    """0: publish. 2: publish, then fail the job (a source keeps failing). Anything else: skip."""
    if scraper_exit_code == 0:
        return Decision.PUBLISH
    if scraper_exit_code == 2:
        return Decision.PUBLISH_THEN_FAIL
    return Decision.SKIP


def output_size(root: Path) -> int:
    return sum(p.stat().st_size for p in root.rglob("*") if p.is_file())


class GitError(RuntimeError):
    pass


def _git(repo: Path, *args: str, env: dict[str, str] | None = None, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        env={**os.environ, **(env or {})},
        capture_output=True,
    )
    if check and result.returncode != 0:
        stderr = result.stderr.decode("utf-8", "replace").strip()
        raise GitError(f"git {' '.join(args[:2])} failed ({result.returncode}): {stderr}")
    return result


def branch_exists(repo: Path, remote: str, branch: str) -> bool:
    result = _git(repo, "ls-remote", "--exit-code", "--heads", remote, branch, check=False)
    if result.returncode == 2:
        return False
    if result.returncode != 0:
        raise GitError(f"git ls-remote failed ({result.returncode}): {result.stderr.decode('utf-8', 'replace').strip()}")
    return True


def fetch_state(repo: Path, dest: Path, *, remote: str = DEFAULT_REMOTE, branch: str = DATA_BRANCH) -> bool:
    """Extract the branch's files into ``dest``; False (and an empty ``dest``) if it does not exist."""
    dest.mkdir(parents=True, exist_ok=True)
    if not branch_exists(repo, remote, branch):
        return False
    _git(repo, "fetch", "--no-tags", "--depth", "1", remote, f"refs/heads/{branch}")
    archive = _git(repo, "archive", "--format=tar", "FETCH_HEAD").stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        # The "data" filter refuses absolute paths, links out of dest and device files.
        tar.extractall(dest, filter="data")
    return True


def publish_tree(
    repo: Path,
    out_dir: Path,
    message: str,
    *,
    remote: str = DEFAULT_REMOTE,
    branch: str = DATA_BRANCH,
) -> str:
    """Commit ``out_dir`` as the only commit of ``branch`` and force-push it; returns the sha."""
    out_dir = out_dir.resolve()
    # Without it GitHub Pages runs Jekyll, which hides files and slows every deploy.
    (out_dir / ".nojekyll").touch()
    with tempfile.TemporaryDirectory() as tmp:
        identity = {
            "GIT_INDEX_FILE": str(Path(tmp) / "index"),
            "GIT_AUTHOR_NAME": BOT_NAME,
            "GIT_AUTHOR_EMAIL": BOT_EMAIL,
            "GIT_COMMITTER_NAME": BOT_NAME,
            "GIT_COMMITTER_EMAIL": BOT_EMAIL,
        }
        git_dir = _git(repo, "rev-parse", "--absolute-git-dir").stdout.decode().strip()
        # Run inside out_dir so "." means the output; --force publishes it whole whatever
        # ignore rules the repository has.
        _git(out_dir, f"--git-dir={git_dir}", f"--work-tree={out_dir}", "add", "--all", "--force", ".", env=identity)
        tree = _git(repo, "write-tree", env=identity).stdout.decode().strip()
        commit = _git(repo, "commit-tree", tree, "-m", message, env=identity).stdout.decode().strip()
    _git(repo, "push", "--force", remote, f"{commit}:refs/heads/{branch}")
    return commit


def _commit_message(out_dir: Path) -> str:
    try:
        generated = json.loads((out_dir / "catalog.json").read_text(encoding="utf-8"))["generated_at"]
    except (OSError, ValueError, KeyError, TypeError):
        generated = "unknown time"
    return f"Publish scraper output generated at {generated}"


def _cmd_fetch_state(args: argparse.Namespace) -> int:
    found = fetch_state(args.repo, args.dir, remote=args.remote, branch=args.branch)
    print(f"previous state: {'restored from ' + args.branch if found else 'none (first run)'} -> {args.dir}")
    return 0


def _cmd_publish(args: argparse.Namespace) -> int:
    decision = decide(args.exit_code)
    if decision is Decision.SKIP:
        print(f"::error::scraper exited with {args.exit_code}; nothing published")
        return 1
    out_dir: Path = args.out
    if not (out_dir / "catalog.json").is_file():
        print(f"::error::{out_dir}/catalog.json is missing; nothing published")
        return 1
    size = output_size(out_dir)
    if size > args.max_bytes:
        print(f"::error::output is {size / 1_048_576:.0f} MB, limit is {args.max_bytes / 1_048_576:.0f} MB; nothing published")
        return 1
    sha = publish_tree(args.repo, out_dir, _commit_message(out_dir), remote=args.remote, branch=args.branch)
    print(f"published {size / 1_048_576:.1f} MB to {args.branch} as {sha[:12]}")
    if decision is Decision.PUBLISH_THEN_FAIL:
        print("::error::published, but a source has failed 3 or more runs in a row (see the run summary)")
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m scraper.publish")
    parser.add_argument("--repo", type=Path, default=Path("."), help="git checkout to work in (default: .)")
    parser.add_argument("--remote", default=DEFAULT_REMOTE)
    parser.add_argument("--branch", default=DATA_BRANCH)
    sub = parser.add_subparsers(dest="command", required=True)

    p_fetch = sub.add_parser("fetch-state", help="copy the published data branch into a folder")
    p_fetch.add_argument("--dir", type=Path, required=True)
    p_fetch.set_defaults(func=_cmd_fetch_state)

    p_pub = sub.add_parser("publish", help="publish an output folder as the data branch")
    p_pub.add_argument("--out", type=Path, required=True)
    p_pub.add_argument("--exit-code", type=int, required=True, help="exit code of `python -m scraper run`")
    p_pub.add_argument("--max-bytes", type=int, default=MAX_OUTPUT_BYTES)
    p_pub.set_defaults(func=_cmd_publish)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except GitError as exc:
        print(f"::error::{exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
