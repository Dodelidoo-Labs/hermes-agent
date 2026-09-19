# Maintained Hermes branch for openCDX

This fork keeps live endpoint discovery and Codex cache affinity as ordinary Hermes
source commits. The maintained and default branch is `opencdx` in
[Dodelidoo-Labs/hermes-agent](https://github.com/Dodelidoo-Labs/hermes-agent).
The upstream project is [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent).
Fork `main` remains an upstream reference; it is not the installed update target.

[Integration setup](docs/opencdx-integration.md) documents the provider configuration,
live model metadata, header behavior, and compatibility tests. The initial source
commit builds on upstream `1879088d3fadb885d04035f5fa658b6efc08a7a1`.

## Updating installed Hermes

The installed checkout should use `origin` pointing to this fork, branch `opencdx`,
and tracking `origin/opencdx`. Keep `upstream` pointing to NousResearch for reference.
`hermes update` and `hermes update --check` default to `opencdx` when the actual
origin URL is this fork; official and other clones still default to `main`.
An explicit `--branch` always wins. Switching to `--branch main` deliberately leaves
these maintained changes behind. The non-main Windows ZIP fallback refuses the
operation instead of silently downloading official main.

Normal updates consume reviewed commits already merged into `origin/opencdx`.
Do not point the updater directly at upstream main. No updater configuration,
provider credentials, or conversation data belong in this repository.

## Integrating upstream

`Review upstream Hermes updates` (`opencdx-upstream-sync.yml`) runs daily at 06:17 UTC
and on manual dispatch. It fetches current upstream main and builds an isolated merge
candidate from the current maintained head. It never changes `opencdx` automatically.

The workflow preserves `.github/workflows` and the validation driver
`.github/scripts/check-opencdx.sh` exactly from the maintained branch.
Upstream automation differences are listed in the run summary for separate review;
they are not imported by routine source integration. This prevents unexpected upstream
release/scheduled workflows from activating in the fork and avoids asking a write token
to modify workflow definitions. Workflow-only conflicts are resolved to the maintained
version. Any source conflict fails visibly and publishes nothing.

Candidate validation runs with read-only repository permissions. It checks Python
model discovery, request construction and SDK serialization, provider isolation,
generated gateway contracts, updater branch selection, Desktop model-picker rendering,
and renderer TypeScript. It uses locked dependencies and does not invoke paid models.
These focused checks establish the maintained behavior; they are not the entire upstream
suite or a live cache-hit benchmark.

Only a successful candidate reaches the separate publication job. It checks that the
maintained base has not moved, then uses an ordinary push to
`automation/upstream-<upstream-sha>-<base-sha>` and opens a PR targeting `opencdx`.
Existing candidates are revalidated, including human amendments. There are no force
pushes and no automatic merges. Concurrent amendments or a moving maintained base
cause a failure and require a rerun. Earlier candidate PRs are not silently closed.
The PR links the workflow run and names the exact validated commit.

Review source changes and merge the PR normally after validation. If upstream changes
break our behavior or tests, fix the candidate and rerun compatibility CI. When upstream
implements the same fixes, remove redundant fork changes only after the invariant tests
continue to pass. Never resolve a conflict by replacing the maintained tree with upstream.

## Repository setup and workflow maintenance

Set the fork default branch to `opencdx`; scheduled workflows run only from the default
branch. Enable only `openCDX compatibility` and `Review upstream Hermes updates`.
Inherited upstream workflows are absent from the active workflow directory; their
original definitions remain in upstream Git history. Routine integration cannot
reintroduce or alter them. When permitted, enable Actions' permission to create pull requests. Without that
setting, the tested candidate is still published and the failed run summary provides
a compare link for manually opening its PR; the automation never approves a PR. The sync publication job requests `contents: write` and `pull-requests: write`;
validation jobs have neither write permission nor provider secrets.

Review upstream workflow changes separately when needed. Enabling or changing any
workflow is a repository-maintenance decision, not an automatic side effect of importing
Hermes source. Branch protection should require compatibility validation and human review
before merging into `opencdx`. The automation itself never bypasses that review.

For local validation, install locked Python extras `dev` and `anthropic`, then run:

```sh
bash .github/scripts/check-opencdx.sh
npm ci
cd apps/desktop
npm run test:ui -- src/app/shell/model-edit-submenu.test.tsx
npx tsc -p . --noEmit
```
