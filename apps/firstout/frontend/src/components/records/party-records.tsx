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
import { useEffect, useState } from "react";

import {
  listPartyAddresses,
  listPartyContacts,
  type PartyAddress,
  type PartyContact,
  type PartyKind,
} from "@/lib/api";

function addressText(row: PartyAddress): string {
  return [row.line1, row.line2, row.city, row.state, row.postcode, row.country]
    .filter(Boolean)
    .join(", ");
}

/** Every address and contact stored for a customer or supplier (imported from Cin7). */
export function PartyRecords({ kind, id }: { kind: PartyKind; id: string }) {
  const [addresses, setAddresses] = useState<PartyAddress[]>([]);
  const [contacts, setContacts] = useState<PartyContact[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void Promise.all([listPartyAddresses(kind, id), listPartyContacts(kind, id)])
      .then(([nextAddresses, nextContacts]) => {
        if (!cancelled) {
          setAddresses(nextAddresses);
          setContacts(nextContacts);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load addresses and contacts.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [kind, id]);

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
