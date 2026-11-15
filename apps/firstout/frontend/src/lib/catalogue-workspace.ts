import { queryWorkspace, type WorkspaceQuery } from "./record-workspace-api";
import type { Sku } from "./api";

/** Preserve lifecycle and advanced filters for catalogue exports and label batches. */
export async function loadCatalogueSelection(
  query: WorkspaceQuery,
  ids?: readonly string[],
): Promise<Sku[]> {
  const selected = ids ? new Set(ids) : null;
  const rows: Sku[] = [];
  for (let offset = 0; ; offset += 100) {
    const page = await queryWorkspace<Sku>("skus", { ...query, limit: 100, offset });
    rows.push(...page.items.filter((item) => !selected || selected.has(item.id)));
    if (offset + page.items.length >= page.total || !page.items.length) break;
  }
  return rows;
}
