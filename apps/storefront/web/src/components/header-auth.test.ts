import { beforeEach, describe, expect, it, vi } from "vitest";
import { createElement, type ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { NextRequest } from "next/server";

const state = vi.hoisted(() => ({
  events: [] as string[], cookies: new Set<string>(),
  click: undefined as (() => unknown) | undefined,
  signOut: vi.fn(async () => { state.events.push("clerk"); }),
  refresh: vi.fn(() => { state.events.push("refresh"); }),
  resetIdentity: vi.fn(() => { state.events.push("identity"); }),
}));

interface ButtonProps { children?: ReactNode; onClick?: () => unknown; disabled?: boolean; type?: "button" | "submit"; className?: string }
function button(props: ButtonProps) {
  if (props.children === "Sign out") state.click = props.onClick;
  return createElement("button", props, props.children);
}

vi.mock("@clerk/nextjs", () => ({
  Show: ({ when, children }: { when: string; children: ReactNode }) => when === "signed-in" ? children : null,
  SignInButton: ({ children }: { children: ReactNode }) => children,
  SignUpButton: ({ children }: { children: ReactNode }) => children,
  UserButton: () => button({ children: "Sign out", onClick: () => state.signOut() }),
  useClerk: () => ({ signOut: state.signOut }),
  useUser: () => ({ user: null, isLoaded: false }),
}));
vi.mock("@f0rge/ui", () => ({ Button: (props: ButtonProps) => button(props) }));
vi.mock("@f0rge/ui/forms", () => ({ TextInput: () => null }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: state.refresh }) }));
vi.mock("@/components/analytics/analytics-provider", () => ({ useStorefrontAnalytics: () => ({ resetIdentity: state.resetIdentity, identify: vi.fn() }) }));
vi.mock("@/app/account/order-history", () => ({ OrderHistory: () => null }));
vi.mock("@/lib/bag-server", () => ({
  cartCookie: "collector_cart", orderAccessCookie: "collector_order_access", emailOrderAccessCookie: "collector_email_order_access",
}));

import { HeaderAuth } from "./header-auth";
import { AccountClient } from "@/app/account/account-client";
import { POST as logoutBff } from "@/app/api/account/logout/route";

function renderControl(surface: "header" | "account") {
  renderToStaticMarkup(surface === "header" ? createElement(HeaderAuth) : createElement(AccountClient, {
    customer: { email: "customer@example.com", first_name: "A", last_name: "Customer" },
  }));
  expect(state.click).toBeTypeOf("function");
}

describe("customer sign-out controls", () => {
  beforeEach(() => {
    vi.clearAllMocks(); state.events.length = 0; state.click = undefined;
    state.cookies = new Set(["collector_cart", "collector_order_access", "collector_email_order_access"]);
  });

  it.each(["header", "account"] as const)("clears capabilities and analytics identity before %s sign-out", async (surface) => {
    const fetcher = vi.fn(async (path: string, init?: RequestInit) => {
      expect(path).toBe("/api/account/logout");
      expect(init).toMatchObject({ method: "POST", cache: "no-store" });
      state.events.push("cleanup");
      const response = await logoutBff(new NextRequest("http://localhost:3004/api/account/logout", { method: "POST" }));
      for (const cookie of response.cookies.getAll()) {
        expect(cookie.maxAge).toBe(0);
        state.cookies.delete(cookie.name);
      }
      return response;
    });
    vi.stubGlobal("fetch", fetcher);
    renderControl(surface);
    await state.click!();
    await vi.waitFor(() => expect(state.refresh).toHaveBeenCalledOnce());
    expect(state.events).toEqual(["cleanup", "identity", "clerk", "refresh"]);
    expect(state.cookies.size).toBe(0);
    expect(state.signOut).toHaveBeenCalledWith({ redirectUrl: "/account" });
    expect(fetcher).toHaveBeenCalledOnce();
  });

  it.each(["header", "account"] as const)("keeps %s signed in when protected-cookie cleanup fails", async (surface) => {
    const fetcher = vi.fn(async () => Response.json({ message: "Unavailable" }, { status: 503 }));
    vi.stubGlobal("fetch", fetcher);
    renderControl(surface);
    await state.click!();
    await vi.waitFor(() => expect(fetcher).toHaveBeenCalledOnce());
    expect(state.signOut).not.toHaveBeenCalled();
    expect(state.resetIdentity).not.toHaveBeenCalled();
    expect(state.refresh).not.toHaveBeenCalled();
    expect(state.cookies.size).toBe(3);
  });
});
