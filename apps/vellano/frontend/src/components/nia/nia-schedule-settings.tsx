"use client";

import {
  Button,
  Checkbox,
  DataTable,
  FeatureFlags,
  InlineNotification,
  Loading,
  MenuItem,
  Modal,
  OverflowMenu,
  Select,
  SelectItem,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableHeader,
  TableRow,
  TextArea,
  TextInput,
  Toggle,
} from "@carbon/react";
import { Add } from "@carbon/icons-react";
import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  createNiaSchedule,
  deleteNiaSchedule,
  listNiaSchedule,
  runNiaScheduleNow,
  updateNiaSchedule,
  type NiaScheduleCadence,
  type NiaScheduledTask,
} from "@/lib/api";
import {
  formatNextRun,
  replaceScheduleTask,
  scheduleToggleLabel,
  shouldHandleScheduleRowToggleKey,
  withScheduleEnabled,
} from "@/lib/nia-schedule";

const HEADERS = [
  { key: "name", header: "Name" },
  { key: "next_run", header: "Next run (SAST)" },
  { key: "last_status", header: "Last status" },
  { key: "enabled", header: "Enabled" },
  { key: "actions", header: "Actions" },
] as const;

const CADENCE_OPTIONS: { id: NiaScheduleCadence; text: string }[] = [
  { id: "weekdays_08", text: "Weekdays 08:00" },
  { id: "daily_08", text: "Daily 08:00" },
  { id: "weekly_mon_08", text: "Mondays 08:00" },
  { id: "hourly", text: "Hourly" },
  { id: "custom", text: "Custom" },
];

const TIMEZONE_OPTIONS = [
  { id: "Africa/Johannesburg", text: "Africa/Johannesburg (SAST)" },
  { id: "UTC", text: "UTC" },
  { id: "Africa/Maputo", text: "Africa/Maputo" },
  { id: "Europe/London", text: "Europe/London" },
];

const DEFAULT_TZ = "Africa/Johannesburg";

type Draft = {
  name: string;
  prompt: string;
  timezone: string;
  cadence: NiaScheduleCadence;
  cron: string;
  enabled: boolean;
  notify_only_if_changed: boolean;
};

function emptyDraft(): Draft {
  return {
    name: "",
    prompt: "",
    timezone: DEFAULT_TZ,
    cadence: "weekdays_08",
    cron: "",
    enabled: true,
    notify_only_if_changed: false,
  };
}

function draftFromTask(task: NiaScheduledTask): Draft {
  return {
    name: task.name,
    prompt: task.prompt,
    timezone: task.timezone,
    cadence: (task.cadence as NiaScheduleCadence) || "custom",
    cron: task.cron ?? "",
    enabled: task.enabled,
    notify_only_if_changed: task.notify_only_if_changed,
  };
}

function statusLabel(task: NiaScheduledTask): string {
  if (!task.last_status) {
    return "—";
  }
  if (task.last_status === "error" && task.last_error) {
    return `error (${task.last_error})`;
  }
  return task.last_status;
}

export function NiaScheduleSettings() {
  const [tasks, setTasks] = useState<NiaScheduledTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<NiaScheduledTask | null>(null);
  const [draft, setDraft] = useState<Draft>(emptyDraft);
  const [saving, setSaving] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const rows = await listNiaSchedule();
      setTasks(rows);
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "Failed to load scheduled tasks");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  function openCreate() {
    setEditing(null);
    setDraft(emptyDraft());
    setModalOpen(true);
  }

  function openEdit(task: NiaScheduledTask) {
    setEditing(task);
    setDraft(draftFromTask(task));
    setModalOpen(true);
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    setNotice(null);
    const payload = {
      name: draft.name.trim(),
      prompt: draft.prompt.trim(),
      timezone: draft.timezone,
      cadence: draft.cadence,
      cron: draft.cadence === "custom" ? draft.cron.trim() : undefined,
      enabled: draft.enabled,
      notify_only_if_changed: draft.notify_only_if_changed,
    };
    try {
      if (editing) {
        const updated = await updateNiaSchedule(editing.id, payload);
        setTasks((current) => current.map((row) => (row.id === updated.id ? updated : row)));
        setNotice("Task updated.");
      } else {
        const created = await createNiaSchedule(payload);
        setTasks((current) => [created, ...current]);
        setNotice("Task created.");
      }
      setModalOpen(false);
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "Failed to save task");
    } finally {
      setSaving(false);
    }
  }

  async function handleToggle(task: NiaScheduledTask, enabled: boolean) {
    const previousEnabled = task.enabled;
    setBusyId(task.id);
    setError(null);
    setNotice(null);
    setTasks((current) => withScheduleEnabled(current, task.id, enabled));
    try {
      const updated = await updateNiaSchedule(task.id, { enabled });
      setTasks((current) => replaceScheduleTask(current, updated));
      setNotice(enabled ? "Task enabled." : "Task paused.");
    } catch (err: unknown) {
      setTasks((current) => withScheduleEnabled(current, task.id, previousEnabled));
      setError(err instanceof ApiError ? err.message : "Failed to update task");
    } finally {
      setBusyId(null);
    }
  }

  async function handleDelete(task: NiaScheduledTask) {
    setBusyId(task.id);
    setError(null);
    try {
      await deleteNiaSchedule(task.id);
      setTasks((current) => current.filter((row) => row.id !== task.id));
      setNotice("Task deleted.");
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "Failed to delete task");
    } finally {
      setBusyId(null);
    }
  }

  async function handleRunNow(task: NiaScheduledTask) {
    setBusyId(task.id);
    setError(null);
    setNotice(null);
    try {
      const updated = await runNiaScheduleNow(task.id);
      setTasks((current) => current.map((row) => (row.id === updated.id ? updated : row)));
      if (updated.last_status === "needs_ok") {
        setNotice("Run finished — Nia needs approval in the dock before any write.");
      } else if (updated.last_status === "error") {
        setError(updated.last_error ?? "Run failed");
      } else {
        setNotice("Run finished. Open Nia history to read the thread.");
      }
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "Failed to run task");
    } finally {
      setBusyId(null);
    }
  }

  const rows = tasks.map((task) => ({
    id: task.id,
    name: task.name,
    next_run: formatNextRun(task.next_run_at, task.timezone),
    last_status: statusLabel(task),
    enabled: task.id,
    actions: task.id,
  }));

  return (
    <Stack gap={5}>
      <p className="cds--type-body-01 vellano-muted-text">
        Named prompts Nia runs on a clock as you. Writes still need a tap in the dock.
      </p>

      {error ? <InlineNotification kind="error" title="Scheduled" subtitle={error} hideCloseButton /> : null}
      {notice ? (
        <InlineNotification kind="success" title="Scheduled" subtitle={notice} hideCloseButton />
      ) : null}

      <div>
        <Button kind="primary" size="sm" renderIcon={Add} onClick={openCreate}>
          New task
        </Button>
      </div>

      {loading ? (
        <Loading withOverlay={false} description="Loading scheduled tasks…" />
      ) : tasks.length === 0 ? (
        <Stack gap={3}>
          <p className="cds--type-body-01">
            Nia can chase overdue invoices every weekday at 8:00.
          </p>
          <p className="cds--type-helper-text-01 vellano-muted-text">
            Examples: weekdays 08:00 SAST overdue invoices; weekdays 08:30 Bedfordview vs
            Kramerville qty; Friday 16:00 open transfers still in transit.
          </p>
        </Stack>
      ) : (
        <DataTable rows={rows} headers={[...HEADERS]}>
          {({ rows: tableRows, headers, getHeaderProps, getRowProps, getTableProps }) => (
            <TableContainer>
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
                  {tableRows.map((row) => {
                    const task = tasks.find((entry) => entry.id === row.id);
                    const { key: rowKey, ...rowProps } = getRowProps({ row });
                    const rowBusy = Boolean(task && busyId === task.id);
                    return (
                      <TableRow
                        key={rowKey}
                        {...rowProps}
                        tabIndex={0}
                        onKeyDown={(event) => {
                          if (!task) {
                            return;
                          }
                          if (
                            !shouldHandleScheduleRowToggleKey(event.target, event.key, rowBusy)
                          ) {
                            return;
                          }
                          event.preventDefault();
                          void handleToggle(task, !task.enabled);
                        }}
                      >
                        {row.cells.map((cell) => {
                          if (cell.info.header === "enabled" && task) {
                            return (
                              <TableCell key={cell.id} aria-busy={rowBusy}>
                                <Toggle
                                  id={`nia-task-enabled-${task.id}`}
                                  size="sm"
                                  hideLabel
                                  labelA="Paused"
                                  labelB="On"
                                  labelText={scheduleToggleLabel(task.name, task.enabled)}
                                  toggled={task.enabled}
                                  disabled={rowBusy}
                                  onToggle={(checked) => void handleToggle(task, checked)}
                                />
                              </TableCell>
                            );
                          }
                          if (cell.info.header === "actions" && task) {
                            return (
                              <TableCell key={cell.id}>
                                <FeatureFlags
                                  enableV12Overflowmenu
                                  enableV12DynamicFloatingStyles
                                >
                                  <OverflowMenu
                                    size="sm"
                                    autoAlign
                                    menuAlignment="bottom-end"
                                    label={`Actions for ${task.name}`}
                                  >
                                    <MenuItem
                                      label="Edit"
                                      onClick={() => openEdit(task)}
                                    />
                                    <MenuItem
                                      label={busyId === task.id ? "Running…" : "Run now"}
                                      disabled={busyId === task.id}
                                      onClick={() => void handleRunNow(task)}
                                    />
                                    <MenuItem
                                      kind="danger"
                                      label="Delete"
                                      disabled={busyId === task.id}
                                      onClick={() => void handleDelete(task)}
                                    />
                                  </OverflowMenu>
                                </FeatureFlags>
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

      <Modal
        open={modalOpen}
        modalHeading={editing ? "Edit scheduled task" : "New scheduled task"}
        primaryButtonText={saving ? "Saving…" : "Save"}
        secondaryButtonText="Cancel"
        primaryButtonDisabled={saving || !draft.name.trim() || !draft.prompt.trim()}
        onRequestClose={() => setModalOpen(false)}
        onRequestSubmit={() => void handleSave()}
      >
        <Stack gap={5}>
          <TextInput
            id="nia-task-name"
            labelText="Name"
            value={draft.name}
            onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))}
          />
          <TextArea
            id="nia-task-prompt"
            labelText="Prompt"
            helperText="Nia runs this as you. Writes stay on HITL — they are never auto-approved."
            value={draft.prompt}
            rows={5}
            onChange={(event) =>
              setDraft((current) => ({ ...current, prompt: event.target.value }))
            }
          />
          <Select
            id="nia-task-cadence"
            labelText="Cadence"
            value={draft.cadence}
            onChange={(event) =>
              setDraft((current) => ({
                ...current,
                cadence: event.target.value as NiaScheduleCadence,
              }))
            }
          >
            {CADENCE_OPTIONS.map((option) => (
              <SelectItem key={option.id} value={option.id} text={option.text} />
            ))}
          </Select>
          {draft.cadence === "custom" ? (
            <TextInput
              id="nia-task-cron"
              labelText="Custom cron"
              helperText="Five fields. Fastest allowed interval is 15 minutes."
              placeholder="30 8 * * 1-5"
              value={draft.cron}
              onChange={(event) =>
                setDraft((current) => ({ ...current, cron: event.target.value }))
              }
            />
          ) : null}
          <Select
            id="nia-task-timezone"
            labelText="Timezone"
            value={draft.timezone}
            onChange={(event) =>
              setDraft((current) => ({ ...current, timezone: event.target.value }))
            }
          >
            {TIMEZONE_OPTIONS.map((option) => (
              <SelectItem key={option.id} value={option.id} text={option.text} />
            ))}
          </Select>
          <Toggle
            id="nia-task-enabled"
            labelText="Enabled"
            labelA="Paused"
            labelB="On"
            toggled={draft.enabled}
            onToggle={(checked) => setDraft((current) => ({ ...current, enabled: checked }))}
          />
          <Checkbox
            id="nia-task-notify-changed"
            labelText="Mark skipped when the output has not changed"
            checked={draft.notify_only_if_changed}
            onChange={(_, { checked }) =>
              setDraft((current) => ({ ...current, notify_only_if_changed: checked }))
            }
          />
        </Stack>
      </Modal>
    </Stack>
  );
}
