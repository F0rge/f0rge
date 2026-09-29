import { expect, test, type Page } from "@playwright/test";

type StudyEventLog = { type: string; milestone?: number };

declare global {
  interface Window {
    __studyEvents: StudyEventLog[];
  }
}

async function openHome(page: Page) {
  await page.addInitScript(() => {
    window.__studyEvents = [];
    window.addEventListener("storefront:study", (event) => {
      window.__studyEvents.push(
        (event as CustomEvent<StudyEventLog>).detail,
      );
    });
  });
  await page.goto("/");
  await expect(page.locator("#sola-study")).toBeAttached();
}

async function scrollStudy(page: Page, progress: number) {
  await page.evaluate((value) => {
    const section = document.querySelector<HTMLElement>("#sola-study");
    if (!section) throw new Error("Study section is missing");
    const sectionTop = window.scrollY + section.getBoundingClientRect().top;
    const scrollRange = Math.max(0, section.offsetHeight - window.innerHeight);
    window.scrollTo({ top: sectionTop + scrollRange * value, behavior: "instant" });
  }, progress);
  await page.waitForTimeout(80);
}

function trackWebglChunk(page: Page) {
  const urls: string[] = [];
  const reads: Promise<void>[] = [];
  page.on("response", (response) => {
    if (!response.url().includes("/_next/static/chunks/") || !response.url().endsWith(".js")) return;
    reads.push((async () => {
      try {
        if ((await response.body()).toString("utf8").includes("WebGLRenderer")) urls.push(response.url());
      } catch {
        // Ignore responses that were cancelled during navigation.
      }
    })());
  });
  return { urls, settle: async () => Promise.all(reads.splice(0)) };
}

test("Three.js stays out of the initial route and loads only near the study", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const webgl = trackWebglChunk(page);
  await openHome(page);
  await page.waitForLoadState("networkidle");
  await webgl.settle();

  const distanceBelowFold = await page.locator("#sola-study").evaluate((section) =>
    section.getBoundingClientRect().top - window.innerHeight,
  );
  expect(distanceBelowFold).toBeGreaterThan(200);
  expect(webgl.urls).toHaveLength(0);

  await page.locator("#sola-study").scrollIntoViewIfNeeded();
  await expect.poll(async () => {
    await webgl.settle();
    return webgl.urls.length;
  }).toBe(1);
  await expect(page.locator("#sola-study canvas")).toHaveCount(1);
});

test("constrained devices keep the fallback and never request the Three.js chunk", async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(Navigator.prototype, "deviceMemory", { configurable: true, get: () => 1 });
  });
  await page.setViewportSize({ width: 1280, height: 800 });
  const webgl = trackWebglChunk(page);
  await openHome(page);
  await page.locator("#sola-study").scrollIntoViewIfNeeded();

  await expect(page.getByRole("status")).toContainText("constrained device");
  await expect(page.locator("#sola-study canvas")).toHaveCount(0);
  await webgl.settle();
  expect(webgl.urls).toHaveLength(0);
});

test("desktop study supports scroll and manual controls without trapping page scroll", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await openHome(page);
  const section = page.locator("#sola-study");

  await section.scrollIntoViewIfNeeded();
  await expect(page.getByRole("heading", { name: "Good from every angle." })).toBeVisible();
  await expect.poll(() => page.locator(".sola-study-model canvas, .sola-study-fallback").count()).toBe(1);

  const material = page.getByRole("button", { name: "The material" });
  await material.focus();
  await page.keyboard.press("Enter");
  await expect(material).toHaveAttribute("aria-pressed", "true");

  const beforeWheel = await page.evaluate(() => window.scrollY);
  await page.mouse.move(720, 420);
  await page.mouse.wheel(0, 260);
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(beforeWheel);

  await page.getByRole("button", { name: "Pause motion" }).click();
  await expect(page.getByRole("button", { name: "Motion off" })).toHaveAttribute("aria-pressed", "true");
  await expect(section).toHaveClass(/is-static/);
});

test("semantic entry, progress and finish events are stable and deduplicated", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await openHome(page);
  await scrollStudy(page, 0.2);
  await scrollStudy(page, 1);

  await expect.poll(() => page.evaluate(() => window.__studyEvents.filter((event) => event.type === "finish").length)).toBe(1);
  await scrollStudy(page, 0.4);
  await scrollStudy(page, 1);

  const events = await page.evaluate(() => window.__studyEvents);
  expect(events.filter((event) => event.type === "entry")).toHaveLength(1);
  expect(events.filter((event) => event.type === "finish")).toHaveLength(1);
  expect(events.filter((event) => event.type === "progress").map((event) => event.milestone)).toEqual([25, 50, 75, 100]);
  expect(events.every((event) => Object.keys(event).every((key) => ["type", "studyId", "milestone"].includes(key)))).toBe(true);
});

test("reduced motion keeps a static study and keyboard-operable manual controls", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.setViewportSize({ width: 1280, height: 800 });
  await openHome(page);
  const section = page.locator("#sola-study");
  await section.scrollIntoViewIfNeeded();

  await expect(section).toHaveClass(/is-static/);
  await expect(page.getByRole("button", { name: "Motion off" })).toBeDisabled();
  await expect(page.getByRole("status")).toContainText("Reduced motion is on");
  await expect(page.locator("#sola-study canvas")).toHaveCount(0);

  const range = page.getByRole("slider", { name: "Rotate and explore the Sola chair study" });
  await range.focus();
  await page.keyboard.press("End");
  await expect(range).toHaveValue("100");
  await expect(range).toHaveAttribute("aria-valuetext", /construction/i);

  const ebony = page.getByRole("button", { name: "Ebony / ochre" });
  await ebony.focus();
  await page.keyboard.press("Enter");
  await expect(ebony).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("img", { name: /Ebony \/ ochre/ })).toBeVisible();
});

test("a forced WebGL failure leaves the editorial study and shopping available", async ({ page }) => {
  await page.addInitScript(() => {
    const original = HTMLCanvasElement.prototype.getContext;
    const failWebGL = function (
      this: HTMLCanvasElement,
      type: string,
      options?: unknown,
    ): RenderingContext | null {
      if (type === "webgl2" || type === "webgl" || type === "experimental-webgl") {
        throw new Error("Forced WebGL failure");
      }
      return Reflect.apply(original, this, options === undefined ? [type] : [type, options]) as RenderingContext | null;
    };
    HTMLCanvasElement.prototype.getContext = failWebGL as typeof HTMLCanvasElement.prototype.getContext;
  });
  await page.setViewportSize({ width: 1280, height: 800 });
  await openHome(page);
  await page.locator("#sola-study").scrollIntoViewIfNeeded();

  await expect(page.getByRole("status")).toContainText("3D could not start");
  await expect(page.getByRole("heading", { name: "Good from every angle." })).toBeVisible();
  await expect(page.locator("#sola-study canvas")).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Browse the collection" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Bag" })).toBeVisible();
});

test("mobile study preserves page navigation and has no horizontal overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await openHome(page);
  await page.locator("#sola-study").scrollIntoViewIfNeeded();

  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await expect(page.getByRole("link", { name: "Bag" })).toBeVisible();
  await expect(page.getByRole("button", { name: "The silhouette" })).toBeVisible();
  await expect(page.getByRole("slider", { name: "Rotate and explore the Sola chair study" })).toBeVisible();

  const before = await page.evaluate(() => window.scrollY);
  await page.mouse.move(195, 420);
  await page.mouse.wheel(0, 220);
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(before);

  await page.getByRole("link", { name: "Browse the collection" }).click();
  await expect(page).toHaveURL(/\/shop$/);
});
