import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import type { components } from "../src/api/generated";
import { normalizeState, type BrowserState } from "../src/state";
const costs = {
  bp: 2.5,
  bpf: 0,
  pay: 0,
  shipin: 125,
  pack: 0,
  repair: 50,
  buffer: 75,
  haircut: 5,
  sellfee: 6.95,
  shipout: 0,
  relist: 0,
};
const original = (): BrowserState =>
  normalizeState({
    version: 1,
    bikes: { watch: {}, log: [], costs },
    wheels: {
      watch: {},
      log: [],
      costs: {
        ...costs,
        bp: 6,
        bpf: 1,
        shipin: 25,
        pack: 10,
        repair: 0,
        buffer: 20,
        sellfee: 0,
      },
    },
  });
const listing = {
  id: "synthetic-bike",
  kind: "bikes",
  name: "Synthetic carbon bicycle",
  brand: "Sample",
  model: "Road",
  price: 1000,
  original_price: 1200,
  reference_price: 1800,
  average_ask: 1850,
  comparables: 5,
  z_score: -1,
  cut_per_day: 10,
  sold_percent: null,
  sold_sample: null,
  versus_typical: null,
  confidence: "medium",
  dispersion: 0.2,
  discount_percent: 44,
  days_listed: 20,
  first_seen: "2026-10-25",
  gone_at: null,
  url: "https://example.invalid/bicycle",
  year: 2024,
  size: "M",
  country: "Luxembourg",
  risk_flags: [],
  next_up: null,
  history: [
    { day: "2026-11-01", price: 1200 },
    { day: "2026-11-15", price: 1000 },
  ],
  brake: "disc",
  rim_material: "carbon",
  wheel_system: "tubeless",
  seller_reviews: 5,
  photo_count: 8,
  description_length: 300,
  distance_km: 0,
  price_reduced: true,
  price_drop_percent: 16.7,
} satisfies components["schemas"]["Listing"];
async function fixture(
  page: Page,
  {
    denied = false,
    empty = false,
    conflict = false,
  }: { denied?: boolean; empty?: boolean; conflict?: boolean } = {},
) {
  let state = original(),
    revision = 0;
  const writes: unknown[] = [];
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    const method = route.request().method();
    const json = (body: unknown, status = 200) =>
      route.fulfill({
        status,
        contentType: "application/json",
        body: JSON.stringify(body),
      });
    if (denied)
      return json(
        {
          error: {
            code: "forbidden",
            message: "This account is not approved.",
            error_id: "synthetic-error",
            field_errors: [],
          },
        },
        403,
      );
    if (path.endsWith("/status"))
      return json({
        status: "ready",
        last_success: "2026-11-15",
        stale: false,
        blocked: false,
        detail_attempts: 12,
        detail_limit: 150,
        version: "synthetic",
        identity: { subject: "synthetic-approved-person" },
      });
    if (path.endsWith("/listings"))
      return json({
        kind: "bikes",
        generated: "2026-11-15T06:15:00Z",
        today: "2026-11-15",
        items: empty ? [] : [listing],
        active: empty ? 0 : 1,
        gone: 0,
        models: [],
        alerts: [],
      });
    if (path.endsWith("/state") && method === "GET")
      return json({ revision, state });
    if (path.endsWith("/state") && method === "PUT") {
      const body = route
        .request()
        .postDataJSON() as components["schemas"]["StateWrite"];
      writes.push(body);
      if (conflict || body.expected_revision !== revision)
        return json(
          {
            error: {
              code: "conflict",
              message: "The resource changed. Refresh and try again.",
              error_id: "synthetic-conflict",
              field_errors: [],
            },
          },
          409,
        );
      state = normalizeState(body.state);
      revision++;
      return json({ revision, state });
    }
    if (path.endsWith("/import-preview"))
      return json({
        expected_revision: revision,
        counts: { watches: 1, trades: 1, costs: 22 },
        warnings: [],
      });
    if (path.endsWith("/import")) {
      const body = route
        .request()
        .postDataJSON() as components["schemas"]["ImportWrite"];
      writes.push(body);
      state = normalizeState(body.state);
      revision++;
      return json({ revision, state });
    }
    return json(
      {
        error: {
          code: "not_found",
          message: "Not found",
          error_id: "synthetic",
          field_errors: [],
        },
      },
      404,
    );
  });
  await page.route("https://**/*", (route) => route.abort());
  return {
    writes,
    advanceRevision: () => {
      revision++;
    },
    get state() {
      return state;
    },
  };
}
test("private denial shows no records and offers the approved Access sign-in", async ({
  page,
}) => {
  await fixture(page, { denied: true });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Private Buycycle" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Sign in through Cloudflare Access" }),
  ).toHaveAttribute("href", "/cdn-cgi/access/login");
  await expect(page.getByText("Synthetic carbon bicycle")).toHaveCount(0);
});
test("browse, filter, watch and preserve missing observations", async ({
  page,
}) => {
  const f = await fixture(page);
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "1 matching listings" }),
  ).toBeVisible();
  await expect(page.getByText("Not observed").first()).toBeVisible();
  await page.getByRole("button", { name: "Watch", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Remove watch", exact: true }),
  ).toBeVisible();
  expect(f.state.bikes.watch["synthetic-bike"]?.n).toBe(listing.name);
  await page.getByLabel("Search model or brand").fill("does not exist");
  await expect(
    page.getByText(
      "No listings match these filters. Reset filters or switch category.",
    ),
  ).toBeVisible();
  expect(new URL(page.url()).searchParams.get("q")).toBe("does not exist");
  await page
    .getByRole("button", { name: "Reset filters", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "1 matching listings" }),
  ).toBeVisible();
});
test("trade and cost edits use TanStack forms and preserve all cost keys", async ({
  page,
}) => {
  const f = await fixture(page);
  await page.goto("/?page=watch");
  await page.getByLabel("Item name", { exact: false }).fill("Synthetic trade");
  await page.getByLabel("Purchase price €", { exact: false }).fill("123");
  await page.getByLabel("Purchase date", { exact: false }).fill("2026-11-15");
  await page.getByRole("button", { name: "Add trade", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Edit Synthetic trade", exact: true }),
  ).toBeVisible();
  expect(f.state.bikes.log[0]?.buy).toBe(123);
  await page
    .getByRole("button", { name: "Cost assumptions", exact: true })
    .click();
  await page.getByLabel("Boost / relist €", { exact: false }).fill("12");
  await page
    .getByRole("button", { name: "Save cost assumptions", exact: true })
    .click();
  await expect(page.getByText("Cost assumptions saved.")).toBeVisible();
  expect(f.state.bikes.costs.relist).toBe(12);
  expect(Object.keys(f.state.bikes.costs)).toHaveLength(11);
});
test("edit conflict keeps the draft and does not claim a save", async ({
  page,
}) => {
  const f = await fixture(page, { conflict: true });
  await page.goto("/?page=watch");
  await page.getByLabel("Item name", { exact: false }).fill("Draft preserved");
  await page.getByLabel("Purchase price €", { exact: false }).fill("42");
  await page.getByRole("button", { name: "Add trade", exact: true }).click();
  await expect(
    page.getByText("Your data changed in another session."),
  ).toBeVisible();
  await expect(page.getByLabel("Item name", { exact: false })).toHaveValue(
    "Draft preserved",
  );
  expect(f.state.bikes.log).toHaveLength(0);
});
test("import previews both categories and commits only after explicit conflict choice", async ({
  page,
}) => {
  const f = await fixture(page);
  await page.goto("/?page=import");
  const document = {
    version: 1,
    documents: [
      {
        kind: "bikes",
        document: {
          watch: {
            legacy: {
              n: "Legacy watch",
              u: "https://example.invalid/legacy",
              p: 100,
              t: "2026-11-01",
            },
          },
          log: [
            {
              name: "Legacy trade",
              url: "",
              buy: 50,
              bd: "2026-11-01",
              sell: null,
              sd: null,
            },
          ],
          costs: { relist: 8 },
        },
      },
      { kind: "wheels", document: { watch: {}, log: [], costs: { bpf: 3 } } },
    ],
  };
  await page.getByLabel("Choose an exported JSON file").setInputFiles({
    name: "both-categories.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify(document)),
  });
  await expect(
    page.getByText("2 category document(s)", { exact: false }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", {
      name: "Validate preview with server",
      exact: true,
    }),
  ).toBeDisabled();
  await page
    .getByLabel("When imported values conflict with saved values")
    .selectOption("replace");
  await page
    .getByRole("button", { name: "Validate preview with server", exact: true })
    .click();
  await page
    .getByRole("button", {
      name: "Confirm import and retain original source",
      exact: true,
    })
    .click();
  expect(f.state.bikes.watch.legacy?.n).toBe("Legacy watch");
  expect(f.state.bikes.costs.relist).toBe(8);
  expect(f.state.wheels.costs.bpf).toBe(3);
  expect(f.writes).toHaveLength(1);
});
test("empty and mobile keyboard journeys have no horizontal page overflow", async ({
  page,
}) => {
  await fixture(page, { empty: true });
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/");
  await expect(
    page.getByText(
      "No listings match these filters. Reset filters or switch category.",
    ),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", { name: "Skip to content" }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await page
    .getByRole("button", { name: "Bring saved data", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Bring saved data", exact: true }),
  ).toBeVisible();
});
test("loading and service failure states are explicit and retry safely", async ({
  page,
}) => {
  await fixture(page);
  let release: () => void = () => undefined;
  const waiting = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/api/v1/status", async (route) => {
    await waiting;
    await route.fallback();
  });
  await page.goto("/");
  await expect(page.getByText("Loading your private workspace…")).toBeVisible();
  release();
  await expect(
    page.getByRole("heading", { name: "1 matching listings" }),
  ).toBeVisible();
  await page.route("**/api/v1/listings*", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({
        error: {
          code: "unavailable",
          message: "Synthetic service unavailable.",
          error_id: "synthetic",
          field_errors: [],
        },
      }),
    }),
  );
  await page.reload();
  await expect(page.getByText("Synthetic service unavailable.")).toBeVisible();
  await page.unroute("**/api/v1/listings*");
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "1 matching listings" }),
  ).toBeVisible();
});
test("core journeys satisfy automated WCAG rules at desktop and mobile widths", async ({
  page,
}) => {
  await fixture(page);
  for (const width of [1280, 375]) {
    await page.setViewportSize({ width, height: 900 });
    for (const section of ["deals", "watch", "costs", "import", "status"]) {
      await page.goto("/?page=" + section);
      await expect(
        page.getByRole("heading", {
          name: "Buycycle deal finder",
          exact: true,
        }),
      ).toBeVisible();
      const result = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
        .analyze();
      expect(result.violations, section + " at " + width).toEqual([]);
    }
  }
});

test("identity switches discard old in-flight responses, private caches and drafts", async ({
  page,
}) => {
  let actor = "person-a",
    probes = 0,
    oldReplied = false;
  let releaseOld: () => void = () => undefined;
  const slowReply = new Promise<void>((resolve) => {
    releaseOld = resolve;
  });
  const saved = { "person-a": original(), "person-b": original() };
  saved["person-a"].bikes.watch.privateA = {
    n: "Person A private watch",
    u: "https://example.invalid/a",
    p: 10,
    t: "2026-11-15",
  };
  saved["person-b"].bikes.watch.privateB = {
    n: "Person B private watch",
    u: "https://example.invalid/b",
    p: 20,
    t: "2026-11-15",
  };
  const writes: {
    actor: string;
    expected: string | undefined;
    name: string | undefined;
  }[] = [];
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const json = (body: unknown, status = 200) =>
      route.fulfill({
        status,
        contentType: "application/json",
        body: JSON.stringify(body),
      });
    if (path.endsWith("/status")) {
      probes++;
      return json({
        status: "ready",
        last_success: "2026-11-15",
        stale: false,
        blocked: false,
        detail_attempts: 0,
        detail_limit: 150,
        version: "synthetic",
        identity: { subject: actor },
      });
    }
    if (path.endsWith("/listings"))
      return json({
        kind: "bikes",
        generated: "2026-11-15",
        today: "2026-11-15",
        items: [],
        active: 0,
        gone: 0,
        models: [],
        alerts: [],
        quarantined: [],
      });
    const expected = route.request().headers()["x-buycycle-expected-identity"];
    if (expected !== actor)
      return json(
        {
          error: {
            code: "forbidden",
            message: "Identity changed.",
            error_id: "synthetic",
            field_errors: [],
          },
        },
        403,
      );
    const identity = actor as keyof typeof saved;
    if (path.endsWith("/state") && route.request().method() === "GET")
      return json({ revision: 0, state: saved[identity] });
    if (path.endsWith("/state") && route.request().method() === "PUT") {
      const body = route
        .request()
        .postDataJSON() as components["schemas"]["StateWrite"];
      writes.push({ actor, expected, name: body.state.bikes?.log?.[0]?.name });
      saved[identity] = normalizeState(body.state);
      if (identity === "person-a") await slowReply;
      return json({ revision: 1, state: saved[identity] })
        .catch(() => undefined)
        .finally(() => {
          if (identity === "person-a") oldReplied = true;
        });
    }
    return json({}, 404);
  });
  await page.goto("/?page=watch");
  await expect(
    page.getByRole("link", { name: "Person A private watch", exact: true }),
  ).toBeVisible();
  await page
    .getByLabel("Item name", { exact: false })
    .fill("Person A unsaved draft");
  await page.getByLabel("Purchase price €", { exact: false }).fill("42");
  await page.getByRole("button", { name: "Add trade", exact: true }).click();
  await expect.poll(() => writes.length).toBe(1);
  const previousProbes = probes;
  actor = "person-b";
  await page.evaluate(() =>
    window.dispatchEvent(new Event("visibilitychange")),
  );
  await expect.poll(() => probes).toBeGreaterThan(previousProbes);
  await expect(
    page.getByRole("link", { name: "Person B private watch", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Person A private watch", exact: true }),
  ).toHaveCount(0);
  await expect(page.getByLabel("Item name", { exact: false })).toHaveValue("");
  releaseOld();
  await expect.poll(() => oldReplied).toBe(true);
  await expect(
    page.getByText("Person A unsaved draft", { exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("link", { name: "Person B private watch", exact: true }),
  ).toBeVisible();
  await page
    .getByLabel("Item name", { exact: false })
    .fill("Person B new trade");
  await page.getByLabel("Purchase price €", { exact: false }).fill("24");
  await page.getByRole("button", { name: "Add trade", exact: true }).click();
  await expect.poll(() => writes.length).toBe(2);
  expect(writes).toEqual([
    { actor: "person-a", expected: "person-a", name: "Person A unsaved draft" },
    { actor: "person-b", expected: "person-b", name: "Person B new trade" },
  ]);
});

test("unpriced source records are disclosed without invented zero-price deals", async ({
  page,
}) => {
  await fixture(page, { empty: true });
  await page.route("**/api/v1/listings*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        kind: "bikes",
        generated: "2026-11-15",
        today: "2026-11-15",
        items: [],
        active: 0,
        gone: 0,
        models: [],
        alerts: [],
        quarantined: [
          {
            id: "synthetic-unpriced-record",
            reason: "missing_or_invalid_price",
          },
        ],
      }),
    }),
  );
  await page.goto("/");
  await expect(
    page.getByText("1 source listing(s) excluded from estimates."),
  ).toBeVisible();
  await expect(
    page.getByText("Their asking prices are missing or invalid.", {
      exact: false,
    }),
  ).toBeVisible();
  await page.getByText("Review excluded source IDs", { exact: true }).click();
  await expect(
    page.getByText(
      "synthetic-unpriced-record — missing or invalid asking price",
    ),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Watch", exact: true }),
  ).toHaveCount(0);
});

test("a refreshed server revision invalidates the exact approved import preview", async ({
  page,
}) => {
  await page.clock.install();
  const f = await fixture(page);
  await page.goto("/?page=import");
  await page.getByLabel("Choose an exported JSON file").setInputFiles({
    name: "legacy.json",
    mimeType: "application/json",
    buffer: Buffer.from(
      JSON.stringify({
        watch: {
          legacy: {
            n: "Imported watch",
            u: "https://example.invalid/",
            p: 10,
            t: "2026-11-15",
          },
        },
        log: [],
        costs: {},
      }),
    ),
  });
  await page
    .getByRole("button", { name: "Validate preview with server", exact: true })
    .click();
  const confirm = page.getByRole("button", {
    name: "Confirm import and retain original source",
    exact: true,
  });
  await expect(confirm).toBeEnabled();
  f.advanceRevision();
  await page.clock.fastForward(31000);
  await page.evaluate(() =>
    window.dispatchEvent(new Event("visibilitychange")),
  );
  await expect(confirm).toBeDisabled();
  await expect(
    page.getByText("Saved data or import choices changed after validation.", {
      exact: false,
    }),
  ).toBeVisible();
  expect(f.writes).toHaveLength(0);
});

test("partial collection is warned about even when another category is fresh", async ({
  page,
}) => {
  await fixture(page);
  await page.route("**/api/v1/status", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "partial",
        last_success: "2026-11-15",
        stale: false,
        blocked: false,
        detail_attempts: 12,
        detail_limit: 150,
        version: "synthetic",
        identity: { subject: "synthetic-approved-person" },
      }),
    }),
  );
  await page.goto("/");
  await expect(
    page.getByText("The latest collection is partial or interrupted.", {
      exact: false,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "1 matching listings" }),
  ).toBeVisible();
});
