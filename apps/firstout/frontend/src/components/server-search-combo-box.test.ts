import { describe, expect, it } from "vitest";

import { itemsWithSelection, searchForInput, selectedSearchOption } from "./server-search-combo-box";

const inv42 = { id: "inv-42", label: "INV-0042 — Thandi Mokoena" };
const inv43 = { id: "inv-43", label: "INV-0043 — Walk-in" };

describe("server-searched picker selection", () => {
  it("keeps the picked option when the next search no longer returns it", () => {
    // Picking writes the label into the input; the server finds nothing for it.
    const selected = selectedSearchOption([], inv42.id, inv42);
    expect(selected).toBe(inv42);
    expect(itemsWithSelection([inv43], selected)).toEqual([inv42, inv43]);
  });

  it("does not search for the selected option's own label", () => {
    expect(searchForInput(inv42.label, inv42)).toBeNull();
    expect(searchForInput("INV-004", inv42)).toBe("INV-004");
    expect(searchForInput("", inv42)).toBe("");
    expect(searchForInput(inv42.label, null)).toBe(inv42.label);
  });

  it("finds a prefilled id in the results and drops a stale pick", () => {
    expect(selectedSearchOption([inv43, inv42], inv42.id, null)).toBe(inv42);
    expect(selectedSearchOption([], inv43.id, inv42)).toBeNull();
    expect(selectedSearchOption([inv42], "", inv42)).toBeNull();
    expect(itemsWithSelection([inv42, inv43], inv42)).toEqual([inv42, inv43]);
  });
});
