import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { AuthPageLoading } from "./auth-loading";
import { WorkspaceLoader } from "./workspace-loader";

it("renders the workspace mark as inline vectors and keeps its announcement visually hidden", () => {
  const html = renderToStaticMarkup(createElement(WorkspaceLoader));
  expect(html.match(/role="status"/g)).toHaveLength(1);
  expect(html).toContain('<span class="firstout-sr-only">Loading your workspace…</span>');
  expect(html).toMatch(/<svg\b[^>]*aria-hidden="true"/);
  expect(html).toContain("<path ");
  expect(html).not.toMatch(/<(img|image|canvas)\b/);
});

describe("Clerk page loading", () => {
  it.each([
    ["/clerk-login", "Organisation sign-in", "Loading sign-in…"],
    ["/clerk-login/factor-one", "Organisation sign-in", "Loading sign-in…"],
    ["/forgot-password", "Organisation sign-in", "Loading sign-in…"],
    ["/sign-up/verify-email-address", "Create your organisation", "Loading sign-up…"],
    ["/trade/login", "Trade customer sign-in", "Loading sign-in…"],
    ["/trade/sign-up", "Trade customer sign-up", "Loading sign-up…"],
  ])("uses one non-interactive card for %s", (pathname, title, label) => {
    const html = renderToStaticMarkup(createElement(AuthPageLoading, { pathname }));
    expect(html).toContain(title);
    expect(html.match(/role="status"/g)).toHaveLength(1);
    expect(html).toContain(`aria-busy="true" aria-label="${label}"`);
    expect(html).not.toMatch(/<(input|button|form|table)\b/);
  });

  it.each(["/purchase-orders/fixture-order", "/trade/catalogue", "/trade/accept-invitation", "/sign-up-other"])(
    "leaves %s to its own fallback",
    (pathname) => {
      const html = renderToStaticMarkup(createElement(AuthPageLoading, { pathname, fallback: "Checking your session…" }));
      expect(html).toBe("Checking your session…");
    },
  );
});
