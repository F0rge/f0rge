#!/usr/bin/env bash
#
# Stages shared by the per-App switch wizards in this directory. Not run directly:
# dk.sh, envmon.sh, buycycle.sh, daskasas.sh, marrow.sh and firstout.sh set a few
# variables, source this file, then call switch_pi or switch_railway.
#
# _wizard.sh is the wizard skill's library, copied unchanged from
# .agents/skills/wizard/template.sh. Do not hand-edit it.
#
# You perform every dashboard step and type every token. Tokens go from your
# clipboard straight into `gh secret set`; this script never sees or prints one.
# The secret names are the ones .github/workflows/cd.yml reads.

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=_wizard.sh
source "$HERE/_wizard.sh"
cd "$HERE/../../.."

if ! command -v gh >/dev/null 2>&1 || ! gh auth status >/dev/null 2>&1; then
  echo "Install the GitHub CLI and run 'gh auth login' first." >&2
  exit 1
fi
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
OWNER=${REPO%%/*}
REGISTRY="ghcr.io/$(printf '%s' "$OWNER" | tr '[:upper:]' '[:lower:]')"
COMMIT=""

# deployables JQ: one line per Project of this App, from the deploy blocks cd.yml releases.
deployables() { node .github/deploy/deployables.mjs | jq -r --arg app "$APP" ".[] | select(.app == \$app) | .projects[] | $1"; }
# Package names are the Nx project names CI pushes as ghcr.io/f0rge/<project>.
PACKAGES=($(deployables .name))
((${#PACKAGES[@]})) || { echo "No Project with scope:$APP has a deploy block." >&2; exit 1; }

cmd()  { printf '      %s%s%s\n' "$BOLD" "$1" "$RESET"; }
done_() { printf '  %s✓%s %s\n' "$GREEN" "$RESET" "$1"; }

# ── Stages every App needs ────────────────────────────────────────────────

stage_environment() {
  stage "GitHub environment \"$APP\""
  say "Releases of this App run in a GitHub environment named $APP, limited to main."
  say "It holds this App's Host token, so no other App's Release can use it."
  say "Without the main-only limit, any branch's workflow could read that token. This step is required."
  confirm "Create or update environment $APP in $REPO now?" || { warn "No main-only environment, no Host token. Stopped here."; exit 1; }
  gh api -X PUT "repos/$REPO/environments/$APP" --input - >/dev/null <<'JSON'
{"deployment_branch_policy":{"protected_branches":false,"custom_branch_policies":true}}
JSON
  gh api "repos/$REPO/environments/$APP/deployment-branch-policies" -q '.branch_policies[].name' | grep -x main >/dev/null ||
    gh api -X POST "repos/$REPO/environments/$APP/deployment-branch-policies" -f name=main -f type=branch >/dev/null
  done_ "environment $APP exists and deploys from main only"
  open_url "https://github.com/$REPO/settings/environments"
  step "Check: $APP is listed, and its deployment branches show only main."
  pause
}

# main_only: environment $APP exists, uses custom branch policies, and its only policy is the branch main.
main_only() {
  [[ "$(gh api "repos/$REPO/environments/$APP" -q '.deployment_branch_policy.custom_branch_policies' 2>/dev/null)" == true ]] &&
    [[ "$(gh api "repos/$REPO/environments/$APP/deployment-branch-policies" -q '"\(.total_count) \(.branch_policies | map((.type // "branch") + ":" + .name) | join(","))"' 2>/dev/null)" == "1 branch:main" ]]
}

# set_env_secret NAME WHAT: gh asks for the value itself, hidden. Refuses unless the environment is main-only.
set_env_secret() {
  main_only || {
    warn "Environment $APP is not limited to the branch main alone, so $1 was not stored."
    say "Fix it under Settings → Environments → $APP → Deployment branches, then re-run this wizard."
    exit 1
  }
  say "gh now asks for $2. Paste it and press Enter; nothing is shown."
  if gh secret set "$1" --env "$APP" --repo "$REPO"; then
    WRITTEN_SECRET+=("$1 (environment $APP)")
  else
    SKIPPED+=("GitHub secret $1: gh secret set $1 --env $APP")
    warn "Not set. Set it before the first Release: gh secret set $1 --env $APP"
  fi
}

stage_images() {
  stage "Pick the commit, make its images public"
  say "On main, CI pushes one image per Project, tagged with the commit."
  say "A new package starts private, and the Host pulls without a login."
  note "Recent CI runs on main (red until every App is switched, so the run's colour says nothing here):"
  gh run list --repo "$REPO" --workflow ci.yml --branch main --limit 10 \
    --json headSha,displayTitle -q '.[] | "      \(.headSha)  \(.displayTitle)"' || true
  step "Pick a commit whose job \"image-push ($APP)\" succeeded; open the run to check."
  note "CI builds an App's images only for commits that affect it. The Release refuses a commit without them."
  ask COMMIT "Full commit sha to release:"
  [[ "$COMMIT" =~ ^[0-9a-f]{40}$ ]] || { warn "That is not a full 40-character sha. Start again."; exit 1; }
  local package
  for package in "${PACKAGES[@]}"; do
    open_url "https://github.com/orgs/$OWNER/packages/container/$package/settings"
    step "$package: Danger Zone → Change visibility → Public."
  done
  note "A 404 there means CI has not pushed that image yet."
  say "Once public, this is the check the Release makes first; each must print a manifest, not an error:"
  for package in "${PACKAGES[@]}"; do cmd "docker manifest inspect $REGISTRY/$package:$COMMIT"; done
  pause "Every package public?"
}

stage_release() {
  stage "First Release"
  say "This starts the same job every merge to main starts from now on:"
  cmd "gh workflow run cd.yml -f app=$APP -f commit=$COMMIT"
  confirm "Release $APP at ${COMMIT:0:12} now?" || { warn "Stopped before the Release. Re-run this wizard when ready."; exit 1; }
  gh workflow run cd.yml --repo "$REPO" -f app="$APP" -f commit="$COMMIT"
  sleep 8
  local run
  run=$(gh run list --repo "$REPO" --workflow cd.yml --event workflow_dispatch --limit 1 --json databaseId -q '.[0].databaseId')
  if ! gh run watch "$run" --repo "$REPO" --exit-status; then
    warn "The Release failed. A service that ran an image before is back on it; one that did not was left alone."
    say "Check each service and put the rest back by hand:"
    release_failed
    exit 1
  fi
  done_ "$APP is released at $COMMIT"
  pause
}

stage_rollback() {
  stage "Check it, and how to roll back"
  step "Open $APP and use it for a minute."
  say "To roll back or redeploy, release an older commit the same way:"
  cmd "gh workflow run cd.yml -f app=$APP -f commit=<older full sha>"
  note "A failed Release puts each service back on the image it ran before, by itself, and fails the run."
  pause "Works?"
}

# delete_old KIND NAME...: KIND is secret or variable. Asks first; deleting cannot be undone.
delete_old() {
  local kind="$1" name
  shift
  (($#)) || return 0
  if confirm "Delete the old GitHub ${kind}s $* now? This cannot be undone."; then
    for name in "$@"; do
      gh "$kind" delete "$name" --repo "$REPO" && done_ "deleted $kind $name" || warn "could not delete $kind $name"
    done
  else
    SKIPPED+=("delete old GitHub ${kind}s: $*")
  fi
}

# ── Railway ───────────────────────────────────────────────────────────────
# Needs: APP, TITLE, RAILWAY_PROJECT. Service names come from the deploy blocks.
# Optional: FROM_REPO=1 (services build from the repository today), DEADLINE,
# OLD_SECRETS, OLD_VARIABLES, functions switch_notes and retire.

switch_railway() {
  SERVICES=($(deployables '.services[].name'))
  TOTAL_STAGES=$((6 + ${FROM_REPO:-0}))
  release_failed() {
    step "Railway keeps the previous deployment serving when a new one fails; check each service is still up."
    step "To go back fully: service → Deployments → the last good one → Redeploy, and reconnect its source under Settings."
  }
  banner "$TITLE"

  stage_environment

  stage_images

  if [[ "${FROM_REPO:-0}" == 1 ]]; then
    stage "Railway: what the first Release changes"
    [[ -n "${DEADLINE:-}" ]] && warn "Run this before $DEADLINE: Railway stops reading railway.toml that day."
    say "Today these services build from the repository: ${SERVICES[*]}"
    say "The first Release points each one at its image, switches off repository deploys for it,"
    say "and sets its start command, pre-deploy command and health check path from the Project's deploy block."
    step "For each service, note Settings → Source (repository and branch) in case you want to go back by hand."
    step "Read each Project's deploy block (project.json → metadata.deploy) and agree with what it will set."
    type switch_notes >/dev/null 2>&1 && switch_notes
    pause "Noted?"
  fi

  # Last, so no merge to main can start a Release before the services are ready for it.
  stage "Railway: project token"
  say "A project token can act on one project and one environment, nothing else."
  open_url "https://railway.com/dashboard"
  step "Open project \"$RAILWAY_PROJECT\" → Settings → Tokens."
  step "Create a token named github-$APP for the production environment. Copy it."
  set_env_secret RAILWAY_TOKEN "the token"

  stage_release
  stage_rollback

  stage "Retire the old setup"
  [[ "${FROM_REPO:-0}" == 1 ]] &&
    step "Railway: each service's Settings → Source now shows its image and no connected repository. Nothing to delete there."
  type retire >/dev/null 2>&1 && retire
  delete_old secret ${OLD_SECRETS[@]+"${OLD_SECRETS[@]}"}
  delete_old variable ${OLD_VARIABLES[@]+"${OLD_VARIABLES[@]}"}
  pause
  finish
}

# ── Pi (Coolify) ──────────────────────────────────────────────────────────
# Needs: APP, TITLE, SERVICES, each "<nx project>|<old application name>|<old uuid>|<ports exposes>|<port mappings>".
# The new application's name is the Nx project name; that is how a Release finds it.
# Optional: DATA_VOLUME + BACKUP_DIR (stateful App), OLD_SECRETS, OLD_VARIABLES,
# function service_notes <nx project>.

switch_pi() {
  local service name old uuid exposes mappings
  # On the Pi each Project is one application named like the Project; SERVICES must list exactly those.
  [[ "$(printf '%s\n' "${PACKAGES[@]}" | sort)" == "$(for service in "${SERVICES[@]}"; do echo "${service%%|*}"; done | sort)" ]] ||
    { echo "SERVICES does not match the deploy blocks of App $APP: ${PACKAGES[*]}" >&2; exit 1; }
  TOTAL_STAGES=$((7 + ${#SERVICES[@]}))
  [[ -n "${DATA_VOLUME:-}" ]] && TOTAL_STAGES=$((TOTAL_STAGES + 1))
  release_failed() {
    step "Coolify: stop the new applications and move any Domains back to the old ones."
    step "Deploy the old applications. They build from the repository as before."
  }
  banner "$TITLE"

  if [[ -n "${DATA_VOLUME:-}" ]]; then
    stage "Back up the data first"
    say "Nothing else happens until this App's data is copied somewhere safe."
    step "On the Pi, in your own SSH session, run:"
    cmd "mkdir -p \"\$HOME/$BACKUP_DIR\" && docker run --rm -v $DATA_VOLUME:/data:ro -v \"\$HOME/$BACKUP_DIR\":/backup alpine tar czf /backup/$APP-before-switch-\$(date +%Y%m%d-%H%M).tar.gz -C /data ."
    step "Check the file exists and is not empty:"
    cmd "ls -lh \"\$HOME/$BACKUP_DIR\" | tail -1"
    type backup_notes >/dev/null 2>&1 && backup_notes
    confirm "Backup written and checked?" || { warn "No backup, no switch."; exit 1; }
  fi

  stage_environment

  stage_images

  for service in "${SERVICES[@]}"; do
    IFS='|' read -r name old uuid exposes mappings <<<"$service"
    stage "Coolify: create $name"
    say "The new application runs the image CI built. The old one ($old, $uuid) keeps running for now."
    step "Open the old application in a second tab; you copy its settings from there."
    step "In the same project and environment, add a new resource → Docker Image."
    step "Image Name: $REGISTRY/$name   Tag: $COMMIT   then Save."
    step "General → Name: $name   (exactly this; a Release finds the application by name)"
    step "General → Ports Exposes: $exposes   Port Mappings: $mappings   (as on the old application)"
    step "General → Custom Docker Options and Network Aliases: copy the old application's, if it has any."
    step "Environment Variables: copy the old application's (Developer view shows them all at once)."
    note "Build-time variables such as NEXT_PUBLIC_* are baked into the image by CI; they do nothing here."
    step "Leave Domains empty; they move over when the old application stops."
    step "Healthcheck: leave Coolify's own health check OFF. The image carries a Docker HEALTHCHECK;"
    say "  Coolify reports its result and a Release waits on it. Coolify's check would replace it."
    type service_notes >/dev/null 2>&1 && service_notes "$name"
    warn "Do not press Deploy. The old application still holds the host port."
    pause "Created $name?"
  done

  stage "Stop the old applications"
  warn "$APP is down from here until the first Release finishes, usually a few minutes."
  for service in "${SERVICES[@]}"; do
    IFS='|' read -r name old uuid exposes mappings <<<"$service"
    step "Old $old ($uuid): Stop. If it has Domains, cut them and Save, then paste them into $name → General → Domains and Save."
  done
  note "Two applications cannot hold the same host port or the same domain, so the old ones go first."
  confirm "Old applications stopped, domains moved?" || { warn "Stopped here. Nothing was released."; exit 1; }

  # Last, so no merge to main can start a Release before the new applications are ready for it.
  stage "Coolify: API token and address"
  step "Open your Coolify dashboard → Keys & Tokens → API Tokens → New Token."
  step "Description github-$APP; tick read, write and deploy. Leave root and read:sensitive unticked."
  step "Create it and copy the token (shown once)."
  warn "Coolify cannot limit a token to one application: with write it can change every application in the team."
  note "The GitHub environment only keeps other Apps' Releases from reading it."
  note "The token Coolify already has for GitHub can read and deploy only; setting an image tag needs write."
  set_env_secret COOLIFY_TOKEN "the token"
  say "Coolify's address is a secret too, so it stays out of this public repository and its logs."
  set_env_secret COOLIFY_URL "Coolify's base URL as GitHub's runners reach it (https://…, no path)"
  pause

  stage_release
  stage_rollback

  stage "Retire the old setup"
  say "The stopped old applications are your way back. Delete them once the new ones have run well for a few days:"
  for service in "${SERVICES[@]}"; do
    IFS='|' read -r name old uuid exposes mappings <<<"$service"
    step "Coolify → old $old ($uuid) → Danger Zone → Delete."
  done
  [[ -n "${DATA_VOLUME:-}" ]] &&
    warn "When deleting, untick \"Permanently delete all volumes associated with this resource.\" The new application uses that data."
  type retire >/dev/null 2>&1 && retire
  delete_old secret ${OLD_SECRETS[@]+"${OLD_SECRETS[@]}"}
  delete_old variable ${OLD_VARIABLES[@]+"${OLD_VARIABLES[@]}"}
  pause
  finish
}
