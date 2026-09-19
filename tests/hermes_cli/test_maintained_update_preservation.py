"""The actual updater must refuse to stash/reset unpublished maintained-fork work."""

import subprocess

import pytest

from hermes_cli import main
from hermes_cli.update_cmd import (
    _prepare_checkout_for_update,
    _prepare_git_command,
    _pull_updates,
    _reconcile_diverged_checkout,
)


def git(root, *args):
    return subprocess.check_output(
        ["git", "-c", "commit.gpgsign=false", *args], cwd=root,
        text=True, stderr=subprocess.PIPE,
    ).strip()


@pytest.fixture
def checkout(tmp_path, monkeypatch):
    root = tmp_path / "install"
    root.mkdir()
    git(root, "init", "-b", "main")
    git(root, "config", "user.name", "Update test")
    git(root, "config", "user.email", "test@example.invalid")
    git(root, "remote", "add", "origin", "https://github.com/Dodelidoo-Labs/hermes-agent.git")
    (root / "feature.txt").write_text("our behavior\n")
    (root / "package-lock.json").write_text("{}\n")
    git(root, "add", ".")
    git(root, "commit", "-m", "Installed customizations")
    git(root, "update-ref", "refs/remotes/origin/main", "HEAD")
    monkeypatch.setattr(main, "PROJECT_ROOT", root)
    return root


def prepare(branch="main"):
    return _prepare_checkout_for_update(
        ["git"], branch, "main", is_fork=True, assume_yes=True, gateway_mode=True,
        gw_input_fn=None, switch_branch=True, _windows_gateway_resume=None,
    )


def test_local_edits_commits_and_wrong_targets_remain_in_place(checkout):
    root = checkout
    original = git(root, "rev-parse", "HEAD")
    (root / "package-lock.json").write_text('{"intentional":"change"}\n')
    (root / "new-feature.txt").write_text("untracked feature\n")
    before = git(root, "status", "--porcelain")
    _prepare_git_command()  # Must not discard lockfile edits before the guard.
    with pytest.raises(SystemExit, match="local edits"):
        prepare()
    assert git(root, "status", "--porcelain") == before
    assert git(root, "stash", "list") == ""
    assert (root / "package-lock.json").read_text() == '{"intentional":"change"}\n'
    git(root, "add", ".")
    git(root, "commit", "-m", "Unpublished future feature")
    local = git(root, "rev-parse", "HEAD")
    for operation in (prepare, lambda: _reconcile_diverged_checkout(["git"], "main", local)):
        with pytest.raises(SystemExit, match="unpublished"):
            operation()
        assert git(root, "rev-parse", "HEAD") == local
        assert (root / "new-feature.txt").read_text() == "untracked feature\n"
    with pytest.raises(SystemExit, match="only reviewed"):
        prepare("feature/unreviewed")
    assert git(root, "branch", "--show-current") == "main"
    assert git(root, "rev-parse", "origin/main") == original


def test_reviewed_fast_forward_keeps_installed_custom_behavior(checkout):
    root = checkout
    installed = git(root, "rev-parse", "HEAD")
    git(root, "checkout", "-b", "reviewed-release")
    (root / "released.txt").write_text("reviewed upstream feature\n")
    git(root, "add", ".")
    git(root, "commit", "-m", "Reviewed release")
    reviewed = git(root, "rev-parse", "HEAD")
    git(root, "update-ref", "refs/remotes/origin/main", reviewed)
    git(root, "checkout", "main")
    plan = prepare()
    assert plan.auto_stash_ref is None
    assert plan.commit_count > 0
    before = _pull_updates(
        ["git"], "main", plan.auto_stash_ref, prompt_for_restore=False,
        gw_input_fn=None, discard_local_changes=False, keep_stash=True,
    )
    assert before == installed
    assert git(root, "rev-parse", "HEAD") == reviewed
    assert (root / "feature.txt").read_text() == "our behavior\n"
    assert (root / "released.txt").read_text() == "reviewed upstream feature\n"
    assert git(root, "status", "--porcelain") == ""
