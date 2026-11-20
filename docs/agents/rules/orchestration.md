> Canonical decisions: [`docs/adr/README.md`](../../adr/README.md). Follow [P-005](../../adr/governance.md#p-005) for review/automatic squash merging and [P-006](../../adr/governance.md#p-006) for release authorization. Legacy commands below remain inventory, not approved exceptions or release permission.

# Orchestration — Plan, Delegate, Verify

Read the [agent guide](../README.md) and [shared protocol](../protocol.md). Repository roles use the `f0rge-` names in the [manifest](../manifest.json); no user-global profile, memory file or particular model is a prerequisite.

## Planning and routing

The coordinator resolves each proposed file with `node scripts/agents/agents.mjs route <repo-relative-path...>`. The manifest is the single routing source, not a native agent configuration format. Resolve specific paths rather than assigning a whole app to one role. Stop to classify unknown paths; do not invent a fallback owner.

Before implementation, the coordinator's plan names `Chunk | Primary | Independent reviewers | Deliverable | Dependencies`. Assign specialists only as the work requires, and parallelize independent slices with explicit file ownership. A trivial single-file correction can be handled inline; substantial work still needs independent review.

A specialist implements its assigned slice. It reports cross-domain dependencies and review needs to the coordinator instead of recursively spawning agents for each step. Reviewers assess evidence independently of the implementer. A role name grants neither policy authority nor production permission.

The plan records unresolved decisions and testable acceptance criteria. UI/API behavior changes require a live-server walkthrough of the affected journey and an error path, with safe local fixtures or sandboxes. Existing commands and useful tests remain valid for their legacy apps; the conditional ADR choices remain conditional.

## Dispatch and handoff

Use the [shared protocol](../protocol.md) for the brief and result contract. Include the approved objective, owned paths, resolved primary/reviewers, relevant ADR and app-context pointers, dependencies, allowed effects, acceptance criteria and available tool capabilities. Preserve explicit release holds.

Select an available runtime/model through the host's supported configuration. If the required agent or tool is unavailable, report the limitation and agree a supported allocation; do not claim a profile provides capabilities or permission controls the host does not enforce.

## PR and release boundary

Use a short-lived branch and a pull request into `main`. Run applicable checks, include the ADR Check for the touched domains (P-003), and obtain independent review. Follow P-005 for Leo's personal review and default native squash auto-merge, and P-006 for release authorization. A task withholding merge authorization keeps its PR unarmed. CI, agent findings and provider configuration do not authorize manual production operations. Use the repository protocol for shipping work.
