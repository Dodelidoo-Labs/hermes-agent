"""Prepare a release integration and a review packet without publishing anything."""

import argparse
import json
import os
from pathlib import Path
import subprocess


PROTECTED_PATHS = (".github/workflows", ".github/scripts")


def git(repo, *args, check=True):
    return subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args], cwd=repo,
        check=check, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )


def ancestor(repo, older, newer):
    result = git(repo, "merge-base", "--is-ancestor", older, newer, check=False)
    if result.returncode not in (0, 1):
        raise RuntimeError(result.stderr)
    return result.returncode == 0


def published_tag(repo, release):
    if release.get("draft") is not False or release.get("prerelease") is not False:
        raise ValueError("Only published, non-prerelease releases may be integrated")
    tag = release.get("tag_name")
    if not release.get("published_at") or not isinstance(tag, str) or not tag:
        raise ValueError("Release must have a published date and tag")
    git(repo, "check-ref-format", f"refs/tags/{tag}")
    return tag


def changed_paths(repo, older, newer):
    return set(filter(None, git(repo, "diff", "--name-only", "-z", older, newer).stdout.split("\0")))


def protected(path):
    return any(path == prefix or path.startswith(prefix + "/") for prefix in PROTECTED_PATHS)


def review_packet(repo, release, base, upstream, candidate):
    common = git(repo, "merge-base", base, upstream).stdout.strip()
    local = {p for p in changed_paths(repo, common, base) if not protected(p)}
    incoming = changed_paths(repo, common, upstream)
    overlap = sorted(local & incoming)
    return {
        "release": release,
        "base": base,
        "upstream": upstream,
        "candidate": candidate,
        "common_base": common,
        "fork_changed_files": sorted(local),
        "overlapping_files": overlap,
        "upstream_automation_changes": sorted(p for p in incoming if protected(p)),
        "integration_stat": git(repo, "diff", "--shortstat", base, candidate).stdout.strip(),
    }


def review_markdown(packet):
    release = packet["release"]
    overlap = packet["overlapping_files"]
    lines = [
        f"Integrate upstream release **{release['tag_name']}** into `main`.", "",
        f"[Upstream release notes]({release['html_url']}) · published {release['published_at']}",
        "", packet["integration_stat"], "",
        "### Review our customizations", "",
        f"Upstream touches **{len(overlap)}** of the **{len(packet['fork_changed_files'])}** "
        "files carrying fork changes since the common upstream baseline.", "",
        *([f"- `{p}`" for p in overlap] or ["No directly overlapping files."]), "",
        "The review artifact includes the complete fork diff and the incoming changes to these files. "
        "Inspect affected callers too: absence of textual conflicts does not prove compatibility.", "",
        "### Validation and approval", "",
        "This PR is published only after compatibility tests, generated contracts, Desktop tests, "
        "TypeScript checks, and a Desktop source build pass. It is not a packaged-app launch test "
        "or a live provider/cache-hit test.", "",
        "- [ ] Review the upstream notes and fork-impact artifact (human or LLM-assisted).",
        "- [ ] Verify existing and newly added custom behavior has regression coverage.",
        "- [ ] Smoke-test Desktop with the real router before approving installation.",
        "- [ ] Confirm validation still matches the current PR head and maintained base.", "",
        "Merge with **Create a merge commit**, never squash/rebase. A changed base or amended "
        "candidate requires fresh validation. Nothing merges automatically.", "",
        "### Exact revisions", "",
        f"- Maintained base: `{packet['base']}`",
        f"- Upstream release commit: `{packet['upstream']}`",
        f"- Validated candidate: `{packet['candidate']}`", "",
        "Fork workflows and automation scripts are retained from the maintained branch. "
        "Their upstream changes are listed separately in the artifact, not imported.", "",
    ]
    return "\n".join(lines)


def prepare(repo, release, upstream_url, output):
    """Merge only the published tag, preserving both histories and fork automation."""
    tag = published_tag(repo, release)
    if git(repo, "status", "--porcelain").stdout:
        raise RuntimeError("Candidate preparation requires a clean checkout")
    base = git(repo, "rev-parse", "HEAD").stdout.strip()
    git(repo, "fetch", "--no-tags", upstream_url, f"refs/tags/{tag}")
    upstream = git(repo, "rev-parse", "FETCH_HEAD^{commit}").stdout.strip()
    result = {"base": base, "upstream": upstream, "tag": tag, "candidate": ""}
    # The fork currently starts AFTER the latest release. Never downgrade it.
    if ancestor(repo, upstream, base):
        return result
    branch = f"automation/release-{upstream[:12]}-{base[:12]}"
    existing = git(repo, "ls-remote", "origin", f"refs/heads/{branch}").stdout.strip()
    if existing:
        git(repo, "fetch", "origin", f"refs/heads/{branch}")
        if not ancestor(repo, base, "FETCH_HEAD") or not ancestor(repo, upstream, "FETCH_HEAD"):
            raise RuntimeError("Existing candidate does not contain both maintained and release histories")
        git(repo, "checkout", "--detach", "FETCH_HEAD")
    else:
        git(repo, "merge", "--no-ff", "--no-commit", upstream, check=False)
        # A failed merge without MERGE_HEAD must not become a fabricated integration.
        git(repo, "rev-parse", "--verify", "MERGE_HEAD")
        git(repo, "rm", "-rf", "--ignore-unmatch", "--", *PROTECTED_PATHS)
        git(repo, "restore", f"--source={base}", "--staged", "--worktree", "--", *PROTECTED_PATHS)
        conflicts = git(repo, "diff", "--name-only", "--diff-filter=U").stdout.strip()
        if conflicts:
            git(repo, "merge", "--abort")
            raise RuntimeError(f"Source conflicts require manual resolution; nothing published:\n{conflicts}")
        git(repo, "commit", "-m", f"Merge upstream Hermes release {tag}; retain fork automation")
    git(repo, "diff", "--exit-code", base, "HEAD", "--", *PROTECTED_PATHS)
    candidate = git(repo, "rev-parse", "HEAD").stdout.strip()
    result.update(candidate=candidate, branch=branch)
    packet = review_packet(repo, release, base, upstream, candidate)
    output.mkdir(parents=True, exist_ok=True)
    (output / "review.json").write_text(json.dumps(packet, indent=2) + "\n")
    (output / "review.md").write_text(review_markdown(packet))
    (output / "upstream-release-notes.md").write_text(release.get("body") or "No upstream release notes provided.")
    (output / "fork-changes.patch").write_text(git(repo, "diff", upstream, candidate, "--", ".", ":!.github").stdout)
    overlap = packet["overlapping_files"]
    (output / "overlapping-upstream-changes.patch").write_text(
        git(repo, "diff", packet["common_base"], upstream, "--", *overlap).stdout if overlap else "")
    git(repo, "bundle", "create", str(output / "candidate.bundle"), "HEAD", f"^{base}")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--upstream-url", default="https://github.com/NousResearch/hermes-agent.git")
    args = parser.parse_args()
    result = prepare(Path.cwd(), json.loads(args.release.read_text()), args.upstream_url, args.output.resolve())
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as stream:
            stream.writelines(f"{key}={value}\n" for key, value in result.items())
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
