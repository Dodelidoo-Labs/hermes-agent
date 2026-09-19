"""The maintained fork installs reviewed fast-forwards, never discarding local work."""

from pathlib import Path


def maintained_update_branch(origin: str) -> str | None:
    canonical = origin.strip().rstrip("/").lower().removesuffix(".git")
    if canonical in {
        "https://github.com/dodelidoo-labs/hermes-agent",
        "git@github.com:dodelidoo-labs/hermes-agent",
        "ssh://git@github.com/dodelidoo-labs/hermes-agent",
    }:
        return "main"
    return None


def is_maintained_checkout(git_cmd: list[str], root: Path) -> bool:
    from hermes_cli.update_cmd_git import _get_origin_url
    return maintained_update_branch(_get_origin_url(git_cmd, root) or "") is not None


def require_official_zip_origin(root: Path) -> None:
    """Git may be broken here; never replace a fork with the official source ZIP."""
    import configparser
    from hermes_cli.banner import _canonical_github_remote, _OFFICIAL_REPO_CANONICAL

    config = configparser.ConfigParser(interpolation=None)
    try:
        with (root / ".git" / "config").open(encoding="utf-8") as stream:
            config.read_file(stream)
        origin = config.get('remote "origin"', "url", fallback="")
    except (OSError, configparser.Error):
        origin = ""
    if _canonical_github_remote(origin) != _OFFICIAL_REPO_CANONICAL:
        raise SystemExit(
            "ZIP update refused: origin is a fork or cannot be verified. "
            "Repair Git and update from your maintained origin; official source will not be installed.")


def check_maintained_update(git_cmd: list[str], root: Path, target: str) -> bool:
    """Refuse before branch switches/stashing, including noninteractive Desktop updates."""
    from hermes_cli.update_cmd_git import _get_origin_url
    from hermes_cli.update_cmd import _git_run

    branch = maintained_update_branch(_get_origin_url(git_cmd, root) or "")
    if branch is None:
        return False

    def read(*args):
        result = _git_run(git_cmd, list(args), root)
        if result.returncode != 0:
            raise SystemExit("Update refused: cannot verify the maintained checkout; local work was not changed.")
        return result.stdout.strip()

    if target != branch or read("branch", "--show-current") != branch:
        raise SystemExit(
            f"Update refused: this fork installs only reviewed {branch} updates while on {branch}. "
            "No branch was switched. Review and commit customizations to the fork first.")
    if read("status", "--porcelain", "--untracked-files=all"):
        raise SystemExit(
            "Update refused: this checkout has local edits. They have NOT been stashed or removed. "
            "Commit and review them into the maintained fork before updating.")
    result = _git_run(git_cmd, ["merge-base", "--is-ancestor", "HEAD", f"origin/{branch}"], root)
    if result.returncode != 0:
        raise SystemExit(
            "Update refused: local commits are unpublished, histories diverged, or ancestry could "
            "not be verified. Integrate the local work into the maintained fork first; "
            "the installed checkout was not reset.")
    return True
