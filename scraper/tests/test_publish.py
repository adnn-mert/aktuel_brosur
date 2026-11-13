"""Publishing to the data branch, against throwaway local repositories (no network)."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from scraper.publish import BOT_NAME, Decision, decide, main

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")

_ENV = {
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
}


def git(cwd: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, env={**os.environ, **_ENV})
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


@pytest.fixture
def repo(tmp_path) -> Path:
    """A checkout of ``main`` whose ``origin`` is a local bare repository."""
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "--bare", "-b", "main", str(remote))
    work = tmp_path / "work"
    git(tmp_path, "clone", str(remote), str(work))
    (work / "README.md").write_text("main branch\n", encoding="utf-8")
    (work / ".gitignore").write_text("*.json\nmedia/\n", encoding="utf-8")
    git(work, "add", ".")
    git(work, "commit", "-m", "init")
    git(work, "push", "origin", "HEAD:main")
    return work


def make_output(root: Path, generated_at: str = "2026-11-13T09:00:00Z") -> Path:
    (root / "media/sok/x").mkdir(parents=True)
    (root / "media/sok/x/p01.webp").write_bytes(b"webp")
    (root / "catalog.json").write_text(f'{{"generated_at": "{generated_at}"}}\n', encoding="utf-8")
    (root / "health.json").write_text("{}\n", encoding="utf-8")
    return root


def remote_files(repo: Path) -> list[str]:
    return sorted(git(repo, "ls-tree", "-r", "--name-only", "origin/data").splitlines())


def publish(repo: Path, out: Path, code: int, *extra: str) -> int:
    return main(["--repo", str(repo), "publish", "--out", str(out), "--exit-code", str(code), *extra])


@pytest.mark.parametrize(
    ("code", "decision"),
    [(0, Decision.PUBLISH), (2, Decision.PUBLISH_THEN_FAIL), (1, Decision.SKIP), (3, Decision.SKIP), (-1, Decision.SKIP)],
)
def test_decide(code: int, decision: Decision) -> None:
    assert decide(code) is decision


def test_publish_writes_a_single_parentless_commit(repo, tmp_path) -> None:
    out = make_output(tmp_path / "out")
    assert publish(repo, out, 0) == 0
    git(repo, "fetch", "origin", "data")
    # Ignore rules of main (*.json, media/) must not hide any published file.
    assert remote_files(repo) == [".nojekyll", "catalog.json", "health.json", "media/sok/x/p01.webp"]
    assert git(repo, "rev-list", "--count", "origin/data") == "1"
    assert git(repo, "log", "-1", "--format=%an|%s", "origin/data") == (
        f"{BOT_NAME}|Publish scraper output generated at 2026-11-13T09:00:00Z"
    )
    # main is untouched: same commit, clean working tree.
    assert git(repo, "log", "-1", "--format=%s", "origin/main") == "init"
    assert git(repo, "status", "--porcelain") == ""

    second = make_output(tmp_path / "out2", "2026-11-13T15:00:00Z")
    (second / "media/sok/x/p01.webp").unlink()
    assert publish(repo, second, 0) == 0
    git(repo, "fetch", "origin", "data")
    assert git(repo, "rev-list", "--count", "origin/data") == "1"
    assert "media/sok/x/p01.webp" not in remote_files(repo)


def test_exit_code_2_publishes_and_fails(repo, tmp_path, capsys) -> None:
    assert publish(repo, make_output(tmp_path / "out"), 2) == 1
    assert "3 or more runs" in capsys.readouterr().out
    git(repo, "fetch", "origin", "data")
    assert "catalog.json" in remote_files(repo)


@pytest.mark.parametrize("code", [1, 137])
def test_failed_scrape_is_not_published(repo, tmp_path, code: int) -> None:
    assert publish(repo, make_output(tmp_path / "out"), code) == 1
    assert git(repo, "ls-remote", "--heads", "origin", "data") == ""


def test_missing_output_is_not_published(repo, tmp_path) -> None:
    assert publish(repo, tmp_path / "nothing", 0) == 1
    assert git(repo, "ls-remote", "--heads", "origin", "data") == ""


def test_size_guard(repo, tmp_path, capsys) -> None:
    assert publish(repo, make_output(tmp_path / "out"), 0, "--max-bytes", "10") == 1
    assert "limit is" in capsys.readouterr().out
    assert git(repo, "ls-remote", "--heads", "origin", "data") == ""


def test_fetch_state(repo, tmp_path) -> None:
    state = tmp_path / "state"
    # First run: no data branch yet, which is not an error.
    assert main(["--repo", str(repo), "fetch-state", "--dir", str(state)]) == 0
    assert state.is_dir() and not any(state.iterdir())

    assert publish(repo, make_output(tmp_path / "out"), 0) == 0
    state2 = tmp_path / "state2"
    assert main(["--repo", str(repo), "fetch-state", "--dir", str(state2)]) == 0
    assert (state2 / "media/sok/x/p01.webp").read_bytes() == b"webp"
    assert (state2 / "catalog.json").is_file()
