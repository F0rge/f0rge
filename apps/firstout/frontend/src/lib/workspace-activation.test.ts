import { afterEach, describe, expect, it, vi } from "vitest";
import { activateWorkspace } from "./workspace-activation";

const origin = "https://app.firstout.co.za";

function deferred() {
  let resolve!: () => void;
  const promise = new Promise<void>((done) => { resolve = done; });
  return { promise, resolve };
}

/**
 * SDK-boundary contract harness, not a mounted Next/Clerk browser test.
 * @clerk/nextjs 7.9.8 app-router/client/ClerkProvider.js awaits the cache action
 * before setActive and refreshes the current Next route afterwards. Its
 * useInternalNavFun.js resolves router navigation on transition completion.
 * Preserve that ordering around our real activation callsite. A slow native
 * document request can lose to the old-route refresh (the observed Safari 499s).
 * The original Safari UI replay remains the end-to-end release gate.
 */
function workspaceBrowser({ changedOrg = true, fastDocument = false, decorateUrl = (url: string) => url } = {}) {
  let location = `${origin}/onboarding`;
  let pendingDocument: string | undefined;
  let commitTransition: (() => void) | undefined;
  let unloading = false;
  const navigationStarted = deferred();
  const events: string[] = [];

  const assign = (url: string) => {
    pendingDocument = new URL(url, location).href;
    events.push("document:start");
    navigationStarted.resolve();
    if (fastDocument || new URL(pendingDocument).origin !== origin) {
      location = pendingDocument;
      pendingDocument = undefined;
      unloading = true;
      events.push("document:commit");
    }
  };
  vi.stubGlobal("window", { location: { assign } });

  const clerk: Parameters<typeof activateWorkspace>[0] = {
    async setActive({ navigate }) {
      events.push("cache-action:200");
      await Promise.resolve();
      events.push("session:transitive");
      await navigate({ decorateUrl });
      if (unloading) return;
      events.push("session:publish");
      if (changedOrg) events.push("auth:remount");
      events.push(`next:refresh:${new URL(location).pathname}`);
      // The after-setActive refresh supersedes a still-pending native request.
      if (pendingDocument) {
        pendingDocument = undefined;
        events.push("document:499");
      }
    },
    navigate(url) {
      const target = new URL(url, location);
      if (target.origin !== origin) {
        assign(url);
        return Promise.resolve();
      }
      events.push("next:start");
      navigationStarted.resolve();
      return new Promise<void>((resolve) => {
        commitTransition = () => {
          location = target.href;
          events.push("next:commit");
          resolve();
        };
      });
    },
  };

  return {
    clerk,
    events,
    async open(destination = "/") {
      const activation = activateWorkspace(clerk, "org_existing", destination);
      await navigationStarted.promise;
      // Explicitly complete the SDK's awaitable Next transition, if one exists.
      commitTransition?.();
      await activation;
      if (pendingDocument) location = pendingDocument;
      events.push("staff-identity:200");
      return location;
    },
  };
}

afterEach(() => { vi.unstubAllGlobals(); });

describe("workspace activation navigation lifecycle", () => {
  it("opens Home from an active personal session despite a slow document navigation", async () => {
    const browser = workspaceBrowser();
    expect(await browser.open()).toBe(`${origin}/`);
    expect(browser.events).toEqual([
      "cache-action:200", "session:transitive", "next:start", "next:commit",
      "session:publish", "auth:remount", "next:refresh:/", "staff-identity:200",
    ]);
  });

  it("keeps the already-selected organisation control working", async () => {
    const browser = workspaceBrowser({ changedOrg: false, fastDocument: true });
    expect(await browser.open()).toBe(`${origin}/`);
    expect(browser.events).not.toContain("auth:remount");
    expect(browser.events).not.toContain("document:499");
  });

  it("preserves a decorated same-origin absolute destination including query and hash", async () => {
    const browser = workspaceBrowser({ decorateUrl: (url) => `${origin}${url}?handoff=public#branding` });
    expect(await browser.open("/organisation")).toBe(`${origin}/organisation?handoff=public#branding`);
  });

  it.each([
    "https://tenant.app.firstout.co.za/organisation?handoff=public#branding",
    "https://accounts.firstout.co.za/v1/client/sync?redirect_url=public#return",
  ])("preserves the full decorated cross-origin destination %s", async (destination) => {
    const browser = workspaceBrowser({ decorateUrl: () => destination });
    expect(await browser.open()).toBe(destination);
    expect(browser.events).toContain("document:commit");
    expect(browser.events).not.toContain("next:start");
    expect(browser.events).not.toContain("session:publish");
  });

  it("propagates an activation rejection without navigating", async () => {
    const error = new Error("Membership is disabled");
    const navigate = vi.fn();
    await expect(activateWorkspace({ setActive: () => Promise.reject(error), navigate }, "org_disabled", "/"))
      .rejects.toBe(error);
    expect(navigate).not.toHaveBeenCalled();
  });
});
