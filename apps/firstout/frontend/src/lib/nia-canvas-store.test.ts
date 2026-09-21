import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  bindCanvasUser,
  clearCanvasSpec,
  isCanvasCleared,
  readCanvasSpec,
  writeCanvasSpec,
} from "./nia-canvas-store";
import {
  canvasEventInstant,
  hydrateCanvasFromThreadMessages,
  syncCanvasSpecFromThread,
} from "./nia-thread-utils";
import type { CanvasSpec } from "./nia-canvas-types";
import type { NiaMessage } from "./api";

class MemoryStorage {
  private readonly data = new Map<string, string>();

  getItem(key: string): string | null {
    return this.data.has(key) ? (this.data.get(key) as string) : null;
  }

  setItem(key: string, value: string): void {
    this.data.set(key, value);
  }

  removeItem(key: string): void {
    this.data.delete(key);
  }
}

function diningSpec(): CanvasSpec {
  return {
    kind: "canvas_spec",
    path: "/canvas",
    title: "Dining vs sofas this month",
    components: [
      {
        type: "bar",
        id: "dining-vs-sofas",
        title: "Sales this month (ZAR inc VAT)",
        categories: ["Dining", "Sofas"],
        series: [{ name: "Sales", values: [13800, 8050] }],
      },
    ],
  };
}

function overdueSpec(): CanvasSpec {
  return {
    kind: "canvas_spec",
    path: "/canvas",
    title: "Overdue invoices",
    components: [
      {
        type: "table",
        id: "overdue-invoices",
        title: "Overdue invoices (30-day terms)",
        headers: ["Invoice"],
        rows: [["INV-0001"]],
      },
    ],
  };
}

afterEach(() => {
  vi.useRealTimers();
});

beforeEach(() => {
  const local = new MemoryStorage();
  const session = new MemoryStorage();
  Object.defineProperty(globalThis, "window", {
    configurable: true,
    value: { localStorage: local, sessionStorage: session },
  });
});

describe("nia canvas store", () => {
  it("writes a spec that survives a later read (refresh)", () => {
    bindCanvasUser("user-1");
    writeCanvasSpec(overdueSpec());
    expect(readCanvasSpec()?.title).toBe("Overdue invoices");
    expect(isCanvasCleared()).toBe(false);
  });

  it("clear wipes the spec and blocks hydrate from an older dining thread", () => {
    bindCanvasUser("user-1");
    writeCanvasSpec(diningSpec());
    clearCanvasSpec();
    expect(readCanvasSpec()).toBeNull();
    expect(isCanvasCleared()).toBe(true);

    const hydrated = hydrateCanvasFromThreadMessages([
      {
        messages: [
          {
            id: "m1",
            role: "assistant",
            content: "chart",
            structured_payload: diningSpec(),
            created_at: "2026-09-01T10:00:00Z",
          } satisfies NiaMessage,
        ],
      },
    ]);
    expect(hydrated).toBe(false);
    expect(readCanvasSpec()).toBeNull();
    expect(isCanvasCleared()).toBe(true);
  });

  it("hydrate prefers a newer clear over an older dining spec", () => {
    const hydrated = hydrateCanvasFromThreadMessages([
      {
        messages: [
          {
            id: "m1",
            role: "assistant",
            content: "chart",
            structured_payload: diningSpec(),
            created_at: "2026-09-01T10:00:00Z",
          },
          {
            id: "m2",
            role: "assistant",
            content: "cleared",
            structured_payload: { kind: "canvas_cleared", path: "/canvas" },
            created_at: "2026-09-01T11:00:00Z",
          },
        ],
      },
    ]);
    expect(hydrated).toBe(false);
    expect(readCanvasSpec()).toBeNull();
    expect(isCanvasCleared()).toBe(true);
  });

  it("switching users does not keep the previous canvas", () => {
    bindCanvasUser("user-1");
    writeCanvasSpec(diningSpec());
    bindCanvasUser("user-2");
    expect(readCanvasSpec()).toBeNull();
  });
});

function chainedTurnMessages(): NiaMessage[] {
  // One turn: chart tool, then the SKU write tool that takes the payload slot.
  return [
    {
      id: "m1",
      role: "user",
      content: "chart dining vs sofas this month, then help me add a new colour SKU",
      structured_payload: null,
      created_at: "2026-09-03T10:00:00.100000",
    },
    {
      id: "m2",
      role: "assistant",
      content: "",
      structured_payload: diningSpec(),
      created_at: "2026-09-03T10:00:00.200000",
    },
    {
      id: "m3",
      role: "assistant",
      content: "Chart's up — Dining R13,800 vs Sofas R8,050 (inc VAT).",
      structured_payload: {
        kind: "needs_fields",
        action_id: "create_sku",
        title: "Create SKU",
        fields: [{ id: "our_ref", label: "Our ref", type: "text", required: true }],
        values: {},
      },
      created_at: "2026-09-03T10:00:00.300000",
    },
  ];
}

describe("nia canvas chained turn (chart then SKU form)", () => {
  it("dock sync keeps the chart when needs_fields is the newest payload", () => {
    bindCanvasUser("user-1");
    syncCanvasSpecFromThread({
      id: "t1",
      title: "chained",
      created_at: "2026-09-03T10:00:00",
      updated_at: "2026-09-03T10:00:00",
      archived_at: null,
      messages: chainedTurnMessages(),
    } as unknown as Parameters<typeof syncCanvasSpecFromThread>[0]);

    expect(readCanvasSpec()?.title).toBe("Dining vs sofas this month");
    expect(readCanvasSpec()?.components[0]?.id).toBe("dining-vs-sofas");
    expect(isCanvasCleared()).toBe(false);
  });

  it("/canvas hydrates the chart from the thread after that one turn", () => {
    const hydrated = hydrateCanvasFromThreadMessages([{ messages: chainedTurnMessages() }]);

    expect(hydrated).toBe(true);
    expect(readCanvasSpec()?.title).toBe("Dining vs sofas this month");
  });

  it("hydrates a chart charted after an earlier local clear", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-03T09:00:00Z"));
    bindCanvasUser("user-1");
    writeCanvasSpec(overdueSpec());
    clearCanvasSpec();
    expect(readCanvasSpec()).toBeNull();

    const hydrated = hydrateCanvasFromThreadMessages([{ messages: chainedTurnMessages() }]);

    expect(hydrated).toBe(true);
    expect(readCanvasSpec()?.title).toBe("Dining vs sofas this month");
    expect(isCanvasCleared()).toBe(false);
  });

  it("keeps a clear that is newer than the thread chart", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-03T11:00:00Z"));
    bindCanvasUser("user-1");
    writeCanvasSpec(overdueSpec());
    clearCanvasSpec();

    const hydrated = hydrateCanvasFromThreadMessages([{ messages: chainedTurnMessages() }]);

    expect(hydrated).toBe(false);
    expect(readCanvasSpec()).toBeNull();
    expect(isCanvasCleared()).toBe(true);
  });

  it("reads naive thread timestamps as UTC", () => {
    expect(canvasEventInstant("2026-09-03T10:00:00.200000")).toBe(
      Date.parse("2026-09-03T10:00:00.200Z"),
    );
    expect(canvasEventInstant("2026-09-03T10:00:00Z")).toBe(Date.parse("2026-09-03T10:00:00Z"));
    expect(canvasEventInstant(null)).toBeNull();
    expect(canvasEventInstant("not-a-date")).toBeNull();
  });
});
