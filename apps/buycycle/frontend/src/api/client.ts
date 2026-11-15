import createClient from "openapi-fetch";
import { ApiFailure, apiFailure } from "@f0rge/primer/api";
import type { paths, components } from "./generated";
import { normalizeState, type BrowserState } from "../state";
import type { IdentitySession } from "./session";
export type { ApiFailure };
export type StateResponse = Omit<
  components["schemas"]["StateResponse"],
  "state"
> & { state: BrowserState };
export type Listing = components["schemas"]["Listing"];
export type StatusResponse = components["schemas"]["StatusResponse"];
export type ListingsResponse = components["schemas"]["ListingsResponse"];
export type ModelMarket = components["schemas"]["ModelMarket"];
export type Alert = components["schemas"]["Alert"];
const client = createClient<paths>({
  baseUrl:
    typeof location === "undefined" ? "http://localhost" : location.origin,
  credentials: "same-origin",
});
function result<T>(data: T | undefined, error: unknown, response: Response): T {
  if (!response.ok) throw apiFailure(response.status, error);
  if (data === undefined)
    throw new ApiFailure(
      502,
      "invalid_response",
      "The server returned an incomplete response.",
    );
  return data;
}
export const api = {
  async listings(
    kind: "bikes" | "wheels",
    session: IdentitySession,
    signal?: AbortSignal,
  ) {
    const { data, error, response } = await client.GET("/api/v1/listings", {
      params: { query: { kind } },
      ...session.request(signal),
    });
    session.assertActive();
    return result(data, error, response);
  },
  async status(signal?: AbortSignal) {
    const { data, error, response } = await client.GET("/api/v1/status", {
      signal,
    });
    return result(data, error, response);
  },
  async privateStatus(session: IdentitySession, signal?: AbortSignal) {
    const { data, error, response } = await client.GET(
      "/api/v1/status",
      session.request(signal),
    );
    session.assertActive();
    const status = result(data, error, response);
    if (status.identity.subject !== session.subject)
      throw new ApiFailure(
        403,
        "identity_changed",
        "The signed-in identity changed. Reload the private workspace.",
      );
    return status;
  },
  async state(
    session: IdentitySession,
    signal?: AbortSignal,
  ): Promise<StateResponse> {
    const { data, error, response } = await client.GET(
      "/api/v1/state",
      session.request(signal),
    );
    session.assertActive();
    const saved = result(data, error, response);
    return { ...saved, state: normalizeState(saved.state) };
  },
  async save(
    body: components["schemas"]["StateWrite"],
    session: IdentitySession,
  ): Promise<StateResponse> {
    const { data, error, response } = await client.PUT("/api/v1/state", {
      body,
      params: { header: { "X-Buycycle-Expected-Identity": session.subject } },
      ...session.request(),
    });
    session.assertActive();
    const saved = result(data, error, response);
    return { ...saved, state: normalizeState(saved.state) };
  },
  async preview(
    body: components["schemas"]["ImportWrite"],
    session: IdentitySession,
  ) {
    const { data, error, response } = await client.POST(
      "/api/v1/state/import-preview",
      {
        body,
        params: { header: { "X-Buycycle-Expected-Identity": session.subject } },
        ...session.request(),
      },
    );
    session.assertActive();
    return result(data, error, response);
  },
  async import(
    body: components["schemas"]["ImportWrite"],
    session: IdentitySession,
  ): Promise<StateResponse> {
    const { data, error, response } = await client.POST(
      "/api/v1/state/import",
      {
        body,
        params: { header: { "X-Buycycle-Expected-Identity": session.subject } },
        ...session.request(),
      },
    );
    session.assertActive();
    const saved = result(data, error, response);
    return { ...saved, state: normalizeState(saved.state) };
  },
};
