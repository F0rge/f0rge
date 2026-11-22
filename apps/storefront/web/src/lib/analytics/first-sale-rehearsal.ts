import { DASHBOARD_IDS, consentedCommerceDashboards, type MeasuredCapture } from "./dashboards";

export type AnalyticsJourneyChoice = "accepted" | "rejected" | "withdrawn";

export type AnalyticsRehearsal = {
  consented: boolean;
  rejected_stopped: boolean;
  withdrawn_stopped: boolean;
  dashboards: string[];
  personal_information_exposed: boolean;
  commerce_blocked: boolean;
};

function choiceCount(journeys: { choice: AnalyticsJourneyChoice; eventsEmitted: number }[], choice: AnalyticsJourneyChoice): number | undefined {
  const matches = journeys.filter((journey) => journey.choice === choice);
  if (matches.length === 0) return undefined;
  return matches.reduce((sum, journey) => sum + journey.eventsEmitted, 0);
}

function exposesPersonalInformation(value: unknown): boolean {
  return /@/.test(JSON.stringify(value));
}

/** Rehearses consent and the seven dashboards. Analytics never enables selling. */
export function assessAnalyticsRehearsal(input: {
  journeys: { choice: AnalyticsJourneyChoice; eventsEmitted: number }[];
  captures: MeasuredCapture[];
  commerceBlocked: boolean;
}): AnalyticsRehearsal {
  const accepted = choiceCount(input.journeys, "accepted");
  const rejected = choiceCount(input.journeys, "rejected");
  const withdrawn = choiceCount(input.journeys, "withdrawn");
  const dashboards = consentedCommerceDashboards(input.captures);
  return {
    consented: accepted !== undefined,
    rejected_stopped: rejected === 0,
    withdrawn_stopped: withdrawn === 0,
    dashboards: DASHBOARD_IDS.filter((id) => dashboards[id]),
    personal_information_exposed: exposesPersonalInformation(dashboards),
    commerce_blocked: input.commerceBlocked,
  };
}
