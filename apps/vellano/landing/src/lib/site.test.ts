import { describe, expect, it } from "vitest";

import { loginHrefFromWorkspaceOrigin, slugFromHostInput, workspaceLoginUrl, workspaceUrl } from "./site";

describe("workspace URLs", () => {
  it("builds a host preview without a scheme", () => {
    expect(workspaceUrl("acme")).toBe("acme.localhost");
    expect(workspaceUrl("")).toBe("yourcompany.localhost");
  });

  it("sends localhost workspaces to port 3003 over http", () => {
    expect(workspaceLoginUrl("acme")).toBe("http://acme.localhost:3003/login");
  });

  it("appends /login when the API returns an origin", () => {
    expect(loginHrefFromWorkspaceOrigin("http://acme.localhost:3003")).toBe(
      "http://acme.localhost:3003/login",
    );
    expect(loginHrefFromWorkspaceOrigin("http://acme.localhost:3003/")).toBe(
      "http://acme.localhost:3003/login",
    );
    expect(loginHrefFromWorkspaceOrigin("http://acme.localhost:3003/login")).toBe(
      "http://acme.localhost:3003/login",
    );
  });
});

describe("slugFromHostInput", () => {
  it("strips scheme, port, path, and the tenant base suffix", () => {
    expect(slugFromHostInput("Acme")).toBe("acme");
    expect(slugFromHostInput("https://acme.localhost:3003/login")).toBe("acme");
    expect(slugFromHostInput("acme.localhost")).toBe("acme");
  });
});
