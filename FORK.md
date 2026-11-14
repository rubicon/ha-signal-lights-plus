# FORK.md

This repository, `rubicon/ha-signal-lights-plus` ("Signal Lights Plus"), is a fork of
[prestomation/ha-signal-lights](https://github.com/prestomation/ha-signal-lights). It carries
new features (effects, acknowledge and snooze, actionable notifications, ZBT-2 LED support and
more) until they are accepted upstream. Each feature is built so it can be offered upstream as
its own pull request.

This file is fork-owned: upstream does not have it, so it never collides on merge. It records
every intentional difference from upstream so that taking in upstream changes stays predictable.

## Remotes

| Remote | Points to | Use |
|---|---|---|
| `origin` | `https://github.com/rubicon/ha-signal-lights-plus` | Where fork work lives and is released from |
| `upstream` | `https://github.com/prestomation/ha-signal-lights` | Fetch only. Contributions go upstream as pull requests from feature branches |

## Taking in upstream changes

1. `git fetch upstream`
2. Open an issue, create a `dev/<issue>-<slug>` branch from `main`, and merge `upstream/main` into it.
3. Resolve conflicts in that branch, using the divergence table below as the guide.
4. Merge through a pull request with all checks green. `main` only moves through pull requests.

Never use an update script that overwrites tracked files.

## Who owns which files

- **Upstream-owned files** are files upstream has and updates, such as `CHANGELOG.md`,
  `README.md`, `AGENTS.md`, `CONTRIBUTING.md`, `.github/workflows/*` and the integration code. In
  these files we follow upstream's conventions, even where they differ from ours. Any intentional
  change to one of them gets a row in the divergence table.
- **Fork-owned files** are files upstream does not have, such as this file. Fork operating
  instructions that would contradict upstream's own docs go in fork-owned files, never into
  upstream's docs.

Upstream's `LICENSE` (MIT) and attribution are kept as they are.

## Divergence table

One row per upstream-owned file this fork changes on purpose.

| File | What differs | Why | Tracking issue |
|---|---|---|---|
| `package.json` | `vitest` requirement raised from `^3.0.0` to `^4.1.11` | Fixes [GHSA-82fw-gwwq-j7x9](https://github.com/advisories/GHSA-82fw-gwwq-j7x9) in the test runner; Dependabot cannot open the fix without a lockfile. Remove this row when upstream takes the change | https://github.com/rubicon/ha-signal-lights-plus/issues/3 |

## Release mechanism

The fork releases the same way upstream does: a pull request that bumps `version` in
`custom_components/signal_lights/manifest.json` and adds a matching `CHANGELOG.md` section, after
which the Release workflow tags and publishes. This follows upstream's convention to keep the
workflows identical. The fork's own version tag scheme is still open (see Open decisions).

## Known fork-specific CI behavior

- **Coverage comment step on manual runs:** in `pytest and coverage`, the step
  "Generate coverage Comment" uses `py-cov-action/python-coverage-comment-action`, which refuses
  `workflow_dispatch` runs. A manually dispatched run therefore fails at that step even when the
  tests pass. Trigger CI through a pull request or a push to `main` instead.

## Open decisions

These will add rows to the divergence table when decided:

- **Release tag scheme.** Upstream's Release workflow accepts only `X.Y.Z` or PEP 440 pre-release
  versions. The fork needs a version that HACS sorts above the matching upstream release. The
  candidates are tested with AwesomeVersion before the first release that differs from upstream.
- **Dependabot.** The repository has no `package-lock.json`, so Dependabot cannot open fixes for
  JavaScript dependencies. The `vitest` alert is fixed by hand (see the `package.json` row above)
  and will be offered upstream as a small pull request. How future Dependabot pull requests on the
  fork are handled is still open.
