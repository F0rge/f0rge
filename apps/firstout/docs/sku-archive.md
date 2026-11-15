# SKU archive

Archive discontinued catalogue entries without deleting their identity, history
or physical stock. Customers and suppliers already use the same Active /
Archived workspace pattern. Leo approved the clickable mockup and requested
reuse of the existing shared components before authorizing this implementation.
The synthetic prototype is retained separately on
[`codex/firstout-sku-archive-prototype`](https://github.com/F0rge/f0rge/tree/codex/firstout-sku-archive-prototype);
its HTML is not part of the application implementation.

## Behaviour

| Situation | Result |
| --- | --- |
| Ordinary SKU | Move between Active and Archived. Keep its UUID, code, barcode, photos, prices and historical links. |
| Stock or open work remains | Show exact stock quantities by location, on-order quantities and open-document warnings before confirmation. Archiving never writes off stock or cancels a document. |
| New business | Archived SKUs are excluded from new sales, purchases, reorders and kit selection. Existing lines cannot be increased or copied into new business. |
| Existing commitments | Existing quantities can be fulfilled, received or cancelled. Source-linked picks remain possible. Stock corrections, transfers, stocktakes and invoice-backed returns remain available. These operations do not restore the SKU. |
| Component of an active kit | Block archive and link to each affected kit. Change the recipe or archive the parent separately first; nothing cascades. |
| Archive a kit | Keep its recipe read-only and leave component archive states unchanged. Existing fulfilment can use the preserved recipe. |
| Restore a kit | Require its components to be active first. Keep each SKU's previous sales setting; restoration does not publish it online. |
| Nested, cyclic or invalid recipe | Block archive-state changes until the recipe is corrected. Nested-kit fulfilment is not introduced by this feature. |
| Published online or active made-to-order offer | Block archive until merchandising withdrawal and offer closure are handled separately. The archive action does not perform a shop sync. |
| Bulk operation | Preview eligible and blocked records. Require explicit acknowledgement before changing eligible records when some are blocked, or when stock/open-work warnings exist. Report each execution outcome. |
| Stale selection or retry | Recheck revisions and dependency fingerprints on execution. Reject stale impact; retain durable per-record outcomes for the same request ID. |
| Later import | Cin7 preserves archive state and archived kit recipes. Catalogue CSV edits require restoring an archived SKU first. |

Archived physical stock remains visible in inventory and bin views. New
stocktakes include archived SKUs with nonzero stock at the selected location;
existing stocktake snapshots remain usable even if their SKU is archived later.
Archiving an incorrectly recorded balance does not correct that balance: use a
stocktake or stock adjustment separately.

## Components and boundaries

The catalogue uses the existing `RecordWorkspace` and its lifecycle controls,
selection, filtering and pagination. `WorkspaceBulkDialog` uses the actual
Carbon modal, acknowledgement checkbox, notifications and dependency links for
both catalogue-list actions and full-SKU archive/restore actions. Catalogue
photos, pricing, labels, CSV export, supplier filters and the existing SKU editor
remain available within their appropriate lifecycle and permission boundaries.

`SkuArchiveService` owns kit eligibility, impact snapshots and lifecycle writes.
The shared workspace endpoints require `catalogue.mutate`, apply tenant scope,
mask costs using existing permissions and retain replay-safe batch outcomes.
Catalogue and new-business mutations share a tenant/SKU lock order so a recipe
cannot gain an archived component between validation and commit.

## Acceptance and verification

- Archive and restore through both catalogue entry points; verify unchanged
  stock, identity, history, prices and prior sellability.
- Exercise component blocking, independent parent archive, component-first
  restoration and invalid-recipe denial.
- Show fractional stock and open work in confirmation; complete existing work
  and reject new, increased or copied business lines.
- Verify tenant/permission denial, cost masking, stale impact and replay outcomes.
- Keep archived stock countable/correctable; preserve archive state through
  imports, receipts and returns.
- Walk the real Carbon UI against a local API, including a blocker/error path.
  Test results and browser evidence belong in the PR's checks section; this
  brief does not substitute for those results.

## Migration and limits

Migration `091_sku_archive` adds a default-false archive flag, nullable archive
metadata, an actor foreign key and a tenant/lifecycle index. It does not rewrite
stock, recipes or documents. Its exact checksum is classified as a compatible
revision in the release migration policy and must pass PostgreSQL upgrade and
compatibility checks. Firstout's controlled CD migration step runs before the
new backend is promoted. Automatic application recovery retains the expanded
schema and customer writes; it never performs a database downgrade. An application
rollback to a pre-archive image preserves these columns but loses archive
enforcement: that image can show archived SKUs and accept new business for them.
Schema compatibility is not a claim of lifecycle behaviour compatibility.
Restore an archive-aware image before relying on archive restrictions again.

The archive feature does not withdraw Medusa merchandising or change checkout
integration. Published flags and active offers therefore block archive. Stock
valuation and historical documents continue to include archived SKUs. The
existing whole-component restriction on fractional kit fulfilment remains.

An existing pre-archive till pick requires a restricted resume path: archived
SKUs must remain absent from ordinary new-sale selectors while that exact
commitment can be completed. This path is part of acceptance, not permission to
sell an archived SKU freely.
