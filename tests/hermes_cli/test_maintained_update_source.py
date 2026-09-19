"""A fork on main consumes origin only; upstream and official ZIPs cannot bypass review."""

import json
import subprocess
from types import SimpleNamespace

import pytest

from hermes_cli import main, banner, update_cmd
from hermes_cli.update_cmd_git import _sync_fork_with_upstream, _sync_with_upstream_if_needed
from hermes_cli.update_cmd_zip import _update_via_zip


def git(root, *args):
    return subprocess.check_output(
        ["git", "-c", "commit.gpgsign=false", *args], cwd=root, text=True, stderr=subprocess.PIPE,
    ).strip()


def repository(path):
    path.mkdir()
    git(path, "init", "-b", "main")
    git(path, "config", "user.name", "Test")
    git(path, "config", "user.email", "test@example.invalid")
    (path / "feature.txt").write_text("maintained behavior\n")
    git(path, "add", ".")
    git(path, "commit", "-m", "Maintained release")
    return path


def test_check_and_sync_never_consume_upstream_main(tmp_path, monkeypatch, capsys):
    published = repository(tmp_path / "published")
    installed = tmp_path / "installed"
    git(tmp_path, "clone", str(published), str(installed))
    git(installed, "remote", "set-url", "origin", "https://github.com/Dodelidoo-Labs/hermes-agent.git")
    # Upstream is a real, reachable repository with newer, unreviewed work.
    upstream = tmp_path / "upstream"
    git(tmp_path, "clone", str(published), str(upstream))
    git(upstream, "config", "user.name", "Test")
    git(upstream, "config", "user.email", "test@example.invalid")
    (upstream / "unreviewed.txt").write_text("not a release\n")
    git(upstream, "add", ".")
    git(upstream, "commit", "-m", "Unreleased main")
    git(installed, "remote", "add", "upstream", str(upstream))
    monkeypatch.setattr(main, "PROJECT_ROOT", installed)
    real_run = update_cmd._git_run
    fetched = []

    def local_transport(cmd, args, cwd=None, **kwargs):
        if args[:2] == ["fetch", "origin"]:
            fetched.append("origin")
            # Substitute transport only; actual git fetch, refs and counting still run.
            return real_run(cmd, ["fetch", str(published), "main:refs/remotes/origin/main"], cwd, **kwargs)
        return real_run(cmd, args, cwd, **kwargs)

    monkeypatch.setattr(update_cmd, "_git_run", local_transport)
    update_cmd._cmd_update_check("main")
    assert fetched == ["origin"]
    assert "Already up to date" in capsys.readouterr().out
    fetch_head = (installed / ".git/FETCH_HEAD").read_bytes()
    assert _sync_with_upstream_if_needed(["git"], installed, assume_yes=True)
    assert not _sync_fork_with_upstream(["git"], installed)
    assert (installed / ".git/FETCH_HEAD").read_bytes() == fetch_head
    assert not (installed / "unreviewed.txt").exists()
    assert git(installed, "rev-parse", "HEAD") == git(published, "rev-parse", "HEAD")
    # A broken Git/Windows fallback must refuse before options, download or swap.
    with pytest.raises(SystemExit, match="ZIP update refused"):
        _update_via_zip(SimpleNamespace())
    from hermes_cli.update_managed_fork import require_official_zip_origin
    git(installed, "remote", "set-url", "origin", "https://github.com/NousResearch/hermes-agent.git")
    require_official_zip_origin(installed)
    git(installed, "remote", "remove", "origin")
    with pytest.raises(SystemExit, match="cannot be verified"):
        require_official_zip_origin(installed)


def test_passive_count_and_changelog_use_the_origin_repository(tmp_path, monkeypatch):
    installed = repository(tmp_path / "installed")
    git(installed, "remote", "add", "origin", "https://github.com/Dodelidoo-Labs/hermes-agent.git")
    current = git(installed, "rev-parse", "HEAD")
    target = "a" * 40
    monkeypatch.setattr(banner, "_resolve_repo_dir", lambda: installed)
    banner._compare_payload_cache.clear()
    urls = []

    class Response:
        def __init__(self, data):
            self.data = data
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self):
            return self.data

    def transport(request, **kwargs):
        urls.append(request.full_url)
        assert "/repos/dodelidoo-labs/hermes-agent/" in request.full_url
        if "/commits/main" in request.full_url:
            return Response(target.encode())
        return Response(json.dumps({"ahead_by": 1, "commits": [{
            "sha": target, "commit": {"message": "Reviewed release", "author": {"name": "Test"}},
        }]}).encode())

    monkeypatch.setattr("urllib.request.urlopen", transport)
    assert banner.check_for_updates() == 1
    assert banner.upstream_commits_behind()[0]["summary"] == "Reviewed release"
    assert any(f"/compare/{current}...{target}" in url for url in urls)
    assert git(installed, "rev-parse", "HEAD") == current
