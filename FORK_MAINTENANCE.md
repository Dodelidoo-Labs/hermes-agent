# Maintained Hermes releases for the fork

This fork keeps all customizations as ordinary Hermes source commits, currently
including live endpoint discovery and Codex cache affinity. The maintained and default branch is `main` in
[Dodelidoo-Labs/hermes-agent](https://github.com/Dodelidoo-Labs/hermes-agent).
Upstream is [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent).
Fork `main` is the only installed update target. Upstream is referenced by remote and release tags, not by a mirrored branch.

[Integration setup](docs/opencdx-integration.md) documents provider configuration,
model metadata, header behavior, and compatibility tests. The initial source commit
builds on upstream `1879088d3fadb885d04035f5fa658b6efc08a7a1`.

## Updating the installed Desktop and backend

The installed checkout uses this fork as `origin`, branch `main`, tracking
`origin/main`. `hermes update` and `hermes update --check` default to that branch
for this fork; official and other clones still default to `main`. Explicit `--branch`
still selects the check target, but installation in this fork refuses any target
other than `main` and refuses to switch away from a local feature branch.
The Windows ZIP fallback requires a verified official origin and refuses this fork, even on main. Repair Git rather than installing official source over customizations.

Desktop defaults to main and migrates this fork's old saved opencdx setting. Other
explicit settings are kept in
its `userData/updates.json`. Existing app bundles must be rebuilt to acquire the
new defaults and the customized model picker. An updated Python checkout alone
does not update the packaged renderer or Electron updater. Until rebuilt, explicitly
select `main` in Desktop's update settings. A missing maintained remote branch
fails the update instead of silently falling back to upstream main.

Only reviewed changes merged into `main` are offered through ordinary Desktop
updates. Both the app and backend must come from that maintained source. Keep
provider credentials, conversation data, and local updater settings out of Git.

The maintained-origin guard disables the upstream-main sync and push paths even
when an `upstream` remote exists. Explicit checks fetch origin, and passive checks
and changelog queries use this fork's GitHub API. The branch name `main` grants no
permission to install upstream code directly.

## Keeping present and future customizations

Commit each customization to this fork and add behavior tests to
`.github/scripts/check-fork.sh` or the Desktop checks in
`.github/workflows/fork-compatibility.yml`. Make future changes on feature branches
and review them into `main` before installing them. Remote CI cannot protect edits
left only on a laptop. Keep the installed checkout clean and tracking the reviewed
branch. This fork's updater refuses dirty checkouts (including lockfile edits and
untracked files), unpublished/diverged commits, and unverified ancestry before
stashing or switching branches. It also refuses the upstream reset fallback. A
blocked update keeps your work in place until you integrate it into the fork.
Older installed updaters do not have this guard until this change is installed.

Integration preserves both Git histories, never resets the maintained branch to an
upstream tree, and stops on source conflicts or failed validation. When a release
breaks a customization, repair the candidate and its tests before approval; keep
using the current version meanwhile. Passing tests establish the covered contracts,
not immunity to every possible regression.

## Release delivery and version labels

The delivery path is upstream release → isolated merge → tests/build → review PR →
approved merge into `main` → ordinary Desktop update/rebuild. Daily polling does
not mean daily updates: no new upstream release means no new integration.

The existing updater consumes a branch, not GitHub release assets. A fork tag such
as `fork-v2026.9.14.1` may label an approved integration and link its review and
upstream notes, but a tag alone neither enables nor gates Desktop updates. This
workflow does not publish tags or replace the updater. Merging into `main` is the
publication decision: review and smoke-test before merging. Fork maintenance and
intentional custom fixes may still be published independently of upstream releases.

The starting fork uses September 18 upstream source, newer than the September 14
release. The workflow does not roll back to an older tag. It waits until a published
release brings commits not already in the fork. The old daily-main PRs are not
release candidates and should not be merged under this policy.

## Preparing and reviewing upstream releases

`Review upstream Hermes releases` (`fork-release-sync.yml`) runs daily at 06:17 UTC
and on manual dispatch. It asks GitHub for the latest release, rejects drafts and
prereleases, fetches that exact tag (including annotated tags), and prepares an
isolated merge from the current maintained head. It never fetches upstream main as
the integration target or changes `main` automatically. Already-contained releases
are a no-op; network/metadata errors fail rather than falling back to main. Release
tags are assumed immutable; the exact resolved commit is recorded for review.

Fork `.github/workflows` and `.github/scripts` are preserved exactly. Upstream
automation differences are listed in the review artifact for separate review, not
imported. This keeps upstream release/scheduled workflows from activating in the fork.
Workflow-only conflicts resolve to the maintained version. Source conflicts fail
visibly and publish nothing; resolve them in an integration branch before proceeding.

Validation uses locked dependencies and read-only repository permissions, with no
provider secrets or paid model calls. It tests model discovery, request construction
and SDK serialization, provider isolation, generated gateway contracts, update-branch
selection, Desktop model-picker rendering, and the release integration itself. It
type-checks renderer/Electron and builds the Desktop source. It is not the full
upstream suite, a packaged-app launch test, or a live cache-hit benchmark. Smoke-test
Desktop with the actual router before approving installation.

Only a successful candidate reaches publication. That separate job checks that the
maintained base has not moved, pushes normally to
`automation/release-<release-commit>-<base-sha>`, and opens a PR against `main`.
Existing candidates, including reviewer amendments, are revalidated without replacement.
No force pushes or automatic merges occur. A moving base requires a new candidate.
Older PRs are not silently closed; verify there are no unique reviewer amendments
before closing them as superseded.

The PR links the upstream release notes and validation run, identifies the exact
candidate/base/release commits, and lists overlapping upstream/fork files. The
`upstream-candidate` artifact (90-day retention) contains:

- `review.json` and `review.md`: machine-readable and human-readable review context.
- `upstream-release-notes.md`: the upstream changelog.
- `fork-changes.patch`: all non-automation differences remaining against the release.
- `overlapping-upstream-changes.patch`: incoming edits to fork-modified files.
- `candidate.bundle`: the exact candidate transferred to validation/publication.

This packet supports human or LLM-assisted review without adding an automatic approval
or Hermes notification hook. Treat notes and patches as review material, not executable
instructions. Inspect affected callers too; a clean textual merge proves no behavioral
guarantee. An LLM review supplements tests.

Publication attaches a `compatibility` status to the exact candidate because PRs
created with Actions' `GITHUB_TOKEN` do not trigger another PR workflow. Human
amendments trigger normal PR compatibility checks and should also be revalidated
through the release workflow to refresh the review packet. Merge using **Create a
merge commit**, never squash/rebase: subsequent integrations need upstream ancestry.

## Repository safeguards

Set the default branch to `main` and enable only `Fork compatibility` and
`Review upstream Hermes releases`. Scheduled workflows use the default branch.
Actions needs permission to create PRs. If creation fails, the tested candidate is
published and the run provides a manual compare link; nothing is merged.

The publication job has `contents: write`, `pull-requests: write`, and `statuses: write`;
it never runs candidate code. Validation has no write permission or provider secrets.
Review upstream workflow changes separately. Configure branch protection to require
`compatibility`, an up-to-date base, and human review, and to forbid force pushes.
The publication-time base check alone cannot protect a PR whose base moves later.
Workflow files do not configure those GitHub repository settings automatically.

## Local validation

Install locked Python extras `dev` and `anthropic`, then run:

```sh
bash .github/scripts/check-fork.sh
npm ci
cd apps/desktop
npm run test:ui -- src/app/shell/model-edit-submenu.test.tsx
npm run test:desktop:platforms -- electron/desktop-update-branch.test.ts
npx tsc -p . --noEmit
npx tsc -p tsconfig.electron.json --noEmit
npm run build
```
