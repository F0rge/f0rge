# gh CLI and API commands

Replace `OWNER`, `REPO`, and issue numbers. Prefer writing bodies to temp files (`--body-file`) to avoid shell escaping issues.

---

## Prerequisites

```bash
gh auth status
gh repo view --json nameWithOwner -q .nameWithOwner   # OWNER/REPO
```

Upgrade for native sub-issue support:

```bash
brew upgrade gh   # need >= 2.94.0 for --parent, --blocked-by
gh version
```

---

## Single issue

```bash
gh issue create \
  --title "feat(area): short outcome" \
  --body-file /tmp/issue-body.md \
  --label "enhancement"
```

Capture URL:

```bash
gh issue create --title "..." --body-file /tmp/issue-body.md --json url,number -q '"#\(.number) \(.url)"'
```

---

## Parent + sub-issues (gh >= 2.94)

### 1. Parent

```bash
PARENT=$(gh issue create \
  --title "epic: overall outcome" \
  --body-file /tmp/parent-body.md \
  --json number -q .number)
echo "Parent: #$PARENT"
```

### 2. Sub-issues

```bash
SUB1=$(gh issue create \
  --title "backend: first slice" \
  --body-file /tmp/sub1-body.md \
  --parent "$PARENT" \
  --json number -q .number)

SUB2=$(gh issue create \
  --title "frontend: second slice" \
  --body-file /tmp/sub2-body.md \
  --parent "$PARENT" \
  --json number -q .number)
```

### 3. Dependencies between sub-issues

```bash
gh issue edit "$SUB2" --add-blocked-by "$SUB1"
```

### 4. Verify hierarchy

```bash
gh issue view "$PARENT" --json title,subIssues,subIssuesSummary
gh issue view "$SUB2" --json title,parent
```

---

## Parent + sub-issues (REST fallback, gh < 2.94)

Sub-issue linking uses the issue **database id** (`id`), not the issue number.

### Get issue id from number

```bash
OWNER=leo-org REPO=my-repo
parent_id=$(gh api "repos/$OWNER/$REPO/issues/$PARENT" --jq .id)
sub_id=$(gh api "repos/$OWNER/$REPO/issues/$SUB1" --jq .id)
```

### Link sub-issue to parent

```bash
gh api \
  --method POST \
  "repos/$OWNER/$REPO/issues/$PARENT/sub_issues" \
  -f sub_issue_id="$sub_id"
```

### Create sub-issue and link in one flow

```bash
# Create standalone issue first
SUB1=$(gh issue create --title "..." --body-file /tmp/sub1.md --json number -q .number)
sub_id=$(gh api "repos/$OWNER/$REPO/issues/$SUB1" --jq .id)

# Attach to parent
gh api --method POST "repos/$OWNER/$REPO/issues/$PARENT/sub_issues" \
  -f sub_issue_id="$sub_id"
```

### List sub-issues

```bash
gh api "repos/$OWNER/$REPO/issues/$PARENT/sub_issues"
```

---

## Other repo flag

```bash
gh issue create -R OWNER/REPO --title "..." --body-file /tmp/body.md
```

---

## Labels and projects

```bash
gh issue create --title "..." --body-file /tmp/body.md \
  --label "enhancement" --label "agent-ready"

# Projects need extra auth scope
gh auth refresh -s project
gh issue create --title "..." --body-file /tmp/body.md --project "Roadmap"
```

---

## Update parent after children exist

If the parent body has a placeholder sub-issue table, patch it:

```bash
gh issue edit "$PARENT" --body-file /tmp/parent-body-updated.md
```

Or add a tracking comment:

```bash
gh issue comment "$PARENT" --body "Sub-issues created: #$SUB1, #$SUB2"
```
