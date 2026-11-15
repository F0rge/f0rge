import type { components } from "./api/generated";
type WireCategory = components["schemas"]["CategoryState"];
export type Category = WireCategory & {
  watch: NonNullable<WireCategory["watch"]>;
  log: NonNullable<WireCategory["log"]>;
  costs: NonNullable<WireCategory["costs"]>;
};
export type BrowserState = components["schemas"]["BrowserState"] & {
  bikes: Category;
  wheels: Category;
};
export type Kind = "bikes" | "wheels";
export function normalizeState(
  state: components["schemas"]["BrowserState"],
): BrowserState {
  const category = (value: WireCategory | undefined): Category => ({
    ...value,
    watch: value?.watch ?? {},
    log: value?.log ?? [],
    costs: value?.costs ?? {},
  });
  return {
    ...state,
    bikes: category(state.bikes),
    wheels: category(state.wheels),
  };
}
export type ConflictPolicy = "reject" | "keep_existing" | "replace";
export const costLabels: Record<string, string> = {
  bp: "Buyer protection %",
  bpf: "Buyer protection fixed €",
  pay: "Payment / FX fee %",
  shipin: "Inbound shipping €",
  pack: "Packaging €",
  repair: "Repair / servicing €",
  buffer: "Risk buffer €",
  haircut: "Negotiation haircut %",
  sellfee: "Seller fee %",
  shipout: "Outbound shipping €",
  relist: "Boost / relist €",
};
export const numericFilters = [
  { key: "pmin", label: "Minimum price €", field: "price", direction: "min" },
  { key: "pmax", label: "Maximum price €", field: "price", direction: "max" },
  {
    key: "avmin",
    label: "Minimum average ask €",
    field: "average_ask",
    direction: "min",
  },
  {
    key: "avmax",
    label: "Maximum average ask €",
    field: "average_ask",
    direction: "max",
  },
  { key: "zmin", label: "Minimum Z-score", field: "z_score", direction: "min" },
  { key: "zmax", label: "Maximum Z-score", field: "z_score", direction: "max" },
  {
    key: "csmin",
    label: "Minimum €/day cut",
    field: "cut_per_day",
    direction: "min",
  },
  {
    key: "stmin",
    label: "Minimum disappeared within 30d %",
    field: "sold_percent",
    direction: "min",
  },
  {
    key: "vsmax",
    label: "Maximum days vs typical",
    field: "versus_typical",
    direction: "max",
  },
  {
    key: "nxmin",
    label: "Minimum next-up days",
    field: "next_up_days",
    direction: "min",
  },
  { key: "minp", label: "Minimum profit €", field: "profit", direction: "min" },
  { key: "minr", label: "Minimum ROI %", field: "roi", direction: "min" },
  {
    key: "minc",
    label: "Minimum comparables",
    field: "comparables",
    direction: "min",
  },
  {
    key: "dmax",
    label: "Maximum days listed",
    field: "days_listed",
    direction: "max",
  },
  {
    key: "kmax",
    label: "Maximum distance km",
    field: "distance_km",
    direction: "max",
  },
] as const;
export function object(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
export function stable(value: unknown): string {
  if (Array.isArray(value)) return "[" + value.map(stable).join(",") + "]";
  if (object(value))
    return (
      "{" +
      Object.keys(value)
        .sort()
        .map((key) => JSON.stringify(key) + ":" + stable(value[key]))
        .join(",") +
      "}"
    );
  return JSON.stringify(value) ?? "null";
}
export function finiteNonnegative(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value) && value >= 0;
}

export function validateLegacy(value: unknown): string[] {
  if (!object(value)) return ["The imported category must be an object."];
  const errors: string[] = [];
  if (value.watch !== undefined && !object(value.watch))
    errors.push("Watchlist must be an object.");
  if (object(value.watch))
    for (const [id, entry] of Object.entries(value.watch))
      if (
        !id ||
        !object(entry) ||
        typeof entry.n !== "string" ||
        typeof entry.u !== "string" ||
        !finiteNonnegative(entry.p) ||
        typeof entry.t !== "string"
      )
        errors.push(`Watch entry ${id || "(missing ID)"} needs review.`);
  if (value.log !== undefined && !Array.isArray(value.log))
    errors.push("Trade log must be an array.");
  if (Array.isArray(value.log))
    value.log.forEach((entry, index) => {
      if (
        !object(entry) ||
        typeof entry.name !== "string" ||
        !finiteNonnegative(entry.buy) ||
        (entry.sell !== undefined &&
          entry.sell !== null &&
          !finiteNonnegative(entry.sell))
      )
        errors.push(`Trade ${index + 1} needs review.`);
    });
  if (value.costs !== undefined && !object(value.costs))
    errors.push("Costs must be an object.");
  if (object(value.costs))
    for (const [key, cost] of Object.entries(value.costs))
      if (
        !finiteNonnegative(cost) ||
        (["bp", "pay", "haircut", "sellfee"].includes(key) && cost > 100)
      )
        errors.push(`Cost ${key} needs review.`);
  for (const key of Object.keys(value))
    if (!["watch", "log", "costs"].includes(key))
      errors.push(
        `Unsupported category field ${key}; retain the original file for manual review.`,
      );
  return errors;
}

/** Build a preview without writing browser/server state. Unknown row fields survive. */
export function mergeLegacy(
  current: BrowserState,
  documents: { kind: Kind; document: unknown }[],
  policy: ConflictPolicy,
): {
  state: BrowserState;
  conflicts: string[];
  errors: string[];
  counts: { watches: number; trades: number; costs: number };
} {
  const state = structuredClone(current);
  const conflicts: string[] = [];
  const errors: string[] = [];
  const counts = { watches: 0, trades: 0, costs: 0 };
  for (const { kind, document } of documents) {
    errors.push(
      ...validateLegacy(document).map((message) => `${kind}: ${message}`),
    );
    if (!object(document) || validateLegacy(document).length) continue;
    const category = state[kind];
    if (object(document.watch))
      for (const [id, value] of Object.entries(document.watch)) {
        const existing = Object.hasOwn(category.watch, id)
          ? category.watch[id]
          : undefined;
        if (existing && stable(existing) !== stable(value)) {
          conflicts.push(`${kind}: watch ${id}`);
          if (policy !== "replace") continue;
        }
        // Runtime validation above and generated types are checked again by the server.
        category.watch = {
          ...category.watch,
          [id]: value as Category["watch"][string],
        };
        counts.watches++;
      }
    const occurrences = new Map<string, number>();
    if (Array.isArray(document.log))
      for (const entry of document.log) {
        const incoming = entry as Category["log"][number];
        const id = incoming.id;
        const fingerprint = stable(incoming);
        const count = (occurrences.get(fingerprint) ?? 0) + 1;
        occurrences.set(fingerprint, count);
        const matches = category.log.flatMap((row, index) =>
          (id ? row.id === id : stable(row) === fingerprint) ? [index] : [],
        );
        const same = id ? (matches[0] ?? -1) : (matches[count - 1] ?? -1);
        if (same >= 0) {
          if (stable(category.log[same]) !== stable(incoming)) {
            conflicts.push(`${kind}: trade ${same + 1}`);
            if (policy === "replace") category.log[same] = incoming;
          }
          continue;
        }
        category.log.push(incoming);
        counts.trades++;
      }
    if (object(document.costs))
      for (const [key, value] of Object.entries(document.costs)) {
        if (
          Object.hasOwn(category.costs, key) &&
          category.costs[key] !== value
        ) {
          conflicts.push(`${kind}: cost ${key}`);
          if (policy !== "replace") continue;
        }
        category.costs = { ...category.costs, [key]: value as number };
        counts.costs++;
      }
  }
  return { state, conflicts, errors, counts };
}
export function currentOriginExports(storage: Pick<Storage, "getItem">): {
  version: 1;
  origin: string;
  exported_at: string;
  documents: { kind: Kind; document: unknown }[];
} {
  return {
    version: 1,
    origin: location.origin,
    exported_at: new Date().toISOString(),
    documents: (["bikes", "wheels"] as const).map((kind) => ({
      kind,
      document: {
        watch: JSON.parse(storage.getItem(kind + ":watch") ?? "{}") as unknown,
        log: JSON.parse(storage.getItem(kind + ":log") ?? "[]") as unknown,
        costs: JSON.parse(storage.getItem(kind + ":costs") ?? "{}") as unknown,
      },
    })),
  };
}
export function downloadJson(value: unknown, name: string) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
