"use client";

import {
  InlineNotification,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableHeader,
  TableRow,
  Tag,
} from "@carbon/react";
import { useQuery } from "@tanstack/react-query";

import { LoadingRegion, LoadingTableRows } from "@/components/page-loading";
import {
  ApiError,
  listPartyAddresses,
  listPartyContacts,
  type PartyAddress,
  type PartyKind,
} from "@/lib/api";

function addressText(row: PartyAddress): string {
  return [row.line1, row.line2, row.city, row.state, row.postcode, row.country]
    .filter(Boolean)
    .join(", ");
}

export function PartyRecordsLoading({ announce = true }: { announce?: boolean }) {
  return (
    <LoadingRegion label="Loading addresses and contacts…" announce={announce}>
      <Stack gap={5}>
        <TableContainer title="Addresses">
          <LoadingTableRows columns={["Type", "Address"]} rows={2} size="sm" />
        </TableContainer>
        <TableContainer title="Contacts">
          <LoadingTableRows columns={["Name", "Job title", "Phone", "Mobile", "Email"]} rows={2} size="sm" />
        </TableContainer>
      </Stack>
    </LoadingRegion>
  );
}

/** Every address and contact stored for a customer or supplier (imported from Cin7). */
export function PartyRecords({ kind, id }: { kind: PartyKind; id: string }) {
  const records = useQuery({
    queryKey: ["party-records", { kind, id }],
    queryFn: async () => {
      const [addresses, contacts] = await Promise.all([listPartyAddresses(kind, id), listPartyContacts(kind, id)]);
      return { addresses, contacts };
    },
  });
  const addresses = records.data?.addresses ?? [];
  const contacts = records.data?.contacts ?? [];
  // An API without these routes (older deploy) hides the section instead of erroring.
  const unavailable = records.error instanceof ApiError && records.error.status === 404;
  const error = records.error && !unavailable
    ? records.error.message || "Failed to load addresses and contacts."
    : null;
  const loading = records.isPending;

  if (unavailable) {
    return null;
  }
  if (loading) return <PartyRecordsLoading />;

  return (
    <Stack gap={5}>
      {error ? (
        <InlineNotification kind="error" title="Error" subtitle={error} lowContrast hideCloseButton />
      ) : null}
      <TableContainer title="Addresses" description={`${addresses.length} stored`}>
        <Table size="sm">
          <TableHead>
            <TableRow>
              <TableHeader>Type</TableHeader>
              <TableHeader>Address</TableHeader>
            </TableRow>
          </TableHead>
          <TableBody>
            {addresses.length === 0 ? (
              <TableRow>
                <TableCell colSpan={2}>No addresses.</TableCell>
              </TableRow>
            ) : (
              addresses.map((row) => (
                <TableRow key={row.id}>
                  <TableCell>
                    {row.address_type ?? "—"}{" "}
                    {row.is_default ? (
                      <Tag size="sm" type="blue">
                        Default
                      </Tag>
                    ) : null}
                  </TableCell>
                  <TableCell>{addressText(row) || "—"}</TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>
      <TableContainer title="Contacts" description={`${contacts.length} stored`}>
        <Table size="sm">
          <TableHead>
            <TableRow>
              <TableHeader>Name</TableHeader>
              <TableHeader>Job title</TableHeader>
              <TableHeader>Phone</TableHeader>
              <TableHeader>Mobile</TableHeader>
              <TableHeader>Email</TableHeader>
            </TableRow>
          </TableHead>
          <TableBody>
            {contacts.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5}>No contacts.</TableCell>
              </TableRow>
            ) : (
              contacts.map((row) => (
                <TableRow key={row.id}>
                  <TableCell>
                    {row.name ?? "—"}{" "}
                    {row.is_default ? (
                      <Tag size="sm" type="blue">
                        Default
                      </Tag>
                    ) : null}
                  </TableCell>
                  <TableCell>{row.job_title ?? "—"}</TableCell>
                  <TableCell>{row.phone ?? "—"}</TableCell>
                  <TableCell>{row.mobile ?? "—"}</TableCell>
                  <TableCell>{row.email ?? "—"}</TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </Stack>
  );
}
