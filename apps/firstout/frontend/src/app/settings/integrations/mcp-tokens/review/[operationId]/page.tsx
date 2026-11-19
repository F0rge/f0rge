"use client";

import {
  Button, Checkbox, InlineNotification, Stack, Table, TableBody, TableCell, TableHead,
  TableHeader, TableRow,
} from "@carbon/react";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { AdminPageHeader } from "@/components/administration";
import { PageLoading } from "@/components/page-loading";
import { ApiError, apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { workspaceIdentity } from "@/lib/record-workspace";
import { adminError } from "@/lib/staff-administration";

type Review = {
  action: "transfers_dispatch" | "transfers_receive";
  token_name: string;
  status: "awaiting_confirmation" | "completed" | "expired";
  expires_at?: string;
  preview: {
    transfer_number: string;
    from_location: string;
    to_location: string;
    lines: {
      line_id: string;
      sku: string;
      name: string;
      from_bin: string | null;
      to_bin: string | null;
      quantity: string;
      counted_quantity?: string;
    }[];
  };
};

function TransferReview({ operationId, business }: { operationId: string; business: string }) {
  const [review, setReview] = useState<Review | null>(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [counted, setCounted] = useState(false);
  const [stale, setStale] = useState(false);
  const path = "/mcp-operations/" + encodeURIComponent(operationId);

  useEffect(() => {
    const controller = new AbortController();
    apiFetch<Review>(path, { cache: "no-store", signal: controller.signal })
      .then((review) => { if (!controller.signal.aborted) setReview(review); })
      .catch((error: unknown) => { if (!controller.signal.aborted) setError(adminError(error, "Please try again.")); });
    return () => controller.abort();
  }, [path]);

  useEffect(() => {
    if (review?.status !== "awaiting_confirmation" || !review.expires_at) return;
    const remaining = Date.parse(review.expires_at) - Date.now();
    const timer = window.setTimeout(() => {
      setReview((current) => current?.status === "awaiting_confirmation"
        ? { ...current, status: "expired" } : current);
    }, Math.max(0, remaining));
    return () => window.clearTimeout(timer);
  }, [review]);

  async function confirm() {
    setSaving(true);
    setError("");
    try {
      setReview(await apiFetch<Review>(path + "/confirm", { method: "POST" }));
    } catch (error) {
      if (error instanceof ApiError) {
        if (error.status === 410) {
          setReview((current) => current && { ...current, status: "expired" });
          return;
        }
        if (error.status === 409) setStale(true);
        if ([401, 403, 404].includes(error.status)) setReview(null);
      }
      setError(adminError(error, "Please try again."));
    } finally {
      setSaving(false);
    }
  }

  if (!review && !error) return <PageLoading label="Loading transfer for review…" />;
  const receive = review?.action === "transfers_receive";
  return (
    <Stack gap={6}>
      <AdminPageHeader title="Review transfer" description={business} />
      {error && <InlineNotification kind="error" title="Could not complete the request" subtitle={error} hideCloseButton />}
      {review && (
        <Stack gap={5}>
          <h2>{review.preview.transfer_number}</h2>
          <p>{review.preview.from_location} → {review.preview.to_location}</p>
          <p>Requested with your “{review.token_name}” token.</p>
          <Table aria-label="Transfer items" tabIndex={0}>
            <TableHead>
              <TableRow>
                <TableHeader>Item</TableHeader><TableHeader>From bin</TableHeader><TableHeader>To bin</TableHeader>
                <TableHeader>Transfer quantity</TableHeader>{receive && <TableHeader>Counted quantity</TableHeader>}
              </TableRow>
            </TableHead>
            <TableBody>
              {review.preview.lines.map((line) => (
                <TableRow key={line.line_id}>
                  <TableCell>{line.name} ({line.sku})</TableCell><TableCell>{line.from_bin ?? "—"}</TableCell>
                  <TableCell>{line.to_bin ?? "—"}</TableCell><TableCell>{line.quantity}</TableCell>
                  {receive && <TableCell>{line.counted_quantity}</TableCell>}
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {review.status === "awaiting_confirmation" && !stale && (
            <Stack gap={4}>
              <p>
                {receive
                  ? "Confirming adds the counted stock to " + review.preview.to_location + "."
                  : "Confirming deducts the listed stock from " + review.preview.from_location + " and marks the transfer in transit."}
                {" "}This request expires at {new Date(review.expires_at!).toLocaleTimeString()}.
              </p>
              {receive && (
                <Checkbox id="counted-items" labelText="I checked the items and quantities received."
                  checked={counted} onChange={(_, { checked }) => setCounted(checked)} />
              )}
              <div>
                <Button disabled={saving || (receive && !counted)} onClick={() => void confirm()}>
                  {saving ? "Confirming…" : receive ? "Confirm receipt" : "Confirm dispatch"}
                </Button>
              </div>
            </Stack>
          )}
          {review.status === "completed" && (
            <InlineNotification kind="success" title={receive ? "Transfer received" : "Transfer dispatched"} hideCloseButton />
          )}
          {review.status === "expired" && (
            <InlineNotification kind="warning" title="This request expired" subtitle="Ask your assistant to request a new review." hideCloseButton />
          )}
        </Stack>
      )}
    </Stack>
  );
}

export default function McpReviewPage() {
  const { user, loading } = useAuth();
  const { operationId } = useParams<{ operationId: string }>();
  if (loading) return <PageLoading label="Loading your account…" />;
  if (!user) return <InlineNotification kind="error" title="Sign in to review this transfer" hideCloseButton />;
  return <TransferReview key={workspaceIdentity(user) + operationId} operationId={operationId} business={user.team.name} />;
}
