"use client";

import {
  Button,
  InlineNotification,
  Modal,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableHeader,
  TableRow,
  TextArea,
} from "@carbon/react";
import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  canMutateOrders,
  canViewStorefrontExceptions,
  deliverStorefrontExceptionAlert,
  listStorefrontExceptions,
  getStorefrontException,
  repairStorefrontException,
  seedStorefrontExceptions,
  type StorefrontException,
  type StorefrontExceptionAudit,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

function ageLabel(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 120) return `${minutes}m`;
  return `${Math.floor(minutes / 60)}h`;
}

export default function StorefrontExceptionsPage() {
  const { user } = useAuth();
  const canView = canViewStorefrontExceptions(user);
  const canSeed = canMutateOrders(user);
  const [items, setItems] = useState<StorefrontException[]>([]);
  const [checkoutAllowed, setCheckoutAllowed] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);
  const [repairTarget, setRepairTarget] = useState<StorefrontException | null>(null);
  const [reason, setReason] = useState("");
  const [audits, setAudits] = useState<StorefrontExceptionAudit[]>([]);
  const [alertText, setAlertText] = useState("");

  const load = useCallback(async () => {
    if (!canView) return;
    setError("");
    const data = await listStorefrontExceptions();
    setItems(data.items);
    setCheckoutAllowed(data.checkout_allowed);
  }, [canView]);

  useEffect(() => {
    void load().catch((err) => setError(err instanceof Error ? err.message : "Could not load exceptions."));
  }, [load]);

  if (!canView) {
    return <p>Storefront exceptions require sales.orders or sales.refunds.</p>;
  }

  const openRepair = (row: StorefrontException) => {
    setRepairTarget(row);
    setReason(`Repair ${row.kind.replaceAll("_", " ")}`);
    setAudits(row.audits);
    void getStorefrontException(row.id)
      .then((detail) => {
        setRepairTarget(detail);
        setAudits(detail.audits);
      })
      .catch(() => undefined);
  };

  const submitRepair = async () => {
    if (!repairTarget) return;
    setLoading(true);
    setError("");
    try {
      const updated = await repairStorefrontException(repairTarget.id, {
        reason,
        idempotency_key: `ui-${crypto.randomUUID()}`,
      });
      setAudits(updated.audits);
      setNotice(`${updated.kind} ${updated.status}`);
      await load();
      setRepairTarget(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Repair was not applied.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Stack gap={5}>
      {error ? <InlineNotification kind="error" title={error} hideCloseButton /> : null}
      {notice ? <InlineNotification kind="success" title={notice} hideCloseButton /> : null}
      <h1>Storefront exceptions</h1>
      {!checkoutAllowed ? (
        <InlineNotification
          kind="warning"
          title="New checkout is blocked until the stale projection or operational outage is repaired. Paid order history remains available for recovery."
          hideCloseButton
        />
      ) : (
        <p>New checkout is allowed. Paid order recovery remains available.</p>
      )}
      <Stack gap={3} orientation="horizontal">
        {canSeed ? (
          <Button
            size="sm"
            kind="secondary"
            disabled={loading}
            onClick={() => {
              setLoading(true);
              void seedStorefrontExceptions()
                .then(async (data) => {
                  setItems(data.items);
                  setCheckoutAllowed(data.checkout_allowed);
                  setNotice("Seeded exception types are on the queue.");
                })
                .catch((err) => setError(err instanceof Error ? err.message : "Could not seed exceptions."))
                .finally(() => setLoading(false));
            }}
          >
            Seed fixtures
          </Button>
        ) : null}
        <Button
          size="sm"
          kind="tertiary"
          disabled={loading}
          onClick={() => {
            setLoading(true);
            void deliverStorefrontExceptionAlert()
              .then((alert) => {
                setAlertText(`${alert.queue_class} · ${JSON.stringify(alert.context)}`);
              })
              .catch((err) => setError(err instanceof Error ? err.message : "Could not send the test alert."))
              .finally(() => setLoading(false));
          }}
        >
          Send test alert
        </Button>
      </Stack>
      {alertText ? <p role="status">{alertText}</p> : null}
      <TableContainer title="Commerce exceptions">
        <Table>
          <TableHead>
            <TableRow>
              <TableHeader>Kind</TableHeader>
              <TableHeader>Status</TableHeader>
              <TableHeader>Age</TableHeader>
              <TableHeader>Correlation</TableHeader>
              <TableHeader>Explanation</TableHeader>
              <TableHeader>Action</TableHeader>
            </TableRow>
          </TableHead>
          <TableBody>
            {items.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6}>No commerce exceptions recorded.</TableCell>
              </TableRow>
            ) : null}
            {items.map((row) => (
              <TableRow key={row.id}>
                <TableCell>{row.kind}</TableCell>
                <TableCell>{row.status}</TableCell>
                <TableCell>{ageLabel(row.age_seconds)}</TableCell>
                <TableCell>{row.correlation_id}</TableCell>
                <TableCell>
                  {row.explanation}
                  {row.last_error ? ` (${row.last_error})` : ""}
                  {row.financial && row.amount_minor != null ? ` · ${row.amount_minor} minor` : ""}
                  {row.financial && row.amount_minor == null ? " · financial fields hidden" : ""}
                </TableCell>
                <TableCell>
                  {row.can_repair ? (
                    <Button size="sm" kind="secondary" onClick={() => openRepair(row)}>
                      Repair
                    </Button>
                  ) : (
                    row.safe_action
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
      <Modal
        open={repairTarget !== null}
        modalHeading={repairTarget ? `Repair ${repairTarget.kind}` : "Repair"}
        primaryButtonText="Apply repair"
        secondaryButtonText="Close"
        onRequestClose={() => setRepairTarget(null)}
        onRequestSubmit={() => void submitRepair()}
        primaryButtonDisabled={loading || reason.trim().length < 8}
      >
        {repairTarget ? (
          <Stack gap={4}>
            <p>{repairTarget.explanation}</p>
            <p>Safe action: {repairTarget.safe_action}</p>
            <TextArea
              id="exception-repair-reason"
              labelText="Reason"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            />
            {audits.length ? (
              <Stack gap={2}>
                <h3>Audit</h3>
                {audits.map((audit) => (
                  <p key={audit.id}>
                    {new Date(audit.created_at).toLocaleString()} · {audit.outcome} · {audit.reason}
                  </p>
                ))}
              </Stack>
            ) : null}
          </Stack>
        ) : null}
      </Modal>
    </Stack>
  );
}
