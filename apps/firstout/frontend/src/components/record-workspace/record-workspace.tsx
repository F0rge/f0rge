"use client";

import {
  Add,
  Archive,
  ArrowDown,
  ArrowUp,
  Catalog,
  ChevronRight,
  Close,
  DocumentExport,
  Edit,
} from "@carbon/icons-react";
import {
  Button,
  Checkbox,
  InlineNotification,
  Pagination,
  Tag,
} from "@carbon/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Suspense, useState } from "react";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import {
  WORKSPACE_PAGE_SIZES,
  workspaceIdentity,
} from "@/lib/record-workspace";
import type { WorkspaceActionDefinition, RecordWorkspaceProps } from "./types";
import { useWorkspace } from "./use-workspace";
import { WorkspaceFilters } from "./workspace-filters";
import {
  WorkspaceBulkDialog,
  type WorkspaceOperation,
} from "./workspace-bulk-dialog";
import styles from "./record-workspace.module.css";

export function RecordWorkspace<T extends { id: string }>(
  props: RecordWorkspaceProps<T>,
) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { retry: false, refetchOnWindowFocus: false },
          mutations: { retry: false },
        },
      }),
  );
  const { user, loading } = useAuth();
  if (loading) return <p role="status">Loading your workspace…</p>;
  if (!user)
    return (
      <InlineNotification
        kind="error"
        title="Sign in required"
        subtitle="Sign in to view this workspace."
        hideCloseButton
      />
    );
  return (
    <QueryClientProvider client={client}>
      <Suspense fallback={<p role="status">Loading workspace…</p>}>
        <WorkspaceContent
          key={`${workspaceIdentity(user)}:${props.adapter.resource}`}
          {...props}
        />
      </Suspense>
    </QueryClientProvider>
  );
}
function WorkspaceContent<T extends { id: string }>({
  adapter,
  refreshKey = 0,
  onCreate,
  createLabel,
  onEdit,
  renderDetails,
  headerActions,
  onExport,
  children,
}: RecordWorkspaceProps<T>) {
  const workspace = useWorkspace(adapter, refreshKey);
  const { query, result, items, active } = workspace;
  const [operation, setOperation] = useState<WorkspaceOperation | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const archived = query.lifecycle === "archived";
  const bulkAvailable = result.data?.bulk_available === true;
  const actions = (adapter.actions ?? []).filter((action) =>
    archived
      ? !["edit", "archive", "disable", "pause"].includes(action.key)
      : !["restore", "enable", "resume"].includes(action.key),
  );
  const canBulkEdit =
    actions.some((action) => action.key === "edit") &&
    !!adapter.bulkFields?.length;
  const selectable = actions.length > 0;
  const allPageChecked =
    items.length > 0 && items.every((item) => workspace.isChecked(item.id));
  const somePageChecked = items.some((item) => workspace.isChecked(item.id));
  const start = (action: WorkspaceActionDefinition, single = false) => {
    if (!bulkAvailable) {
      setNotice("Bulk actions unavailable. Contact your administrator.");
      return;
    }
    setOperation({
      action: action.key,
      label: action.label,
      count: single ? 1 : workspace.selectedCount,
      selection:
        single && active
          ? {
              ids: [active.id],
              revisions: {
                [active.id]: result.data?.revisions[active.id] ?? "",
              },
            }
          : workspace.selected,
    });
  };
  const error = result.error;
  return (
    <div className={styles.page}>
      <nav aria-label="Breadcrumb" className={styles.breadcrumb}>
        <span>{adapter.breadcrumb}</span>
        <ChevronRight size={14} aria-hidden="true" />
        <span aria-current="page">{adapter.title}</span>
      </nav>
      <header className={styles.header}>
        <div>
          <h1>{adapter.title}</h1>
          <p>{adapter.description}</p>
        </div>
        <div className={styles.actions}>
          {headerActions}
          {onExport && (
            <Button
              kind="ghost"
              renderIcon={DocumentExport}
              disabled={exporting || result.isPending}
              onClick={() => {
                setExporting(true);
                Promise.resolve(onExport(query))
                  .catch((err: unknown) =>
                    setNotice(
                      err instanceof Error ? err.message : "Export failed.",
                    ),
                  )
                  .finally(() => setExporting(false));
              }}
            >
              {exporting ? "Exporting…" : "Export CSV"}
            </Button>
          )}
          {onCreate && !archived && (
            <Button renderIcon={Add} onClick={onCreate}>
              {createLabel ?? `New ${adapter.singular}`}
            </Button>
          )}
        </div>
      </header>
      {notice && (
        <InlineNotification
          kind="info"
          title="Workspace updated"
          subtitle={notice}
          onCloseButtonClick={() => setNotice(null)}
          lowContrast
        />
      )}
      <WorkspaceFilters
        resource={adapter.resource}
        fields={adapter.filters}
        query={query}
        search={workspace.search}
        onSearch={workspace.setSearch}
        update={workspace.update}
      />
      {error && (
        <InlineNotification
          kind="error"
          title={
            error instanceof ApiError && error.status === 403
              ? "Access denied"
              : "Could not load records"
          }
          subtitle={error.message}
          hideCloseButton
          lowContrast
        />
      )}
      {workspace.selectionNotice && (
        <InlineNotification
          kind="info"
          title="Selection limit"
          subtitle={workspace.selectionNotice}
          hideCloseButton
          lowContrast
        />
      )}
      {result.data && !bulkAvailable && actions.length > 0 && (
        <p className={styles.configurationNotice}>
          Bulk actions unavailable. Contact your administrator.
        </p>
      )}
      <div className={styles.layout}>
        <section
          className={styles.list}
          aria-label={`${adapter.title} list`}
          aria-busy={result.isFetching}
        >
          <div className={styles.listHeading}>
            <div>
              <h2>
                {archived
                  ? (adapter.lifecycle?.archivedLabel ?? "Archived")
                  : "All"}{" "}
                {adapter.title.toLowerCase()}
              </h2>
              <p role="status" aria-live="polite">
                {result.isPending
                  ? "Loading records…"
                  : `${result.data?.total ?? 0} ${adapter.title.toLowerCase()}${query.q || query.filters.length ? " match your filters" : ""}`}
              </p>
            </div>
          </div>
          {adapter.lifecycle && (
            <div
              className={styles.lifecycle}
              role="group"
              aria-label="Record status"
            >
              {([false, true] as const).map((inactive) => (
                <button
                  key={String(inactive)}
                  aria-pressed={archived === inactive}
                  onClick={() =>
                    workspace.update({
                      lifecycle: inactive ? "archived" : "active",
                    })
                  }
                >
                  {inactive
                    ? adapter.lifecycle?.archivedLabel
                    : adapter.lifecycle?.activeLabel}
                  <span>
                    {inactive
                      ? (result.data?.counts.archived ?? 0)
                      : (result.data?.counts.active ?? 0)}
                  </span>
                </button>
              ))}
            </div>
          )}
          {workspace.selectedCount > 0 && bulkAvailable && (
            <>
              <div
                className={styles.batch}
                role="region"
                aria-label="Bulk actions"
              >
                <strong>{workspace.selectedCount} selected</strong>
                {canBulkEdit && !archived && (
                  <Button
                    kind="ghost"
                    size="sm"
                    renderIcon={Edit}
                    onClick={() => start({ key: "edit", label: "Edit" })}
                  >
                    Edit
                  </Button>
                )}
                {actions
                  .filter((action) => action.key !== "edit")
                  .map((action) => (
                    <Button
                      key={action.key}
                      kind="ghost"
                      size="sm"
                      onClick={() => start(action)}
                    >
                      {action.label}
                    </Button>
                  ))}
                <Button
                  kind="ghost"
                  size="sm"
                  hasIconOnly
                  renderIcon={Close}
                  iconDescription="Clear selection"
                  onClick={workspace.clearSelection}
                />
              </div>
              <div className={styles.selectionScope}>
                <span>
                  {workspace.selected.selection_token
                    ? "Selection frozen across matching records; newer records are excluded"
                    : "Selected records across pages"}
                </span>
                {!workspace.selected.selection_token &&
                  workspace.selectedCount < (result.data?.total ?? 0) &&
                  (result.data?.selection_token ? (
                    <button onClick={workspace.selectAll}>
                      Select all {result.data.selection_count} matching
                    </button>
                  ) : (
                    <span>
                      Refine your filters to select all; maximum 500 records.
                    </span>
                  ))}
              </div>
            </>
          )}
          <div className={styles.tableScroll}>
            {items.length ? (
              <table className={styles.table}>
                <thead>
                  <tr>
                    {selectable && (
                      <th className={styles.check}>
                        <Checkbox
                          id={`${adapter.resource}-select-page`}
                          labelText="Select records on this page"
                          hideLabel
                          disabled={!bulkAvailable}
                          checked={allPageChecked}
                          indeterminate={somePageChecked && !allPageChecked}
                          onChange={(_, { checked }) =>
                            workspace.togglePage(checked)
                          }
                        />
                      </th>
                    )}
                    {adapter.columns.map((column) => (
                      <th
                        key={column.key}
                        aria-sort={column.sortable
                          ? query.sort.field === column.key
                            ? query.sort.direction === "asc" ? "ascending" : "descending"
                            : "none"
                          : undefined}
                        className={column.numeric ? styles.numeric : undefined}
                      >
                        {column.sortable ? (
                          <button
                            className={styles.sort}
                            onClick={() =>
                              workspace.update({
                                sort: {
                                  field: column.key,
                                  direction:
                                    query.sort.field === column.key &&
                                    query.sort.direction === "asc"
                                      ? "desc"
                                      : "asc",
                                },
                              })
                            }
                          >
                            {column.label}
                            {query.sort.field === column.key ? (
                              query.sort.direction === "asc" ? (
                                <ArrowUp size={12} />
                              ) : (
                                <ArrowDown size={12} />
                              )
                            ) : null}
                          </button>
                        ) : (
                          column.label
                        )}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => (
                    <tr
                      key={item.id}
                      className={
                        active?.id === item.id ? styles.active : undefined
                      }
                    >
                      {selectable && (
                        <td className={styles.check}>
                          <Checkbox
                            id={`${adapter.resource}-select-${item.id}`}
                            labelText={`Select ${adapter.getTitle(item)}`}
                            hideLabel
                            disabled={
                              !bulkAvailable || !workspace.canSelect(item.id)
                            }
                            checked={workspace.isChecked(item.id)}
                            onChange={(_, { checked }) =>
                              workspace.toggle(item.id, checked)
                            }
                          />
                        </td>
                      )}
                      {adapter.columns.map((column, index) => (
                        <td
                          key={column.key}
                          className={
                            column.numeric ? styles.numeric : undefined
                          }
                        >
                          {index === 0 ? (
                            <button
                              className={styles.record}
                              aria-current={
                                active?.id === item.id ? "true" : undefined
                              }
                              onClick={() => workspace.focus(item.id)}
                            >
                              <span
                                className={styles.avatar}
                                aria-hidden="true"
                              >
                                {adapter
                                  .getTitle(item)
                                  .split(" ")
                                  .slice(0, 2)
                                  .map((part) => part[0])
                                  .join("")}
                              </span>
                              <span>
                                <strong>{column.render(item)}</strong>
                                {adapter.getSubtitle && (
                                  <small>{adapter.getSubtitle(item)}</small>
                                )}
                              </span>
                            </button>
                          ) : (
                            column.render(item)
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className={styles.empty}>
                <Catalog size={28} aria-hidden="true" />
                <h3>
                  {result.isPending
                    ? "Loading records…"
                    : error
                      ? "Records unavailable"
                      : `No ${adapter.title.toLowerCase()} found`}
                </h3>
                <p>
                  {error
                    ? "Retry loading this workspace."
                    : "Try changing the search or filters."}
                </p>
                {error ? (
                  <Button kind="tertiary" onClick={() => void result.refetch()}>
                    Retry
                  </Button>
                ) : (
                  !result.isPending && (
                    <Button
                      kind="ghost"
                      onClick={() => workspace.update({ q: "", filters: [] })}
                    >
                      Reset filters
                    </Button>
                  )
                )}
              </div>
            )}
          </div>
          <Pagination
            page={Math.floor(query.offset / query.limit) + 1}
            pageSize={query.limit}
            pageSizes={WORKSPACE_PAGE_SIZES}
            totalItems={result.data?.total ?? 0}
            onChange={({ page, pageSize }) =>
              workspace.update(
                {
                  limit: pageSize,
                  offset: pageSize === query.limit ? (page - 1) * pageSize : 0,
                },
                true,
              )
            }
          />
        </section>
        <aside
          className={styles.inspector}
          aria-label="Selected record details"
        >
          {active ? (
            <>
              <div className={styles.inspectorLabel}>
                {adapter.singular} details
                <Tag size="sm" type="gray">
                  {archived
                    ? (adapter.lifecycle?.archivedLabel ?? "Archived")
                    : "Selected"}
                </Tag>
              </div>
              <div className={styles.identity}>
                <span className={styles.avatar} aria-hidden="true">
                  {adapter
                    .getTitle(active)
                    .split(" ")
                    .slice(0, 2)
                    .map((part) => part[0])
                    .join("")}
                </span>
                <div>
                  <h2>{adapter.getTitle(active)}</h2>
                  {adapter.getSubtitle && <p>{adapter.getSubtitle(active)}</p>}
                </div>
              </div>
              <div className={styles.detailBody}>
                {renderDetails(active, { reload: workspace.reload, archived })}
              </div>
              <div className={styles.inspectorActions}>
                {actions
                  .filter((action) => action.key !== "edit")
                  .map((action) => (
                    <Button
                      key={action.key}
                      kind={action.danger ? "danger--tertiary" : "tertiary"}
                      size="sm"
                      disabled={!bulkAvailable}
                      renderIcon={
                        action.key === "archive" ? Archive : undefined
                      }
                      onClick={() => start(action, true)}
                    >
                      {action.label}
                    </Button>
                  ))}
                {onEdit &&
                  (adapter.canEdit ? adapter.canEdit(active) : !archived) && (
                    <Button
                      size="sm"
                      renderIcon={Edit}
                      onClick={() => onEdit(active)}
                    >
                      Edit {adapter.singular}
                    </Button>
                  )}
              </div>
            </>
          ) : (
            <div className={styles.empty}>
              <h3>Select a record</h3>
              <p>Its details will appear here.</p>
            </div>
          )}
        </aside>
      </div>
      {operation && (
        <WorkspaceBulkDialog
          key={JSON.stringify(operation)}
          resource={adapter.resource}
          operation={operation}
          fields={adapter.bulkFields ?? []}
          onClose={() => setOperation(null)}
          onComplete={(message) => {
            setNotice(message);
            workspace.reload();
          }}
        />
      )}
      {children}
    </div>
  );
}
