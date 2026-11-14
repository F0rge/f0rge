# Pull request descriptions

Use this process when creating, updating or reviewing a PR into `main`. Start
from [the PR template](../../.github/PULL_REQUEST_TEMPLATE.md). Keep explanations
short, concrete and understandable without the originating chat. Rewrite the
description when the final scope changes.

## Required order

1. **What changed:** describe the resulting behavior and affected scope. Give a
   before/after example when useful.
2. **Why it changed:** state the problem and why the chosen approach solves it.
3. **Solution design:** include a small Mermaid diagram of the actual solution,
   showing the relevant flow, components or dependencies. For process or
   documentation work, diagram the changed review or instruction flow. Keep
   proposed future components clearly labelled as proposed.
4. **ADR assessment:** include the complete table defined below. A brief summary
   of important gaps may precede it.
5. **Checks and limitations:** give the checks actually run, their results,
   independent review evidence and material untested behavior. Link CI runs,
   source, walkthroughs and approval records where available. Distinguish local
   fixtures, static checks and runtime evidence.

## ADR assessment

Include each current ID from [the ADR index](../adr/README.md) exactly once:
currently P-001–P-064 and C-001–C-002. Link each ID and short title to its record.
Short titles are navigation labels; the linked decision remains authoritative.

| ADR | Reviewed | Complies? | Existing gap? | Reason / comment |
| --- | --- | --- | --- | --- |

Use these values consistently:

- **Reviewed:** `Yes` only after considering the decision against the final PR
  scope and available evidence; otherwise `No`. Reading the decision is not
  proof of compliance.
- **Complies?:** `No`, `Partial`, `Not assessed`, `Approved exception`,
  `Yes for PR`, or `Outside PR scope`. Assess the behavior and safeguards touched
  by the PR, including existing patterns continued or expanded by the change.
  Use `No` for a known unmet requirement, `Partial` for an incompletely met
  requirement, and `Not assessed` when evidence is insufficient to judge.
  `Yes for PR` needs specific evidence and covers only the stated PR scope.
- **Existing gap?:** `Yes`, `No`, or `Not assessed`. Record known pre-existing
  gaps in the affected app or platform, including those outside the diff. Use
  `No` only when the relevant baseline was checked; a small PR does not require
  a fresh audit of every app or certify the whole repository.
- **Reason / comment:** explain the result, cite evidence for compliance and
  distinguish new, continued and unchanged gaps. For an outside-scope row, state
  why it is outside scope and retain any known baseline gap. For a conditional
  decision, state that it remains conditional and whether the PR exercises it;
  an unadopted conditional selection alone is not a compliance failure.

Sort rows by **Complies?** in this order: `No`, `Partial`, `Not assessed`,
`Approved exception`, `Yes for PR`, `Outside PR scope`. Within each group, put
existing `Yes` gaps first, then `Not assessed`, then `No`; break remaining ties
by canonical index order (P-001–P-064, then C-001–C-002). This puts unmet requirements and uncertainties before compliant or
unaffected decisions. Keep all rows in the PR description, even if the complete
table is placed inside a labelled expandable section.

`Approved exception` requires a link to Leo's explicit approval and its scope,
with any expiry or conditions and why they apply to this change. Legacy code,
passing CI, an agent review or a merge is not exception approval. Without the
approval evidence, report the actual gap or uncertainty. Maintaining a legacy
app does not migrate it or automatically waive its migration gaps; the gradual
migration policy remains P-002.

Compliance claims need evidence of the relevant behavior, not merely a record
that the ADR was considered. If enforcement is missing or only proposed, state
that in the reason; a manually completed table does not install a CI gate.
Keep platform enforcement gaps distinct from whether this PR follows a rule.

## Before requesting review

Check that all five sections reflect the final diff; the diagram matches the
solution; every ADR appears with its short title, status, baseline and reason;
the rows follow the sort order; and approval claims have real references.
Report missing checks, reviews or evidence explicitly. P-006 still requires
Leo's separate production-release approval; a completed description grants
neither merge nor deployment permission.
