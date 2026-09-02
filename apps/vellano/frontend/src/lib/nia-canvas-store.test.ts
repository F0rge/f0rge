import { beforeEach, describe, expect, it } from "vitest";

import {
  bindCanvasUser,
  clearCanvasSpec,
  isCanvasCleared,
  readCanvasSpec,
  writeCanvasSpec,
} from "./nia-canvas-store";
import { hydrateCanvasFromThreadMessages } from "./nia-thread-utils";
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
