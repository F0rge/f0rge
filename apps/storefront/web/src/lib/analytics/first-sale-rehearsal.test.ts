import { describe, expect, it } from "vitest";
import { DASHBOARD_IDS } from "./dashboards";
import { assessAnalyticsRehearsal } from "./first-sale-rehearsal";

describe("assessAnalyticsRehearsal", () => {
  it("records consented, rejected, and withdrawn journeys and keeps sensitive routes out of replay", () => {
    const result = assessAnalyticsRehearsal({
      journeys: [
        { choice: "accepted", eventsEmitted: 2 },
        { choice: "rejected", eventsEmitted: 0 },
        { choice: "withdrawn", eventsEmitted: 0 },
      ],
      captures: [
        {
          event: "storefront_page_viewed",
          distinct_id: "anon_1",
          properties: {
            page_key: "home",
            anonymous_id: "anon_1",
            utm_source: "ada@example.com",
            email: "ada@example.com",
          },
        },
      ],
      commerceBlocked: false,
    });

    expect(result).toEqual({
      consented: true,
      rejected_stopped: true,
      withdrawn_stopped: true,
      replay_excludes_sensitive_routes: true,
      dashboards: [...DASHBOARD_IDS],
      personal_information_exposed: false,
      commerce_blocked: false,
    });
  });

  it("keeps the analytics gate open when a withdrawn visitor still emits events or commerce is blocked", () => {
    const withdrawn = assessAnalyticsRehearsal({
      journeys: [
        { choice: "accepted", eventsEmitted: 1 },
        { choice: "rejected", eventsEmitted: 0 },
        { choice: "withdrawn", eventsEmitted: 3 },
      ],
      captures: [],
      commerceBlocked: false,
    });
    const blocked = assessAnalyticsRehearsal({
      journeys: [
        { choice: "accepted", eventsEmitted: 1 },
        { choice: "rejected", eventsEmitted: 0 },
        { choice: "withdrawn", eventsEmitted: 0 },
      ],
      captures: [],
      commerceBlocked: true,
    });

    expect(withdrawn.withdrawn_stopped).toBe(false);
    expect(blocked.commerce_blocked).toBe(true);
  });
});
