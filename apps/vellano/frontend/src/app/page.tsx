"use client";

import { InlineNotification, Stack } from "@carbon/react";
import { useEffect, useState } from "react";

type HealthState = "loading" | "ok" | "down";

export default function HomePage() {
  const [health, setHealth] = useState<HealthState>("loading");

  useEffect(() => {
    let cancelled = false;
    fetch("/api/v1/health")
      .then((response) => {
        if (!cancelled) {
          setHealth(response.ok ? "ok" : "down");
        }
      })
      .catch(() => {
        if (!cancelled) {
          setHealth("down");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <Stack gap={6}>
      <h1 className="cds--type-productive-heading-04">Home</h1>
      <p className="cds--type-body-01">
        Vellano back office. S4 purchase-order flow: raise PO, on water, land costs, receive into
        locations. Ledger and till land in later slices.
      </p>
      {health === "loading" ? (
        <InlineNotification kind="info" title="API" subtitle="Checking /api/v1/health…" hideCloseButton />
      ) : null}
      {health === "ok" ? (
        <InlineNotification kind="success" title="API" subtitle="Health check returned 200." hideCloseButton />
      ) : null}
      {health === "down" ? (
        <InlineNotification
          kind="warning"
          title="API"
          subtitle="Health check did not succeed. Start the API on :8003."
          hideCloseButton
        />
      ) : null}
    </Stack>
  );
}
