"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "@/lib/auth";
import {
  queryWorkspace,
  type WorkspaceQuery,
  type WorkspaceSelection,
} from "@/lib/record-workspace-api";
import {
  readWorkspaceQuery,
  selectionContext,
  workspaceIdentity,
  workspaceSearch,
  workspaceStateForKey,
} from "@/lib/record-workspace";
import { withSkuPanelParams } from "@/lib/sku-panel";
import type { RecordWorkspaceAdapter } from "./types";

interface SelectionState {
  context: string;
  ids: Set<string>;
  revisions: Record<string, string>;
  token?: string;
  count: number;
  excluded: Set<string>;
}
function emptySelection(context: string): SelectionState {
  return {
    context,
    ids: new Set(),
    revisions: {},
    count: 0,
    excluded: new Set(),
  };
}
export function useWorkspace<T extends { id: string }>(
  adapter: RecordWorkspaceAdapter<T>,
  refreshKey: number,
) {
  const { user } = useAuth();
  const params = useSearchParams();
  const pathname = usePathname();
  const router = useRouter();
  const client = useQueryClient();
  const query = useMemo(
    () => readWorkspaceQuery(params, adapter.defaultSort),
    [params, adapter.defaultSort],
  );
  const identity = workspaceIdentity(user);
  const context = selectionContext(query, identity, adapter.resource);
  const [selectionState, setSelection] = useState<SelectionState>(() =>
    emptySelection(context),
  );
  const selection =
    selectionState.context === context
      ? selectionState
      : emptySelection(context);
  if (selectionState.context !== context) setSelection(selection);
  const [selectionNotice, setSelectionNotice] = useState<{
    context: string;
    message: string;
  } | null>(null);
  if (selectionNotice && selectionNotice.context !== context)
    setSelectionNotice(null);
  const [searchState, setSearchState] = useState({
    key: query.q,
    value: query.q,
  });
  const currentSearch = workspaceStateForKey(searchState, {
    key: query.q,
    value: query.q,
  });
  if (searchState.key !== query.q) setSearchState(currentSearch);
  const search = currentSearch.value;
  const update = useCallback(
    (patch: Partial<WorkspaceQuery>, keepPage = false) => {
      const next = {
        ...query,
        ...patch,
        offset: keepPage ? (patch.offset ?? query.offset) : 0,
      };
      // The shell SKU panel (?sku, &skuView) stays open while the list changes underneath it.
      router.replace(`${pathname}?${withSkuPanelParams(workspaceSearch(next), params)}`, { scroll: false });
    },
    [query, pathname, router, params],
  );
  useEffect(() => {
    if (search.trim() === query.q) return;
    const timer = window.setTimeout(() => update({ q: search.trim() }), 300);
    return () => window.clearTimeout(timer);
  }, [query.q, search, update]);
  const result = useQuery({
    queryKey: [
      "record-workspace",
      identity,
      adapter.resource,
      query,
      refreshKey,
    ],
    queryFn: ({ signal }) => queryWorkspace<T>(adapter.resource, query, signal),
    enabled: !!user,
    retry: false,
  });
  useEffect(() => {
    if (!result.data || query.offset < result.data.total || query.offset === 0)
      return;
    update(
      {
        offset:
          Math.max(0, Math.ceil(result.data.total / query.limit) - 1) *
          query.limit,
      },
      true,
    );
  }, [result.data, query.offset, query.limit, update]);
  const items = result.data?.items ?? [];
  const recordId = params.get("record");
  const requestedRecord = items.find((item) => item.id === recordId);
  const active = requestedRecord ?? items[0];
  const focus = (id?: string) =>
    router.replace(`${pathname}?${withSkuPanelParams(workspaceSearch(query, id), params)}`, {
      scroll: false,
    });
  const isChecked = (id: string) =>
    selection.token
      ? selection.ids.has(id) && !selection.excluded.has(id)
      : selection.ids.has(id);
  const canSelect = (id: string) => !selection.token || selection.ids.has(id);
  const selectedCount = selection.token
    ? selection.count - selection.excluded.size
    : selection.ids.size;
  const clearSelection = () => {
    setSelection(emptySelection(context));
    setSelectionNotice(null);
  };
  const toggle = (id: string, checked: boolean) => {
    const next = {
      ...selection,
      ids: new Set(selection.ids),
      excluded: new Set(selection.excluded),
      revisions: { ...selection.revisions },
    };
    if (next.token) {
      if (!next.ids.has(id)) return;
      if (checked) next.excluded.delete(id);
      else next.excluded.add(id);
    } else if (checked) {
      if (next.ids.size >= 500 && !next.ids.has(id)) {
        setSelectionNotice({
          context,
          message:
            "A batch can contain at most 500 records. Refine your selection.",
        });
        return;
      }
      next.ids.add(id);
      next.revisions[id] = result.data?.revisions[id] ?? "";
    } else {
      next.ids.delete(id);
      delete next.revisions[id];
    }
    setSelection(next);
  };
  const togglePage = (checked: boolean, ids = items.map((item) => item.id)) => {
    const next = {
      ...selection,
      ids: new Set(selection.ids),
      excluded: new Set(selection.excluded),
      revisions: { ...selection.revisions },
    };
    for (const id of ids) {
      if (next.token) {
        if (!next.ids.has(id)) continue;
        if (checked) next.excluded.delete(id);
        else next.excluded.add(id);
      } else if (checked) {
        if (next.ids.size >= 500 && !next.ids.has(id)) {
          setSelectionNotice({
            context,
            message:
              "Only the first 500 records were selected. A batch can contain at most 500 records.",
          });
          continue;
        }
        next.ids.add(id);
        next.revisions[id] = result.data?.revisions[id] ?? "";
      } else {
        next.ids.delete(id);
        delete next.revisions[id];
      }
    }
    setSelection(next);
  };
  const selectAll = () => {
    if (result.data?.selection_token)
      setSelection({
        ...emptySelection(context),
        token: result.data.selection_token,
        count: result.data.selection_count,
        ids: new Set(result.data.selection_ids),
      });
  };
  const selected: WorkspaceSelection = selection.token
    ? {
        selection_token: selection.token,
        excluded_ids: [...selection.excluded],
      }
    : { ids: [...selection.ids], revisions: selection.revisions };
  const reload = () => {
    clearSelection();
    void client.invalidateQueries({
      queryKey: ["record-workspace", identity, adapter.resource],
    });
    // Resource names match the reference keys in lib/queries ("skus", "customers", ...),
    // so editors stop showing an archived or edited record.
    void client.invalidateQueries({ queryKey: [adapter.resource] });
  };
  return {
    query,
    update: (patch: Partial<WorkspaceQuery>, keepPage = false) => {
      // Reset also cancels a typed search before its debounce reaches the URL.
      if (patch.q === "") setSearchState({ key: query.q, value: "" });
      update(patch, keepPage);
    },
    search,
    setSearch: (value: string) => setSearchState({ key: query.q, value }),
    result,
    items,
    active,
    requestedRecord,
    focus,
    selected,
    selectedCount,
    selectedIds: [...selection.ids].filter((id) => !selection.excluded.has(id)),
    isChecked,
    canSelect,
    toggle,
    togglePage,
    selectAll,
    clearSelection,
    reload,
    identity,
    selectionNotice:
      selectionNotice?.context === context ? selectionNotice.message : null,
  };
}
