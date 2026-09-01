"use client";

import {
  Button,
  DataTable,
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
  TextInput,
} from "@carbon/react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import {
  canMutateBooks,
  createContact,
  listContacts,
  type Contact,
  type CreateContactPayload,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

const TABLE_HEADERS = [
  { key: "kind", header: "Kind" },
  { key: "name", header: "Name" },
  { key: "currency", header: "Currency" },
] as const;

type ContactRow = {
  id: string;
  kind: string;
  name: string;
  currency: string;
};

const emptyCreateForm: CreateContactPayload = {
  name: "",
  email: "",
  vat_number: "",
  billing_address: "",
};

export default function ContactsPage() {
  const { user } = useAuth();
  const canMutate = canMutateBooks(user?.role);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState<CreateContactPayload>(emptyCreateForm);
  const [saving, setSaving] = useState(false);

  const loadContacts = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listContacts();
      setContacts(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load contacts.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user) {
      void loadContacts();
    }
  }, [user, loadContacts]);

  const rows: ContactRow[] = contacts.map((entry) => ({
    id: entry.id,
    kind: entry.kind === "customer" ? "Customer" : "Supplier",
    name: entry.name,
    currency: entry.currency ?? "—",
  }));

  async function handleCreate() {
    setSaving(true);
    setError(null);
    try {
      const payload: CreateContactPayload = {
        name: createForm.name.trim(),
      };
      const email = createForm.email?.trim();
      const vatNumber = createForm.vat_number?.trim();
      const billingAddress = createForm.billing_address?.trim();
      if (email) {
        payload.email = email;
      }
      if (vatNumber) {
        payload.vat_number = vatNumber;
      }
      if (billingAddress) {
        payload.billing_address = billingAddress;
      }
      await createContact(payload);
      setCreateOpen(false);
      setCreateForm(emptyCreateForm);
      await loadContacts();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create customer.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Stack gap={6}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h1 className="cds--type-productive-heading-04">Contacts</h1>
          <p className="cds--type-body-01">
            Customers for invoicing.{" "}
            <Link href="/suppliers">Suppliers are added under Suppliers.</Link>
          </p>
        </div>
        {canMutate ? <Button onClick={() => setCreateOpen(true)}>Add customer</Button> : null}
      </div>

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
        <p className="cds--type-body-01">Loading contacts…</p>
      ) : contacts.length === 0 ? (
        <InlineNotification
          kind="info"
          title="No contacts"
          subtitle="No customers or suppliers in the books contact list yet."
          hideCloseButton
          lowContrast
        />
      ) : (
        <DataTable rows={rows} headers={[...TABLE_HEADERS]}>
          {({ rows: tableRows, headers, getTableProps, getHeaderProps, getRowProps }) => (
            <TableContainer title="Contacts" description="Customers and suppliers in books">
              <Table {...getTableProps()}>
                <TableHead>
                  <TableRow>
                    {headers.map((header) => (
                      <TableHeader {...getHeaderProps({ header })} key={header.key}>
                        {header.header}
                      </TableHeader>
                    ))}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {tableRows.map((row) => (
                    <TableRow {...getRowProps({ row })} key={row.id}>
                      {row.cells.map((cell) => (
                        <TableCell key={cell.id}>{cell.value}</TableCell>
                      ))}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </DataTable>
      )}

      <Modal
        open={createOpen}
        modalHeading="Add customer"
        primaryButtonText={saving ? "Adding…" : "Add"}
        secondaryButtonText="Cancel"
        primaryButtonDisabled={saving || !createForm.name.trim()}
        onRequestClose={() => setCreateOpen(false)}
        onRequestSubmit={() => void handleCreate()}
      >
        <Stack gap={5}>
          <TextInput
            id="create-contact-name"
            labelText="Name"
            value={createForm.name}
            onChange={(event) =>
              setCreateForm((form) => ({ ...form, name: event.target.value }))
            }
            required
          />
          <TextInput
            id="create-contact-email"
            labelText="Email"
            value={createForm.email ?? ""}
            onChange={(event) =>
              setCreateForm((form) => ({ ...form, email: event.target.value }))
            }
          />
          <TextInput
            id="create-contact-vat"
            labelText="VAT number"
            value={createForm.vat_number ?? ""}
            onChange={(event) =>
              setCreateForm((form) => ({ ...form, vat_number: event.target.value }))
            }
          />
          <TextArea
            id="create-contact-address"
            labelText="Billing address"
            value={createForm.billing_address ?? ""}
            onChange={(event) =>
              setCreateForm((form) => ({ ...form, billing_address: event.target.value }))
            }
            rows={3}
          />
        </Stack>
      </Modal>
    </Stack>
  );
}
