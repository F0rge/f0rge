import { describe, expect, it } from "vitest";

import {
  formatNextRun,
  isScheduleToggleKey,
  replaceScheduleTask,
  scheduleToggleLabel,
  scheduleToggleStateLabel,
  shouldHandleScheduleRowToggleKey,
  withScheduleEnabled,
} from "./nia-schedule";

describe("formatNextRun", () => {
  it("returns an em dash when next run is missing", () => {
    expect(formatNextRun(null, "Africa/Johannesburg")).toBe("—");
  });

  it("formats a UTC instant in Johannesburg", () => {
    const label = formatNextRun("2026-09-02T06:00:00.000Z", "Africa/Johannesburg");
    expect(label).toContain("2026");
    expect(label.includes("08:00") || label.includes("8:00")).toBe(true);
  });
});

describe("scheduleToggleStateLabel", () => {
  it("returns On when enabled", () => {
    expect(scheduleToggleStateLabel(true)).toBe("On");
  });

  it("returns Paused when disabled", () => {
    expect(scheduleToggleStateLabel(false)).toBe("Paused");
  });
});

describe("scheduleToggleLabel", () => {
  it("includes the task name and On", () => {
    expect(scheduleToggleLabel("Overdue invoices", true)).toBe("Overdue invoices — On");
  });

  it("includes the task name and Paused", () => {
    expect(scheduleToggleLabel("Overdue invoices", false)).toBe(
      "Overdue invoices — Paused",
    );
  });
});

describe("withScheduleEnabled", () => {
  const rows = [
    { id: "a", enabled: true, name: "Overdue" },
    { id: "b", enabled: false, name: "Transfers" },
  ];

  it("flips only the matching row (optimistic apply)", () => {
    expect(withScheduleEnabled(rows, "a", false)).toEqual([
      { id: "a", enabled: false, name: "Overdue" },
      { id: "b", enabled: false, name: "Transfers" },
    ]);
  });

  it("restores the previous enabled value (rollback)", () => {
    const flipped = withScheduleEnabled(rows, "a", false);
    expect(withScheduleEnabled(flipped, "a", true)).toEqual(rows);
  });
});

describe("replaceScheduleTask", () => {
  it("replaces the matching row with the server payload", () => {
    const rows = [
      { id: "a", enabled: false, name: "Overdue" },
      { id: "b", enabled: true, name: "Transfers" },
    ];
    const updated = { id: "a", enabled: true, name: "Overdue invoices" };
    expect(replaceScheduleTask(rows, updated)).toEqual([
      updated,
      { id: "b", enabled: true, name: "Transfers" },
    ]);
  });
});

describe("isScheduleToggleKey", () => {
  it("is true for Space and Enter", () => {
    expect(isScheduleToggleKey(" ")).toBe(true);
    expect(isScheduleToggleKey("Spacebar")).toBe(true);
    expect(isScheduleToggleKey("Enter")).toBe(true);
  });

  it("is false for other keys", () => {
    expect(isScheduleToggleKey("r")).toBe(false);
    expect(isScheduleToggleKey("Escape")).toBe(false);
    expect(isScheduleToggleKey("Tab")).toBe(false);
    expect(isScheduleToggleKey("ArrowDown")).toBe(false);
  });
});

describe("shouldHandleScheduleRowToggleKey", () => {
  function targetMatching(...selectors: string[]) {
    return {
      closest: (selector: string) => (selectors.includes(selector) ? {} : null),
    };
  }

  it("handles Space and Enter on the focused row", () => {
    const row = { closest: () => null };
    expect(shouldHandleScheduleRowToggleKey(row, " ", false)).toBe(true);
    expect(shouldHandleScheduleRowToggleKey(row, "Enter", false)).toBe(true);
  });

  it("ignores a busy row", () => {
    expect(shouldHandleScheduleRowToggleKey({ closest: () => null }, " ", true)).toBe(
      false,
    );
  });

  it("ignores the Carbon Toggle (no double fire)", () => {
    expect(
      shouldHandleScheduleRowToggleKey(
        { id: "nia-task-enabled-abc", closest: () => null },
        " ",
        false,
      ),
    ).toBe(false);
    expect(
      shouldHandleScheduleRowToggleKey(
        targetMatching("button.cds--toggle__button"),
        "Enter",
        false,
      ),
    ).toBe(false);
    expect(
      shouldHandleScheduleRowToggleKey(targetMatching('[role="switch"]'), " ", false),
    ).toBe(false);
  });

  it("does not steal OverflowMenu keys", () => {
    expect(
      shouldHandleScheduleRowToggleKey(
        targetMatching(".cds--overflow-menu"),
        "Enter",
        false,
      ),
    ).toBe(false);
    expect(
      shouldHandleScheduleRowToggleKey(targetMatching('[role="menuitem"]'), " ", false),
    ).toBe(false);
  });
});
