# Branch rulesets (required checks)

Configured in GitHub **Settings → Rules → Rulesets** (not YAML). Keep this file
in sync when changing check names.

| Ruleset | Branches | Required checks |
|---------|----------|-----------------|
| `main-pr-gate` | `main` | `ci`, `playwright smoke` |
| `baseline-no-delete-no-force-push` | `main` | (deletion / non-ff only) |

**Policy:** pull requests go to `main`. Leo approves every production release. Do not enable auto-merge. A remote `develop` ref may still exist and is not an approved long-lived branch. Ruleset `develop-pr-gate` may also still exist. Do not delete that ruleset or the ref from this document: deleting the ruleset does not delete commits, and deleting the ref only removes the branch pointer. Review the commits that are only on that ref, and the Airflow `tracking_ref` values, before either change.

- Aggregate job `ci` in [workflows/ci.yml](workflows/ci.yml) must stay named `ci`.
- Aggregate job `playwright smoke` in [workflows/e2e-smoke.yml](workflows/e2e-smoke.yml)
  always runs (passes when marrow is unaffected) so the main ruleset never blocks
  on a missing check.



The required contexts `ci` and `playwright smoke` are the current ruleset names. They are not the ADR architecture gate and they are not a production release approval. This file does not change GitHub settings.
## Git flow (trunk-based, main only)

Do not open a `develop` branch workflow. A remote `develop` ref may still exist; it is not an approved long-lived branch. Pull requests go to `main`. Leo approves every production release. A merge to `main` is not that approval. Do not enable auto-merge.

- **Trunk-based development.** Everyone integrates into `main` continuously.
- **Short-lived feature branches off `main`.** Name them `<type>/<short-kebab-description>`, where type is `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, or `hotfix` (for example `feat/peach-policy-pages`, `fix/tour-last-step`). Agent-created branches may keep their tool prefix (`cursor/…`). Branch from up-to-date `origin/main`; keep a branch to a few days and one concern.
- **PRs into `main` only.** Never open a PR against `develop` or any other branch. CI (`ci`, plus `playwright smoke` when required) must be green before merge.
- **Squash merge** with a clean conventional-commit title (`feat(scope): …`). Delete the branch after merge.
- **Committed deploy files name `main`.** They describe Railway services (Marrow, Firstout, DasKasas) and Coolify for dk. That is not a live check. A merge to `main` is not by itself a production release approval.
- **No long-lived branches.** No `develop`, `staging`, `release/*`, or per-environment branches. Rebase or merge `origin/main` into your branch to stay current; never merge another feature branch into yours.
- **Hotfixes are just PRs into `main`** (`hotfix/<desc>` or `fix/<desc>`), same CI and squash merge.
- Never force-push `main`. Force-pushing your own feature branch is fine when needed.
- PRs target `main`. Historical host/environment names do not authorize another branch workflow. Airflow still has committed `develop` bundle references; reconcile their consumers separately before changing or deleting that ref.
