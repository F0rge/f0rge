import { describe, expect, it } from "vitest";
import {
  bulkPatch,
  fieldOperators,
  isWorkspaceFilter,
  readWorkspaceQuery,
  selectionContext,
  quickFilterValue,
  workspaceIdentity,
  workspaceSearch,
  workspaceStateForKey,
  workspaceScalar,
} from "./record-workspace";
import type { AuthUser } from "./api";

const defaults = () => readWorkspaceQuery(new URLSearchParams());
describe("record workspace URL state", () => {
  it("reads a leading minus on the default sort as descending until the URL picks a sort", () => {
    expect(readWorkspaceQuery(new URLSearchParams(), "-paid_on").sort).toEqual({
      field: "paid_on",
      direction: "desc",
    });
    expect(
      readWorkspaceQuery(new URLSearchParams("sort=amount&direction=asc"), "-paid_on").sort,
    ).toEqual({ field: "amount", direction: "asc" });
  });
  it("does not mislabel advanced numeric thresholds as zero shortcuts", () => {
    expect(
      quickFilterValue("number", {
        field: "amount",
        operator: "gt",
        value: 10000,
      }),
    ).toBe("");
    expect(
      quickFilterValue("number", {
        field: "amount",
        operator: "eq",
        value: 100,
      }),
    ).toBe("");
    expect(
      quickFilterValue("number", { field: "amount", operator: "gt", value: 0 }),
    ).toBe("positive");
    expect(
      quickFilterValue("number", { field: "amount", operator: "eq", value: 0 }),
    ).toBe("zero");
  });
  it("round trips typed filter groups, paging and sort without putting selections in the URL", () => {
    const query = {
      ...defaults(),
      q: "Oak & Grain",
      lifecycle: "archived" as const,
      match: "any" as const,
      filters: [
        { field: "open_invoices_zar", operator: "gt" as const, value: 0 },
        { field: "on_hold", operator: "eq" as const, value: false },
      ],
      sort: { field: "updated_at", direction: "desc" as const },
      limit: 50,
      offset: 100,
    };
    const params = new URLSearchParams(workspaceSearch(query, "record-id"));
    expect(readWorkspaceQuery(params)).toEqual(query);
    expect(params.get("record")).toBe("record-id");
    expect(params.has("ids")).toBe(false);
  });
  it("retains older archived deep links and rejects unsupported page sizes", () => {
    expect(
      readWorkspaceQuery(new URLSearchParams("archived=true&size=7&page=-3")),
    ).toMatchObject({ lifecycle: "archived", limit: 25, offset: 0 });
  });
  it("recovers from malformed URL filters and drops invalid clauses", () => {
    expect(
      readWorkspaceQuery(new URLSearchParams("filters=not-json")).filters,
    ).toEqual([]);
    const params = new URLSearchParams({
      filters: JSON.stringify([
        { field: "name", operator: "sql", value: "x" },
        { field: "name", operator: "contains", value: "Cedar" },
      ]),
    });
    expect(readWorkspaceQuery(params).filters).toEqual([
      { field: "name", operator: "contains", value: "Cedar" },
    ]);
    expect(
      isWorkspaceFilter({ field: "amount", operator: "gt", value: Infinity }),
    ).toBe(false);
  });
});
describe("URL-owned draft transitions", () => {
  it("clears a committed search on reset and when history returns to an empty search", () => {
    let state = { key: "", value: "Acme" };
    state = workspaceStateForKey(state, { key: "Acme", value: "Acme" });
    state = workspaceStateForKey(state, { key: "", value: "" });
    expect(state.value).toBe("");
    state = workspaceStateForKey(state, { key: "Acme", value: "Acme" });
    expect(state.value).toBe("Acme");
    state = workspaceStateForKey(state, { key: "", value: "" });
    expect(state.value).toBe("");
  });
  it("drops an unapplied filter draft when navigating away and back", () => {
    let state = { key: "all", filters: ["unapplied"], match: "any" };
    state = workspaceStateForKey(state, { key: "archived", filters: ["archived"], match: "all" });
    state = workspaceStateForKey(state, { key: "all", filters: [], match: "all" });
    expect(state).toEqual({ key: "all", filters: [], match: "all" });
  });
  it("preserves edits during unrelated renders of the same query", () => {
    const state = { key: "Acme", value: "Acme furniture" };
    expect(workspaceStateForKey(state, { key: "Acme", value: "Acme" })).toBe(state);
  });
});
describe("selection scope", () => {
  it("preserves cross-page selection and resets it when actual filter context changes", () => {
    const query = defaults();
    expect(selectionContext(query, "actor", "customers")).toBe(
      selectionContext(
        { ...query, offset: 25, limit: 50 },
        "actor",
        "customers",
      ),
    );
    expect(selectionContext(query, "actor", "customers")).not.toBe(
      selectionContext({ ...query, q: "Oak" }, "actor", "customers"),
    );
    expect(selectionContext(query, "actor", "customers")).not.toBe(
      selectionContext(query, "other-org", "customers"),
    );
  });
  it("includes grants and role in identity, regardless of permission ordering", () => {
    const user: AuthUser = {
      id: "user",
      email: "staff@example.com",
      role: "buyer",
      permissions: ["catalogue.mutate", "stock.cost.view"],
      team: { id: "team", name: "Sample" },
      display_name: "Sample",
      default_location_id: null,
    };
    expect(workspaceIdentity(user)).toBe(
      workspaceIdentity({
        ...user,
        permissions: [...user.permissions].reverse(),
      }),
    );
    expect(workspaceIdentity(user)).not.toBe(
      workspaceIdentity({ ...user, permissions: [] }),
    );
    expect(workspaceIdentity(user)).not.toBe(
      workspaceIdentity({ ...user, role: "books" }),
    );
  });
});
describe("bulk editing", () => {
  const fields = [
    { key: "phone", label: "Phone", type: "text", nullable: true },
    { key: "terms", label: "Terms", type: "number" },
    { key: "hold", label: "Hold", type: "boolean" },
  ];
  it("keeps omitted fields unchanged and only clears explicitly selected nullable fields", () => {
    expect(
      bulkPatch(fields, {
        phone: { mode: "clear", value: "ignored" },
        terms: { mode: "keep", value: "30" },
      }),
    ).toEqual({ phone: null });
    expect(() =>
      bulkPatch(fields, { phone: { mode: "set", value: "" } }),
    ).toThrow("Enter a value");
    expect(() =>
      bulkPatch(fields, { terms: { mode: "clear", value: "" } }),
    ).toThrow("cannot be cleared");
  });
  it("keeps a boolean placeholder empty instead of silently choosing No", () => {
    const value = workspaceScalar("", "boolean");
    expect(value).toBe("");
    expect(workspaceScalar("false", "boolean")).toBe(false);
    expect(workspaceScalar("true", "boolean")).toBe(true);
    expect(() => bulkPatch(fields, {
      hold: { mode: "set", value: String(value) },
    })).toThrow("Enter a value");
  });
  it("handles valid numeric zero and false without dropping them", () => {
    expect(
      bulkPatch(fields, {
        terms: { mode: "set", value: "0" },
        hold: { mode: "set", value: "false" },
      }),
    ).toEqual({ terms: 0, hold: false });
  });
  it("rejects nonfinite numbers, invalid booleans and empty patches", () => {
    expect(() =>
      bulkPatch(fields, { terms: { mode: "set", value: "Infinity" } }),
    ).toThrow("must be a number");
    expect(() =>
      bulkPatch(fields, { hold: { mode: "set", value: "maybe" } }),
    ).toThrow("must be Yes or No");
    expect(() => bulkPatch(fields, {})).toThrow("Choose at least one field");
  });
  it("offers type-appropriate filter operators", () => {
    expect(fieldOperators("enum").map((item) => item.value)).not.toContain(
      "gt",
    );
    expect(fieldOperators("date").map((item) => item.value)).toContain("gte");
    expect(fieldOperators("text").map((item) => item.value)).toContain(
      "contains",
    );
  });
});
