"use client";

import {
  Button,
  InlineNotification,
  Select,
  SelectItem,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableHeader,
  TableRow,
} from "@carbon/react";
import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  STOCKTAKE_STATUS_LABELS,
  canReceive,
  getStocktake,
  isActiveLocation,
  listLocations,
  listStocktakes,
  startStocktake,
  type Location,
  type Stocktake,
  type StocktakeLine,
  type StocktakeSummary,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

import { StocktakeSession } from "./stocktake-session";

function formatDateTime(iso: string | null): string {
  if (!iso) {
    return "—";
  }
  return new Date(iso).toLocaleString("en-ZA");
}

export default function StocktakesPage() {
  const { user } = useAuth();
  const canMutate = canReceive(user?.role);
  const [stocktakes, setStocktakes] = useState<StocktakeSummary[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [active, setActive] = useState<Stocktake | null>(null);
  const [locationId, setLocationId] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [summaryData, locationData] = await Promise.all([
        listStocktakes(),
        listLocations(),
      ]);
      setStocktakes(summaryData);
      setLocations(locationData.filter(isActiveLocation));
      const activeSummary = summaryData.find((entry) => entry.status === "in_progress");
      if (activeSummary) {
        setActive(await getStocktake(activeSummary.id));
      } else {
        setActive(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load stocktakes.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user) {
      void load();
    }
  }, [user, load]);

  const history = stocktakes
    .filter((entry) => entry.status !== "in_progress")
    .slice()
    .sort((a, b) => b.started_at.localeCompare(a.started_at));

  async function handleStart() {
    if (!canMutate || !locationId) {
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await startStocktake({ location_id: locationId });
      setLocationId("");
      await load();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError(err.message);
        await load();
      } else {
        setError(err instanceof Error ? err.message : "Failed to start stocktake.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  function handleLinePatched(line: StocktakeLine) {
    setActive((current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        lines: current.lines.map((entry) => (entry.id === line.id ? line : entry)),
      };
    });
  }

  return (
    <Stack gap={6}>
      {error ? (
        <InlineNotification
          kind="error"
          title="Error"
          subtitle={error}
          onCloseButtonClick={() => setError(null)}
          lowContrast
        />
      ) : null}

      {loading ? (
        <p className="cds--type-body-01">Loading stocktakes…</p>
      ) : active ? (
        <StocktakeSession
          key={active.id}
          stocktake={active}
          canMutate={canMutate}
          onLinePatched={handleLinePatched}
          onFinished={load}
          onError={setError}
        />
      ) : (
        <Stack gap={6}>
          <div>
            <h1 className="cds--type-productive-heading-04">Stocktakes</h1>
            <p className="cds--type-body-01">
              Count on-hand stock for one location. Completing posts quantity adjustments.
            </p>
          </div>

          {!canMutate ? (
            <InlineNotification
              kind="warning"
              title="Permission required"
              subtitle="Only owner and warehouse roles can start or complete a stocktake."
              hideCloseButton
              lowContrast
            />
          ) : (
            <Stack gap={5}>
              <Select
                id="stocktake-location"
                labelText="Location"
                value={locationId}
                onChange={(event) => setLocationId(event.target.value)}
                helperText={
                  locations.length === 0 ? "No active locations available" : undefined
                }
              >
                <SelectItem value="" text="Select a location" />
                {locations.map((entry) => (
                  <SelectItem key={entry.id} value={entry.id} text={entry.name} />
                ))}
              </Select>
              <Button
                disabled={submitting || !locationId}
                onClick={() => void handleStart()}
              >
                {submitting ? "Starting…" : "Start stocktake"}
              </Button>
            </Stack>
          )}
        </Stack>
      )}

      {!loading && !active && history.length === 0 ? (
        <InlineNotification
          kind="info"
          title="No stocktakes"
          subtitle="No completed or cancelled stocktakes yet."
          hideCloseButton
          lowContrast
        />
      ) : null}

      {!loading && history.length > 0 ? (
        <TableContainer title="History" description="Completed and cancelled stocktakes">
          <Table>
            <TableHead>
              <TableRow>
                <TableHeader>Location</TableHeader>
                <TableHeader>Status</TableHeader>
                <TableHeader>Started</TableHeader>
                <TableHeader>Completed</TableHeader>
              </TableRow>
            </TableHead>
            <TableBody>
              {history.map((entry) => (
                <TableRow key={entry.id}>
                  <TableCell>{entry.location_name}</TableCell>
                  <TableCell>{STOCKTAKE_STATUS_LABELS[entry.status]}</TableCell>
                  <TableCell>{formatDateTime(entry.started_at)}</TableCell>
                  <TableCell>{formatDateTime(entry.completed_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      ) : null}
    </Stack>
  );
}
