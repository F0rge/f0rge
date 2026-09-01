"use client";

import {
  Column,
  Grid,
  InlineNotification,
  Loading,
  Stack,
  Tile,
} from "@carbon/react";
import { useEffect, useState } from "react";

import { ApiError, getHomeSummary, type HomeSummary } from "@/lib/api";

function formatZar(value: string, currency: string): string {
  const amount = Number(value);
  if (Number.isNaN(amount)) {
    return value;
  }
  return `${amount.toLocaleString("en-ZA", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} ${currency}`;
}

export default function HomePage() {
  const [summary, setSummary] = useState<HomeSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getHomeSummary()
      .then((data) => {
        if (!cancelled) {
          setSummary(data);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Failed to load home summary");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <Stack gap={6}>
      <div>
        <h1 className="cds--type-productive-heading-04">Home</h1>
        <p className="cds--type-body-01">
          Stock cockpit — on-order (in transit) versus on-hand (received at locations).
        </p>
      </div>

      {loading ? <Loading withOverlay={false} description="Loading summary…" /> : null}
      {error ? (
        <InlineNotification kind="error" title="Home summary" subtitle={error} hideCloseButton />
      ) : null}

      {summary ? (
        <Grid condensed fullWidth>
          <Column lg={8} md={4} sm={4}>
            <Tile className="vellano-home-tile">
              <h2 className="cds--type-productive-heading-03">On order</h2>
              <p className="cds--type-body-01 vellano-home-metric">
                {summary.on_order_qty.toLocaleString("en-ZA")} units
              </p>
              <p className="cds--type-helper-text-01">
                {formatZar(summary.on_order_value_zar, summary.home_currency)} estimated
              </p>
            </Tile>
          </Column>
          <Column lg={8} md={4} sm={4}>
            <Tile className="vellano-home-tile">
              <h2 className="cds--type-productive-heading-03">On hand</h2>
              <p className="cds--type-body-01 vellano-home-metric">
                {summary.on_hand_qty.toLocaleString("en-ZA")} units
              </p>
              <p className="cds--type-helper-text-01">
                {formatZar(summary.on_hand_value_zar, summary.home_currency)} at landed cost
              </p>
            </Tile>
          </Column>
        </Grid>
      ) : null}
    </Stack>
  );
}
