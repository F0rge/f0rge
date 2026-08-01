# Branch rulesets (required checks)

Configured in GitHub **Settings → Rules → Rulesets** (not YAML). Keep this file
in sync when changing check names.

| Ruleset | Branches | Required checks |
|---------|----------|-----------------|
| `develop-pr-gate` | `develop` | `ci` |
| `main-pr-gate` | `main` | `ci`, `playwright smoke` |
| `baseline-no-delete-no-force-push` | `develop`, `main` | (deletion / non-ff only) |

- Aggregate job `ci` in [workflows/ci.yml](workflows/ci.yml) must stay named `ci`.
- Aggregate job `playwright smoke` in [workflows/e2e-smoke.yml](workflows/e2e-smoke.yml)
  always runs (passes when marrow is unaffected) so the main ruleset never blocks
  on a missing check.
