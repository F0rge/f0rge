#!/usr/bin/env bash
# Group all open GitHub issues under a single parent issue (sub-issue links)
# and generate docs/issues/remediation-plan.md for the remediation branch.
#
# Requires: gh CLI authenticated with issues:read + issues:write on the repo.
# Run from repo root:
#   ./scripts/group-open-issues.sh
#
# Optional env:
#   PARENT_TITLE   — override parent issue title
#   PARENT_BODY    — override parent issue body (markdown file path)
#   DRY_RUN=1      — list issues and print plan without creating/linking
#   REPO           — owner/name (default: leothesouthafrican/health-tracker)

set -euo pipefail

REPO="${REPO:-leothesouthafrican/health-tracker}"
OWNER="${REPO%%/*}"
NAME="${REPO#*/}"
PARENT_TITLE="${PARENT_TITLE:-Open issues remediation bundle}"
PLAN_PATH="docs/issues/remediation-plan.md"
DRY_RUN="${DRY_RUN:-0}"

die() { echo "error: $*" >&2; exit 1; }

command -v gh >/dev/null || die "gh CLI not found"
command -v python3 >/dev/null || die "python3 not found"

# Verify issues API access before doing anything destructive.
if ! gh api "repos/${REPO}/issues?state=open&per_page=1" --jq 'type' >/dev/null 2>&1; then
  die "$(cat <<'EOF'
GitHub Issues API returned 403. The authenticated token needs issues:read and issues:write.

Fix (pick one):
  1. GitHub → Settings → Applications → Cursor → Configure → Repository access
     → health-tracker → enable Issues (read & write), then re-run this script.
  2. Run locally with a PAT that has repo scope:
       GH_TOKEN=ghp_... ./scripts/group-open-issues.sh
EOF
)"
fi

# Fetch open issues (exclude pull requests).
mapfile -t OPEN_ISSUES_JSON < <(
  gh api "repos/${REPO}/issues?state=open&per_page=100" \
    --paginate \
    --jq '.[] | select(.pull_request == null) | {number, id, title, labels: [.labels[].name], body, url}'
)

if [[ "${#OPEN_ISSUES_JSON[@]}" -eq 0 ]]; then
  echo "No open issues found in ${REPO}."
  exit 0
fi

echo "Found ${#OPEN_ISSUES_JSON[@]} open issue(s)."

# Skip issues that already have a parent (idempotent re-run).
FILTERED=()
for row in "${OPEN_ISSUES_JSON[@]}"; do
  num=$(echo "$row" | python3 -c "import sys,json; print(json.load(sys.stdin)['number'])")
  parent=$(gh api "repos/${REPO}/issues/${num}/parent" 2>/dev/null || true)
  if [[ -n "$parent" && "$parent" != "null" && "$parent" != *"Not Found"* ]]; then
    echo "  skip #${num} (already has parent)"
    continue
  fi
  FILTERED+=("$row")
done

if [[ "${#FILTERED[@]}" -eq 0 ]]; then
  echo "All open issues already have a parent. Nothing to link."
  exit 0
fi

# Build parent issue body.
PARENT_BODY_FILE="${PARENT_BODY:-}"
if [[ -z "$PARENT_BODY_FILE" ]]; then
  PARENT_BODY_FILE=$(mktemp)
  {
    echo "## Purpose"
    echo
    echo "Parent tracker for all currently open issues. Each sub-issue is fixed in"
    echo "branch \`cursor/open-issues-remediation-c55e\` with **one commit per issue**."
    echo
    echo "## Workflow"
    echo
    echo "1. Implement fixes on \`cursor/open-issues-remediation-c55e\` (one commit per sub-issue)."
    echo "2. Open PR → \`develop\`; CI (\`ci-develop.yml\`) must be green."
    echo "3. Merge to \`develop\`; run dev smoke tests on https://health-dev.leo-figueiredo.com."
    echo "4. Open PR \`develop\` → \`main\` for production review."
    echo
    echo "## Sub-issues"
    echo
    for row in "${FILTERED[@]}"; do
      python3 -c "import json,sys; d=json.load(sys.stdin); print(f'- [ ] #{d[\"number\"]} — {d[\"title\"]}')" <<<"$row"
    done
    echo
    echo "## Plan"
    echo
    echo "See [\`docs/issues/remediation-plan.md\`](docs/issues/remediation-plan.md) on branch \`cursor/open-issues-remediation-c55e\`."
  } >"$PARENT_BODY_FILE"
fi

if [[ "$DRY_RUN" == "1" ]]; then
  echo "DRY_RUN=1 — would create parent issue and link:"
  for row in "${FILTERED[@]}"; do
    python3 -c "import json,sys; d=json.load(sys.stdin); print(f'  #{d[\"number\"]} {d[\"title\"]}')" <<<"$row"
  done
  exit 0
fi

# Create parent issue.
PARENT_JSON=$(gh api "repos/${REPO}/issues" -X POST \
  -f title="$PARENT_TITLE" \
  -F body=@"$PARENT_BODY_FILE")
PARENT_NUMBER=$(echo "$PARENT_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['number'])")
PARENT_URL=$(echo "$PARENT_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['html_url'])")

echo "Created parent issue #${PARENT_NUMBER}: ${PARENT_URL}"

# Link each open issue as a sub-issue (REST uses internal issue id, not number).
for row in "${FILTERED[@]}"; do
  read -r child_num child_id child_title <<<"$(
    python3 -c "import json,sys; d=json.load(sys.stdin); print(d['number'], d['id'], d['title'])" <<<"$row"
  )"
  echo "  linking #${child_num} — ${child_title}"
  echo "{\"sub_issue_id\": ${child_id}}" \
    | gh api "repos/${REPO}/issues/${PARENT_NUMBER}/sub_issues" -X POST --input -
done

echo "Linked ${#FILTERED[@]} sub-issue(s) under #${PARENT_NUMBER}."

# Generate remediation plan markdown.
mkdir -p "$(dirname "$PLAN_PATH")"
python3 - "$PLAN_PATH" "$PARENT_NUMBER" "$PARENT_URL" "${FILTERED[@]}" <<'PY'
import json
import sys
from datetime import datetime, timezone

plan_path = sys.argv[1]
parent_number = sys.argv[2]
parent_url = sys.argv[3]
issues = [json.loads(row) for row in sys.argv[4:]]

AGENT_RULES = {
    "fastapi-backend": "Routers ≤3 lines; services via Depends(); `from __future__ import annotations`; ruff clean; pytest for new behavior.",
    "frontend-dev": "Next.js 16 App Router; TypeScript strict; shadcn/ui; mobile-first; loading/error/empty states.",
    "data-engineer": "Idempotent ETL; versioned source data; ingredient/tag normalization.",
    "data-scientist": "AI prompt contracts; confidence scores; embedding dim 1024; BYOK via resolve_llm_credentials.",
    "devops": "docker-compose.{dev,prod}.yml; RUN_MIGRATIONS only on backend; Coolify bind-mount caveats.",
    "qa-engineer": "QA Gate Report; live-server walkthrough required; dev smoke on health-dev*.leo-figueiredo.com before main PR.",
}

def guess_agents(issue: dict) -> list[str]:
    text = f"{issue['title']}\n{issue.get('body') or ''}".lower()
    labels = {l.lower() for l in issue.get("labels", [])}
    agents: list[str] = []

    def add(a: str) -> None:
        if a not in agents:
            agents.append(a)

    if labels & {"backend", "api", "fastapi"} or any(k in text for k in ("backend/", "fastapi", "router", "alembic", "migration")):
        add("fastapi-backend")
    if labels & {"frontend", "ui", "nextjs"} or any(k in text for k in ("frontend/", "next.js", "react", "tailwind", "checkin")):
        add("frontend-dev")
    if labels & {"data", "etl", "ingredient"} or any(k in text for k in ("ingredient", "fodmap", "histamine", "seed", "lookup table")):
        add("data-engineer")
    if labels & {"ai", "ml", "embedding", "llm"} or any(k in text for k in ("openrouter", "embedding", "vision", "prompt", "rag")):
        add("data-scientist")
    if labels & {"devops", "infra", "docker"} or any(k in text for k in ("docker-compose", "coolify", "deploy", "migration entrypoint")):
        add("devops")

    if not agents:
        add("fastapi-backend")
    add("qa-engineer")
    return agents

lines: list[str] = []
lines.append("# Open issues remediation plan")
lines.append("")
lines.append(f"**Parent issue:** [#{parent_number}]({parent_url})")
lines.append(f"**Branch:** `cursor/open-issues-remediation-c55e` (off `develop`)")
lines.append(f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
lines.append("")
lines.append("## Workflow")
lines.append("")
lines.append("```mermaid")
lines.append("flowchart LR")
lines.append("  A[develop] --> B[cursor/open-issues-remediation-c55e]")
lines.append("  B --> C[one commit per sub-issue]")
lines.append("  C --> D[PR to develop]")
lines.append("  D --> E[ci-develop.yml green]")
lines.append("  E --> F[merge develop]")
lines.append("  F --> G[dev smoke tests]")
lines.append("  G --> H[PR develop to main]")
lines.append("```")
lines.append("")
lines.append("### Commit convention")
lines.append("")
lines.append("One atomic commit per sub-issue, in dependency order:")
lines.append("")
lines.append("```")
lines.append("fix(scope): short description (#NN)")
lines.append("feat(scope): short description (#NN)")
lines.append("```")
lines.append("")
lines.append("### CI gates")
lines.append("")
lines.append("| Stage | Trigger | Checks |")
lines.append("|-------|---------|--------|")
lines.append("| PR → `develop` | `ci-develop.yml` | ruff + pytest + frontend lint/typecheck/build |")
lines.append("| PR → `main` | `ci-main.yml` | same + prod-shaped frontend build |")
lines.append("")
lines.append("### Dev smoke tests (post-merge to develop)")
lines.append("")
lines.append("Run against https://health-dev.leo-figueiredo.com (API: https://health-dev-api.leo-figueiredo.com):")
lines.append("")
lines.append("1. PIN login → `ht_session` cookie set.")
lines.append("2. Golden path for **each** sub-issue fix (see per-issue acceptance below).")
lines.append("3. Tail backend logs on Pi during test window — no hidden 500s.")
lines.append("4. If migrations: verify `alembic_version` on dev Postgres matches new revision.")
lines.append("5. qa-engineer produces QA Gate Report with VERDICT: PASS before opening PR to `main`.")
lines.append("")
lines.append("## Sub-agent rules (all issues)")
lines.append("")
lines.append("Each implementing agent reads `.claude/projects/-Users-leo-development-health-tracker/memory/` before starting and writes back durable findings when done.")
lines.append("")
lines.append("| Agent | When to use | Key rules |")
lines.append("|-------|-------------|-----------|")
for agent, rules in AGENT_RULES.items():
    lines.append(f"| `{agent}` | see per-issue table | {rules} |")
lines.append("")
lines.append("## Issues (execution order)")
lines.append("")

for idx, issue in enumerate(sorted(issues, key=lambda i: i["number"]), start=1):
    agents = guess_agents(issue)
    labels = ", ".join(issue.get("labels") or []) or "—"
    lines.append(f"### {idx}. #{issue['number']} — {issue['title']}")
    lines.append("")
    lines.append(f"- **URL:** {issue['url']}")
    lines.append(f"- **Labels:** {labels}")
    lines.append(f"- **Commit:** `fix|feat(scope): … (#{issue['number']})`")
    lines.append(f"- **Agents:** {' → '.join(agents)}")
    lines.append("")
    lines.append("| Step | Agent | Task |")
    lines.append("|------|-------|------|")
    for a in agents:
        if a == "qa-engineer":
            lines.append(f"| Gate | `{a}` | Live-server walkthrough + dev smoke; QA Gate Report |")
        else:
            lines.append(f"| Implement | `{a}` | Implement per issue body; follow agent playbook |")
    lines.append("")
    body = (issue.get("body") or "").strip()
    if body:
        preview = body[:400].replace("\n", " ")
        if len(body) > 400:
            preview += "…"
        lines.append(f"**Summary:** {preview}")
        lines.append("")
    lines.append("---")
    lines.append("")

lines.append("## Boundaries")
lines.append("")
lines.append("- **Always:** branch off up-to-date `develop`; one commit per issue; run local pytest/lint before push.")
lines.append("- **Ask first:** prod DB backfills; schema drops; Coolify env changes; force-push.")
lines.append("- **Never:** `--no-verify`; secrets in code; skip dev smoke before main PR.")
lines.append("")

with open(plan_path, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print(f"Wrote {plan_path}")
PY

echo "Done. Parent: ${PARENT_URL}"
