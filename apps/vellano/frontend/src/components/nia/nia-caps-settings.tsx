"use client";

import {
  Button,
  DataTable,
  InlineNotification,
  Loading,
  NumberInput,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableHeader,
  TableRow,
  Tile,
} from "@carbon/react";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  ApiError,
  getNiaUsageMe,
  listNiaUsage,
  patchNiaUsageCap,
  updateSettings,
  type NiaUsageMe,
  type NiaUsageUser,
} from "@/lib/api";
import {
  formatNiaTokenCount,
  formatNiaUsageLine,
  niaUsagePercent,
  overrideDraftFromOverride,
  parseOverrideDraft,
  type NiaOverrideDraft,
} from "@/lib/nia-caps-math";

const ADMIN_HEADERS = [
  { key: "user", header: "User" },
  { key: "used", header: "Used" },
  { key: "cap", header: "Cap" },
  { key: "remaining", header: "Remaining" },
  { key: "override", header: "Override cap" },
  { key: "actions", header: "Actions" },
] as const;

function formatPeriodStart(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  return date.toLocaleDateString("en-GB", { month: "long", year: "numeric" });
}

type NiaCapsSettingsProps = {
  canUse: boolean;
  canAdmin: boolean;
  teamDefaultCap: number;
  teamDefaultDisabled?: boolean;
  onTeamDefaultCapChange: (value: number) => void;
  /** Bump after parent "Save settings" so the usage table reloads with the new team default. */
  refreshKey?: number;
  hideChrome?: boolean;
};

export function NiaCapsSettings({
  canUse,
  canAdmin,
  teamDefaultCap,
  teamDefaultDisabled = false,
  onTeamDefaultCapChange,
  refreshKey = 0,
  hideChrome = false,
}: NiaCapsSettingsProps) {
  const [usageMe, setUsageMe] = useState<NiaUsageMe | null>(null);
  const [usageRows, setUsageRows] = useState<NiaUsageUser[]>([]);
  const [overrideDrafts, setOverrideDrafts] = useState<Record<string, NiaOverrideDraft>>({});
  const [teamDraft, setTeamDraft] = useState(teamDefaultCap);
  const [persistedTeamCap, setPersistedTeamCap] = useState(teamDefaultCap);
  const draftDrivenParentSync = useRef(false);
  const [loadingMe, setLoadingMe] = useState(canUse);
  const [loadingAdmin, setLoadingAdmin] = useState(canAdmin);
  const [error, setError] = useState<string | null>(null);
  const [rowNotice, setRowNotice] = useState<string | null>(null);
  const [savingUserId, setSavingUserId] = useState<string | null>(null);
  const [savingTeamDefault, setSavingTeamDefault] = useState(false);

  const loadMyUsage = useCallback(async () => {
    if (!canUse) {
      return;
    }
    const data = await getNiaUsageMe();
    setUsageMe(data);
  }, [canUse]);

  const loadAdminUsage = useCallback(async () => {
    if (!canAdmin) {
      return;
    }
    setLoadingAdmin(true);
    try {
      const rows = await listNiaUsage();
      setUsageRows(rows);
      setOverrideDrafts(
        Object.fromEntries(rows.map((row) => [row.user_id, overrideDraftFromOverride(row.override)])),
      );
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "Failed to load Nia usage");
    } finally {
      setLoadingAdmin(false);
    }
  }, [canAdmin]);

  useEffect(() => {
    setTeamDraft(teamDefaultCap);
    // Typing syncs the parent so "Save settings" keeps the draft; do not treat that as persisted.
    if (draftDrivenParentSync.current) {
      draftDrivenParentSync.current = false;
      return;
    }
    setPersistedTeamCap(teamDefaultCap);
  }, [teamDefaultCap]);

  useEffect(() => {
    if (!canUse) {
      return;
    }
    let cancelled = false;
    setLoadingMe(true);
    getNiaUsageMe()
      .then((data) => {
        if (!cancelled) {
          setUsageMe(data);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Failed to load your Nia usage");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoadingMe(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [canUse]);

  useEffect(() => {
    void loadAdminUsage();
  }, [loadAdminUsage, refreshKey]);

  useEffect(() => {
    if (refreshKey === 0 || !canUse) {
      return;
    }
    void loadMyUsage().catch((err: unknown) => {
      setError(err instanceof ApiError ? err.message : "Failed to load your Nia usage");
    });
  }, [refreshKey, canUse, loadMyUsage]);

  async function handleSaveTeamDefault() {
    setSavingTeamDefault(true);
    setError(null);
    setRowNotice(null);
    try {
      const updated = await updateSettings({ nia_monthly_token_cap: teamDraft });
      onTeamDefaultCapChange(updated.nia_monthly_token_cap);
      setTeamDraft(updated.nia_monthly_token_cap);
      setPersistedTeamCap(updated.nia_monthly_token_cap);
      await loadAdminUsage();
      if (canUse) {
        await loadMyUsage();
      }
      setRowNotice(
        `Saved team default cap (${formatNiaTokenCount(updated.nia_monthly_token_cap)}). Users with Inherit now use this cap.`,
      );
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "Failed to save team default cap");
    } finally {
      setSavingTeamDefault(false);
    }
  }

  async function handleSaveOverride(userId: string) {
    const draft = overrideDrafts[userId];
    if (!draft) {
      return;
    }
    setSavingUserId(userId);
    setError(null);
    setRowNotice(null);
    try {
      const cap = parseOverrideDraft(draft);
      const updated = await patchNiaUsageCap(userId, cap);
      setUsageRows((current) =>
        current.map((row) => (row.user_id === userId ? updated : row)),
      );
      setOverrideDrafts((current) => ({
        ...current,
        [userId]: overrideDraftFromOverride(updated.override),
      }));
      // Summary card ("Your usage") must track the same effective cap as the table.
      if (canUse) {
        await loadMyUsage();
      }
      setRowNotice(`Saved cap for ${updated.email}.`);
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "Failed to save user cap");
    } finally {
      setSavingUserId(null);
    }
  }

  if (!canUse && !canAdmin) {
    return null;
  }

  const usagePercent = usageMe ? niaUsagePercent(usageMe.used, usageMe.cap) : 0;
  const teamDefaultDirty = teamDraft !== persistedTeamCap;

  const adminRows = usageRows.map((row) => ({
    id: row.user_id,
    user: row.display_name ? `${row.display_name} (${row.email})` : row.email,
    used: formatNiaTokenCount(row.used),
    cap: formatNiaTokenCount(row.cap),
    remaining: formatNiaTokenCount(row.remaining),
    override: row.user_id,
    actions: row.user_id,
  }));

  const body = (
      <Stack gap={5}>
        {hideChrome ? (
          <p className="cds--type-body-01 vellano-muted-text">
            Monthly token usage for the in-app assistant. Caps reset each UTC calendar month.
          </p>
        ) : (
          <div>
            <h2 className="cds--type-productive-heading-03">Nia</h2>
            <p className="cds--type-body-01 vellano-muted-text">
              Monthly token usage for the in-app assistant. Caps reset each UTC calendar month.
            </p>
          </div>
        )}

        {error ? (
          <InlineNotification kind="error" title="Nia" subtitle={error} hideCloseButton />
        ) : null}
        {rowNotice ? (
          <InlineNotification kind="success" title="Nia" subtitle={rowNotice} hideCloseButton />
        ) : null}

        {canUse ? (
          <Stack gap={3}>
            <p className="cds--label">Your usage</p>
            {loadingMe ? (
              <Loading withOverlay={false} description="Loading your Nia usage…" />
            ) : usageMe ? (
              <Stack gap={3}>
                <p className="cds--type-body-01">
                  {formatNiaUsageLine(usageMe.used, usageMe.cap, usageMe.remaining)} —{" "}
                  {formatPeriodStart(usageMe.period_start)}
                </p>
                <div
                  className="vellano-nia-usage-meter"
                  role="progressbar"
                  aria-valuemin={0}
                  aria-valuemax={usageMe.cap}
                  aria-valuenow={usageMe.used}
                  aria-label="Nia token usage this month"
                >
                  {usageMe.cap > 0 ? (
                    <div
                      className="vellano-nia-usage-meter__bar"
                      style={{ width: `${usagePercent}%` }}
                    />
                  ) : null}
                </div>
                {usageMe.cap === 0 ? (
                  <p className="cds--type-helper-text-01">
                    Your cap is 0 — Nia is blocked until an admin raises your limit.
                  </p>
                ) : null}
              </Stack>
            ) : null}
          </Stack>
        ) : null}

        {canAdmin ? (
          <Stack gap={5}>
            <Stack gap={3}>
              <NumberInput
                id="nia-team-default-cap"
                label="Team default monthly token cap"
                helperText="Applies when a user has no override. Set to 0 to block Nia for users without an override. Use Save team default below — editing the field alone does not persist."
                value={String(teamDraft)}
                min={0}
                step={1000}
                disabled={teamDefaultDisabled || savingTeamDefault}
                onChange={(_, { value }) => {
                  if (typeof value === "number") {
                    draftDrivenParentSync.current = true;
                    setTeamDraft(value);
                    onTeamDefaultCapChange(value);
                    return;
                  }
                  if (typeof value === "string" && value.trim() !== "") {
                    const parsed = Number(value);
                    if (Number.isFinite(parsed) && parsed >= 0) {
                      const next = Math.trunc(parsed);
                      draftDrivenParentSync.current = true;
                      setTeamDraft(next);
                      onTeamDefaultCapChange(next);
                    }
                  }
                }}
              />
              <Button
                kind="secondary"
                size="md"
                disabled={teamDefaultDisabled || savingTeamDefault || !teamDefaultDirty}
                onClick={() => void handleSaveTeamDefault()}
              >
                {savingTeamDefault ? "Saving…" : "Save team default"}
              </Button>
            </Stack>

            <Stack gap={3}>
              <p className="cds--label">Per-user caps</p>
              <p className="vellano-muted-text">
                Leave override empty to inherit the team default. Set 0 to block Nia for that user.
              </p>
              {loadingAdmin ? (
                <Loading withOverlay={false} description="Loading user usage…" />
              ) : adminRows.length === 0 ? (
                <p className="cds--type-body-01">No users to show.</p>
              ) : (
                <DataTable rows={adminRows} headers={[...ADMIN_HEADERS]}>
                  {({
                    rows,
                    headers,
                    getHeaderProps,
                    getRowProps,
                    getTableProps,
                    getTableContainerProps,
                  }) => (
                    <TableContainer {...getTableContainerProps()}>
                      <Table {...getTableProps()}>
                        <TableHead>
                          <TableRow>
                            {headers.map((header) => {
                              const { key: headerKey, ...headerProps } = getHeaderProps({ header });
                              return (
                                <TableHeader key={headerKey} {...headerProps}>
                                  {header.header}
                                </TableHeader>
                              );
                            })}
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {rows.map((row) => {
                            const userId = row.id;
                            const sourceRow = usageRows.find((entry) => entry.user_id === userId);
                            const draft =
                              overrideDrafts[userId] ??
                              (sourceRow
                                ? overrideDraftFromOverride(sourceRow.override)
                                : { value: "", inherit: true });
                            const { key: rowKey, ...rowProps } = getRowProps({ row });
                            return (
                              <TableRow key={rowKey} {...rowProps}>
                                {row.cells.map((cell) => {
                                  if (cell.info.header === "override") {
                                    return (
                                      <TableCell key={cell.id}>
                                        <NumberInput
                                          id={`nia-override-${userId}`}
                                          hideLabel
                                          label="Override cap"
                                          placeholder="Inherit"
                                          allowEmpty
                                          value={draft.inherit ? "" : draft.value}
                                          min={0}
                                          step={1000}
                                          disabled={savingUserId === userId}
                                          onChange={(_, { value }) => {
                                            if (typeof value === "number") {
                                              setOverrideDrafts((current) => ({
                                                ...current,
                                                [userId]: {
                                                  value: String(value),
                                                  inherit: false,
                                                },
                                              }));
                                              return;
                                            }
                                            if (typeof value === "string") {
                                              setOverrideDrafts((current) => ({
                                                ...current,
                                                [userId]: {
                                                  value,
                                                  inherit: value.trim() === "",
                                                },
                                              }));
                                            }
                                          }}
                                        />
                                      </TableCell>
                                    );
                                  }
                                  if (cell.info.header === "actions") {
                                    return (
                                      <TableCell key={cell.id}>
                                        <Button
                                          kind="ghost"
                                          size="sm"
                                          disabled={savingUserId === userId}
                                          onClick={() => void handleSaveOverride(userId)}
                                        >
                                          {savingUserId === userId ? "Saving…" : "Save"}
                                        </Button>
                                      </TableCell>
                                    );
                                  }
                                  return <TableCell key={cell.id}>{cell.value}</TableCell>;
                                })}
                              </TableRow>
                            );
                          })}
                        </TableBody>
                      </Table>
                    </TableContainer>
                  )}
                </DataTable>
              )}
            </Stack>
          </Stack>
        ) : null}
      </Stack>
  );

  if (hideChrome) {
    return body;
  }
  return <Tile>{body}</Tile>;
}
