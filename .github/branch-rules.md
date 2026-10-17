# Branch rulesets (required checks)

Configured in GitHub **Settings → Rules → Rulesets** (not YAML). Keep this file
in sync when changing check names.

| Ruleset | Branches | Required checks |
|---------|----------|-----------------|
| `main-pr-gate` | `main` | `ci`, `playwright smoke` |
| `baseline-no-delete-no-force-push` | `main` | (deletion / non-ff only) |

**`main` is the only protected, long-lived, and deployed branch.** There is no
`develop` branch workflow and no develop environment. If GitHub still lists a
`develop-pr-gate` ruleset or `develop` in the baseline ruleset, remove it in
Settings → Rules → Rulesets (it is stale).

- Aggregate job `ci` in [workflows/ci.yml](workflows/ci.yml) must stay named `ci`.
- Aggregate job `playwright smoke` in [workflows/e2e-smoke.yml](workflows/e2e-smoke.yml)
  always runs (passes when marrow is unaffected) so the main ruleset never blocks
  on a missing check.

## Git flow (trunk-based, main only)

There is **no `develop` branch workflow and no develop environment**. `main` is the only long-lived branch and the only deployed branch. Merging to `main` is deploying.

- **Trunk-based development.** Everyone integrates into `main` continuously.
- **Short-lived feature branches off `main`.** Name them `<type>/<short-kebab-description>`, where type is `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, or `hotfix` (for example `feat/peach-policy-pages`, `fix/tour-last-step`). Agent-created branches may keep their tool prefix (`cursor/…`). Branch from up-to-date `origin/main`; keep a branch to a few days and one concern.
- **PRs into `main` only.** Never open a PR against `develop` or any other branch. CI (`ci`, plus `playwright smoke` when required) must be green before merge.
- **Squash merge** with a clean conventional-commit title (`feat(scope): …`). Delete the branch after merge.
- **`main` is the only deployed branch.** Railway services (Marrow, Firstout, Vellano) track `main`; Coolify deploys dk from `main`. A merge to `main` ships to the live environment.
- **No long-lived branches.** No `develop`, `staging`, `release/*`, or per-environment branches. Rebase or merge `origin/main` into your branch to stay current; never merge another feature branch into yours.
- **Hotfixes are just PRs into `main`** (`hotfix/<desc>` or `fix/<desc>`), same CI and squash merge.
- Never force-push `main`. Force-pushing your own feature branch is fine when needed.
- Hostnames or Railway environments still *named* `develop`, `app-dev`, or `api-dev` are names only, or are retired. They do not imply a develop branch, and nothing deploys from one.
