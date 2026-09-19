"""Release integration must retain fork history and never consume unreleased main."""

import importlib.util
import json
from pathlib import Path
import subprocess

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / ".github/scripts/fork_release.py"
spec = importlib.util.spec_from_file_location("fork_release", SCRIPT)
release_sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release_sync)


def git(repo, *args):
    return subprocess.check_output(
        ["git", "-c", "commit.gpgsign=false", *args], cwd=repo, text=True,
        stderr=subprocess.PIPE,
    ).strip()


def commit(repo, message):
    git(repo, "add", ".")
    git(repo, "commit", "-m", message)
    return git(repo, "rev-parse", "HEAD")


def setup_repos(tmp_path):
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    git(upstream, "init", "-b", "main")
    git(upstream, "config", "user.name", "Release test")
    git(upstream, "config", "user.email", "test@example.invalid")
    for path in (".github/workflows/check.yml", ".github/scripts/check.sh"):
        target = upstream / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("original automation\n")
    (upstream / "shared.txt").write_text("first\n" + "context\n" * 20 + "last\n")
    commit(upstream, "Common baseline")
    fork = tmp_path / "fork"
    git(tmp_path, "clone", str(upstream), str(fork))
    git(fork, "config", "user.name", "Release test")
    git(fork, "config", "user.email", "test@example.invalid")
    git(fork, "checkout", "main")
    origin = tmp_path / "origin.git"
    git(tmp_path, "init", "--bare", str(origin))
    git(fork, "remote", "set-url", "origin", str(origin))
    return upstream, fork, origin


def metadata(tag):
    return {
        "tag_name": tag, "published_at": "2026-09-19T00:00:00Z",
        "draft": False, "prerelease": False,
        "html_url": f"https://example.invalid/releases/{tag}", "body": "Release notes",
    }


def test_release_preserves_customizations_excludes_main_and_reuses_amendments(tmp_path):
    upstream, fork, origin = setup_repos(tmp_path)
    (fork / "custom.txt").write_text("Present and future fork features\n")
    shared = fork / "shared.txt"
    shared.write_text(shared.read_text().replace("last", "fork behavior"))
    for path in release_sync.PROTECTED_PATHS:
        target = fork / path / ("check.yml" if path.endswith("workflows") else "check.sh")
        target.write_text("maintained automation\n")
    base = commit(fork, "Customizations")
    git(fork, "push", "origin", "main")
    shared = upstream / "shared.txt"
    shared.write_text(shared.read_text().replace("first", "released behavior"))
    (upstream / ".github/workflows/check.yml").write_text("upstream automation\n")
    released = commit(upstream, "Published work")
    # Annotated tags must resolve to their commit, not the tag object.
    git(upstream, "-c", "tag.gpgsign=false", "tag", "-a", "release-one", "-m", "Release one")
    (upstream / "unreleased.txt").write_text("Must not ship\n")
    commit(upstream, "Unreleased main")
    release = metadata("release-one")
    output = tmp_path / "review"
    result = release_sync.prepare(fork, release, str(upstream), output)
    assert result["upstream"] == released
    assert release_sync.ancestor(fork, base, result["candidate"])
    assert release_sync.ancestor(fork, released, result["candidate"])
    assert not (fork / "unreleased.txt").exists()
    assert (fork / "custom.txt").read_text() == "Present and future fork features\n"
    assert "released behavior" in (fork / "shared.txt").read_text()
    assert "fork behavior" in (fork / "shared.txt").read_text()
    assert (fork / ".github/workflows/check.yml").read_text() == "maintained automation\n"
    packet = json.loads((output / "review.json").read_text())
    assert "shared.txt" in packet["overlapping_files"]
    assert "custom.txt" in packet["fork_changed_files"]
    assert ".github/workflows/check.yml" in packet["upstream_automation_changes"]
    assert "fork behavior" in (output / "fork-changes.patch").read_text()
    assert "released behavior" in (output / "overlapping-upstream-changes.patch").read_text()
    # Exercise the same artifact transfer used by the validation job.
    consumer = tmp_path / "consumer"
    git(tmp_path, "clone", "--branch", "main", str(origin), str(consumer))
    git(consumer, "fetch", str(output / "candidate.bundle"), "HEAD")
    assert git(consumer, "rev-parse", "FETCH_HEAD") == result["candidate"]
    assert release_sync.prepare(fork, release, str(upstream), tmp_path / "noop")["candidate"] == ""
    # A reviewer's amendments survive later scheduled revalidation.
    (fork / "custom.txt").write_text("Reviewed fix\n")
    amended = commit(fork, "Review fix")
    git(fork, "push", "origin", f"HEAD:refs/heads/{result['branch']}")
    git(fork, "checkout", "--detach", base)
    repeated = release_sync.prepare(fork, release, str(upstream), tmp_path / "revalidated")
    assert repeated["candidate"] == amended
    assert (fork / "custom.txt").read_text() == "Reviewed fix\n"


def test_invalid_release_dirty_checkout_and_source_conflict_publish_nothing(tmp_path):
    upstream, fork, origin = setup_repos(tmp_path)
    (fork / "shared.txt").write_text("Our behavior\n")
    base = commit(fork, "Fork feature")
    git(fork, "push", "origin", "main")
    original_refs = git(origin, "show-ref")
    (upstream / "shared.txt").write_text("Conflicting upstream behavior\n")
    commit(upstream, "Upstream change")
    git(upstream, "tag", "release-two")
    release = metadata("release-two")
    output = tmp_path / "review"
    for flags in ({"draft": True}, {"prerelease": True}, {"published_at": None}):
        with pytest.raises(ValueError):
            release_sync.prepare(fork, {**release, **flags}, str(upstream), output)
    (fork / "uncommitted.txt").write_text("Unsaved feature\n")
    with pytest.raises(RuntimeError, match="clean checkout"):
        release_sync.prepare(fork, release, str(upstream), output)
    assert (fork / "uncommitted.txt").read_text() == "Unsaved feature\n"
    (fork / "uncommitted.txt").unlink()
    with pytest.raises(RuntimeError, match="Source conflicts"):
        release_sync.prepare(fork, release, str(upstream), output)
    assert git(fork, "rev-parse", "HEAD") == base
    assert git(fork, "status", "--porcelain") == ""
    assert (fork / "shared.txt").read_text() == "Our behavior\n"
    assert git(origin, "show-ref") == original_refs
    assert not output.exists()
