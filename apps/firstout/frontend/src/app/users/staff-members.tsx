"use client";

import { ArrowDown, ArrowRight, ArrowUp } from "@carbon/icons-react";
import {
  Button, Checkbox, InlineNotification, Pagination, Table, TableBody, TableCell,
  TableHead, TableHeader, TableRow, DataTableSkeleton, Tag,
} from "@carbon/react";
import { useRef, useState } from "react";
import { useWorkspace } from "@/components/record-workspace/use-workspace";
import type { RecordWorkspaceAdapter } from "@/components/record-workspace";
import { WorkspaceFilters } from "@/components/record-workspace/workspace-filters";
import { WorkspaceBulkDialog, type WorkspaceOperation } from "@/components/record-workspace/workspace-bulk-dialog";
import { type AuthUser, type Location, type Role, type User } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { WORKSPACE_PAGE_SIZES } from "@/lib/record-workspace";
import { adminError, isOwnerRole } from "@/lib/staff-administration";
import { type StaffMember, StaffMemberDialog } from "./staff-member-dialog";
import styles from "./users.module.css";

export function StaffMembers({
  user, roles, locations, optionsReady, optionsError, retryOptions, onChanged,
}: {
  user: AuthUser;
  roles: Role[];
  locations: Location[];
  optionsReady: boolean;
  optionsError: Error | null;
  retryOptions: () => void;
  onChanged: () => void;
}) {
  const [operation, setOperation] = useState<WorkspaceOperation | null>(null);
  const [member, setMember] = useState<StaffMember | null>(null);
  const [dismissedRecord, setDismissedRecord] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const memberButton = useRef<HTMLButtonElement>(null);
  const { refreshUser } = useAuth();
  const roleName = (slug: string) => roles.find((role) => role.slug === slug)?.name ?? slug;
  const locationName = (locationId: string | null) =>
    locationId ? locations.find((location) => location.id === locationId)?.name ?? "Unavailable location" : "No default";
  const adapter: RecordWorkspaceAdapter<StaffMember> = {
    resource: "users",
    title: "Team members",
    singular: "member",
    description: "",
    breadcrumb: "Administration",
    defaultSort: "display_name",
    columns: [],
    filters: [
      { key: "display_name", label: "Display name", type: "text" },
      { key: "email", label: "Email", type: "text" },
      { key: "role", label: "Role", type: "enum", quick: true, options: roles.map((role) => ({ value: role.slug, label: role.name })) },
    ],
    getTitle: (item) => item.display_name || item.email,
  };
  const workspace = useWorkspace(adapter, 0);
  const { items, query, result, selectedCount, update } = workspace;
  const activeMember = member ?? (workspace.requestedRecord?.id === dismissedRecord ? undefined : workspace.requestedRecord);
  const bulkAvailable = result.data?.bulk_available === true;
  const archived = query.lifecycle === "archived";
  const actorIsOwner = isOwnerRole(user.role, roles);
  const mayManage = (item: User) =>
    item.id === user.id || (optionsReady && (actorIsOwner || !isOwnerRole(item.role, roles)));
  const selectable = items.filter((item) => item.id !== user.id && mayManage(item));
  const allChecked = selectable.length > 0 && selectable.every((item) => workspace.isChecked(item.id));
  const someChecked = selectable.some((item) => workspace.isChecked(item.id));

  function changed(message: string) {
    onChanged();
    workspace.reload();
    setNotice(message);
  }

  return (
    <>
      <WorkspaceFilters resource="users" fields={adapter.filters} query={query} search={workspace.search} onSearch={workspace.setSearch} update={update} />
      <div className={styles.controls}>
        <div role="group" aria-label="Member status" className={styles.actions}>
          {([["active", "Active"], ["archived", "Disabled"], ["all", "All"]] as const).map(([value, label]) =>
            <Button key={value} size="sm" kind={query.lifecycle === value ? "tertiary" : "ghost"} aria-pressed={query.lifecycle === value} onClick={() => update({ lifecycle: value })}>
              {label}{result.data && value !== "all" ? " (" + (value === "active" ? result.data.counts.active : result.data.counts.archived) + ")" : ""}
            </Button>,
          )}
        </div>
        {result.data && <p role="status">{result.data.total} {result.data.total === 1 ? "member" : "members"}</p>}
      </div>
      {notice && <InlineNotification lowContrast kind="success" title={notice} onCloseButtonClick={() => setNotice("")} />}
      {result.error && (
        <div className={styles.feedback}>
          <InlineNotification lowContrast kind="error" title="Could not load team members" subtitle={adminError(result.error, "The directory is unavailable.")} hideCloseButton />
          <Button size="sm" kind="tertiary" onClick={() => void result.refetch()}>Retry members</Button>
        </div>
      )}
      {optionsError && (
        <div className={styles.feedback}>
          <InlineNotification lowContrast kind="error" title="Roles or locations unavailable" subtitle={adminError(optionsError, "Could not load directory details.")} hideCloseButton />
          <Button size="sm" kind="tertiary" onClick={retryOptions}>Retry roles and locations</Button>
        </div>
      )}
      {bulkAvailable && selectedCount > 0 && query.lifecycle !== "all" && (
        <div className={styles.batch}>
          <strong>{selectedCount} selected across pages</strong>
          <Button
            size="sm" disabled={result.isFetching} kind={archived ? "primary" : "danger"}
            onClick={() => setOperation({
              action: archived ? "enable" : "disable",
              label: archived ? "Enable access to" : "Disable access to",
              count: selectedCount,
              selection: workspace.selected,
            })}
          >{archived ? "Enable access" : "Disable access"}</Button>
          {!workspace.selected.selection_token && result.data?.selection_token && selectedCount < result.data.selection_count && (
            <Button kind="ghost" size="sm" onClick={workspace.selectAll}>Select all {result.data.selection_count} matching</Button>
          )}
          <Button size="sm" kind="ghost" onClick={workspace.clearSelection}>Clear selection</Button>
        </div>
      )}
      {workspace.selectionNotice && <InlineNotification lowContrast kind="info" title="Selection limit" subtitle={workspace.selectionNotice} hideCloseButton />}
      {result.isPending ? (
        <DataTableSkeleton aria-label="Loading team members" columnCount={4} rowCount={3} showHeader={false} showToolbar={false} />
      ) : items.length > 0 ? (
        <div className={styles.tableScroll} role="region" aria-label="Team members table" tabIndex={0} aria-busy={result.isFetching}>
          <Table size="lg" aria-label="Team members">
            <TableHead>
              <TableRow>
                {bulkAvailable && query.lifecycle !== "all" && (
                  <TableHeader className={styles.checkbox}>
                    <Checkbox id="staff-select-page" labelText="Select members on this page" hideLabel disabled={!selectable.length || result.isFetching}
                      checked={allChecked} indeterminate={!allChecked && someChecked}
                      onChange={(_, { checked }) => workspace.togglePage(checked, selectable.map((item) => item.id))} />
                  </TableHeader>
                )}
                {([["display_name", "Team member"], ["role", "Role"]] as const).map(([field, label]) => (
                  <TableHeader key={field} aria-sort={
                    query.sort.field !== field ? "none" : query.sort.direction === "asc" ? "ascending" : "descending"
                  }>
                    <button
                      type="button"
                      className={styles.sort}
                      onClick={() => update({
                        sort: { field, direction: query.sort.field === field && query.sort.direction === "asc" ? "desc" : "asc" },
                      })}
                    >
                      {label}
                      {query.sort.field === field && (query.sort.direction === "asc" ? <ArrowUp size={12} aria-hidden="true" /> : <ArrowDown size={12} aria-hidden="true" />)}
                    </button>
                  </TableHeader>
                ))}
                <TableHeader>Default location</TableHeader>
                <TableHeader>Status</TableHeader>
              </TableRow>
            </TableHead>
            <TableBody>
              {items.map((item) => (
                <TableRow key={item.id} isSelected={workspace.isChecked(item.id)}>
                  {bulkAvailable && query.lifecycle !== "all" && (
                    <TableCell className={styles.checkbox}>
                      <Checkbox id={"staff-select-" + item.id} labelText={"Select " + adapter.getTitle(item)} hideLabel
                        checked={workspace.isChecked(item.id)} disabled={result.isFetching || !workspace.canSelect(item.id) || !selectable.includes(item)}
                        onChange={(_, { checked }) => workspace.toggle(item.id, checked)} />
                    </TableCell>
                  )}
                  <TableCell>
                    <button type="button" className={styles.memberLink} onClick={(event) => {
                      memberButton.current = event.currentTarget;
                      setMember(item);
                      setDismissedRecord(null);
                      workspace.focus(item.id);
                    }}>
                      {adapter.getTitle(item)}
                      <ArrowRight size={14} aria-hidden="true" />
                    </button>
                    <small className={styles.email}>{item.email}</small>
                  </TableCell>
                  <TableCell>{roleName(item.role)}</TableCell>
                  <TableCell>{locationName(item.default_location_id)}</TableCell>
                  <TableCell><Tag size="sm" type={item.is_disabled ? "gray" : "green"}>{item.is_disabled ? "Disabled" : "Active"}</Tag></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      ) : !result.error && (
        <div className={styles.empty}>
          <p role="status">{query.q || query.filters.length ? "No team members match your filters." : archived ? "No disabled team members." : "No team members to display."}</p>
          {(query.q || query.filters.length > 0) && (
            <Button kind="ghost" size="sm" onClick={() => update({ q: "", filters: [] })}>Reset filters</Button>
          )}
        </div>
      )}
      {!result.isPending && result.data && (
        <Pagination
          page={Math.floor(query.offset / query.limit) + 1}
          pageSize={query.limit}
          pageSizes={WORKSPACE_PAGE_SIZES}
          totalItems={result.data.total}
          onChange={({ page, pageSize }) =>
            update({ limit: pageSize, offset: pageSize === query.limit ? (page - 1) * pageSize : 0 }, true)
          }
        />
      )}
      {activeMember && (
        <StaffMemberDialog
          key={activeMember.id}
          member={activeMember}
          user={user}
          roles={roles.filter((role) => actorIsOwner || !isOwnerRole(role.slug, roles))}
          roleName={roleName}
          locations={locations}
          locationName={locationName}
          editable={mayManage(activeMember) && optionsReady}
          onClose={() => {
            setMember(null);
            setDismissedRecord(activeMember.id);
            workspace.focus();
            requestAnimationFrame(() => memberButton.current?.focus());
          }}
          onChanged={(updated, message) => {
            setMember(updated);
            if (updated.id === user.id) void refreshUser();
            changed(message);
          }}
        />
      )}
      {operation && (
        <WorkspaceBulkDialog
          resource="users" operation={operation} fields={[]}
          onClose={() => setOperation(null)} onComplete={changed}
        />
      )}
    </>
  );
}
