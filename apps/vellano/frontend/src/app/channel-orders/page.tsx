"use client";

import {
  Button,
  InlineNotification,
  Pagination,
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
  Tag,
  TextInput,
} from "@carbon/react";
import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  CHANNEL_ORDER_STATUS_LABELS,
  cancelChannelOrder,
  canManageChannels,
  canMutateDeliveries,
  fulfillChannelOrder,
  listChannelOrders,
  processChannelOrder,
  type ChannelOrder,
  type ChannelOrderStatus,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

const STATUS_FILTERS: { value: "" | ChannelOrderStatus; label: string }[] = [
  { value: "", label: "All statuses" },
  { value: "needs_mapping", label: "Needs mapping" },
  { value: "received", label: "Received" },
  { value: "posted", label: "Posted" },
  { value: "failed", label: "Failed" },
  { value: "cancelled", label: "Cancelled" },
  { value: "refunded", label: "Refunded" },
];

function statusKind(status: ChannelOrderStatus): "red" | "green" | "blue" | "gray" | "purple" {
  if (status === "posted") {
    return "green";
  }
  if (status === "needs_mapping" || status === "failed") {
    return "red";
  }
  if (status === "refunded" || status === "cancelled") {
    return "gray";
  }
  return "blue";
}

export default function ChannelOrdersPage() {
  const { user } = useAuth();
  const canFulfill = canMutateDeliveries(user);
  const canManage = canManageChannels(user);
  const [items, setItems] = useState<ChannelOrder[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<"" | ChannelOrderStatus>("");
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await listChannelOrders({
        limit: pageSize,
        offset: (page - 1) * pageSize,
        q: q.trim() || undefined,
        status: status || undefined,
      });
      setItems(result.items);
      setTotal(result.total);
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "Failed to load channel orders");
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, q, status]);

  useEffect(() => {
    if (user) {
      void load();
    }
  }, [user, load]);

  async function run(orderId: string, action: () => Promise<ChannelOrder>) {
    setBusyId(orderId);
    setError(null);
    try {
      await action();
      await load();
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "Channel order action failed");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <Stack gap={5}>
      <div>
        <h1 className="cds--type-productive-heading-04">Channel orders</h1>
        <p className="cds--type-body-01">
          Shopify, email, and manual channel sales. Mapping inbox is status Needs mapping.
        </p>
      </div>
      {error ? (
        <InlineNotification kind="error" title="Channel orders" subtitle={error} hideCloseButton />
      ) : null}
      <div className="vellano-catalogue-actions">
        <TextInput
          id="channel-orders-q"
          labelText="Search"
          hideLabel
          placeholder="Order id or email"
          value={q}
          onChange={(event) => {
            setPage(1);
            setQ(event.target.value);
          }}
        />
        <Select
          id="channel-orders-status"
          labelText="Status"
          hideLabel
          value={status}
          onChange={(event) => {
            setPage(1);
            setStatus(event.target.value as "" | ChannelOrderStatus);
          }}
        >
          {STATUS_FILTERS.map((option) => (
            <SelectItem key={option.value || "all"} value={option.value} text={option.label} />
          ))}
        </Select>
      </div>
      <TableContainer>
        <Table>
          <TableHead>
            <TableRow>
              <TableHeader>External id</TableHeader>
              <TableHeader>Channel</TableHeader>
              <TableHeader>Status</TableHeader>
              <TableHeader>Email</TableHeader>
              <TableHeader>Invoice</TableHeader>
              <TableHeader>Error</TableHeader>
              <TableHeader>Actions</TableHeader>
            </TableRow>
          </TableHead>
          <TableBody>
            {items.map((row) => (
              <TableRow key={row.id}>
                <TableCell>{row.external_order_id}</TableCell>
                <TableCell>{row.channel}</TableCell>
                <TableCell>
                  <Tag type={statusKind(row.status)}>{CHANNEL_ORDER_STATUS_LABELS[row.status]}</Tag>
                </TableCell>
                <TableCell>{row.email ?? "—"}</TableCell>
                <TableCell>{row.invoice_number ?? "—"}</TableCell>
                <TableCell>{row.error_message ?? "—"}</TableCell>
                <TableCell>
                  {row.status === "needs_mapping" || row.status === "received" || row.status === "failed" ? (
                    <Button
                      kind="ghost"
                      size="sm"
                      disabled={busyId === row.id}
                      onClick={() => void run(row.id, () => processChannelOrder(row.id))}
                    >
                      Process
                    </Button>
                  ) : null}
                  {row.status === "posted" && canFulfill ? (
                    <Button
                      kind="ghost"
                      size="sm"
                      disabled={busyId === row.id}
                      onClick={() => void run(row.id, () => fulfillChannelOrder(row.id))}
                    >
                      Fulfill
                    </Button>
                  ) : null}
                  {row.status === "posted" && canManage ? (
                    <Button
                      kind="danger--ghost"
                      size="sm"
                      disabled={busyId === row.id}
                      onClick={() => void run(row.id, () => cancelChannelOrder(row.id))}
                    >
                      Cancel
                    </Button>
                  ) : null}
                </TableCell>
              </TableRow>
            ))}
            {!loading && items.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7}>No channel orders.</TableCell>
              </TableRow>
            ) : null}
          </TableBody>
        </Table>
      </TableContainer>
      <Pagination
        page={page}
        pageSize={pageSize}
        pageSizes={[10, 25, 50]}
        totalItems={total}
        onChange={({ page: nextPage, pageSize: nextSize }) => {
          setPage(nextPage);
          setPageSize(nextSize);
        }}
      />
    </Stack>
  );
}
