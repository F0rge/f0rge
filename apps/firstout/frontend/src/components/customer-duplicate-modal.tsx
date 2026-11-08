"use client";

import { Button, InlineNotification, Modal, Stack } from "@carbon/react";

import type { CustomerDuplicateMatch } from "@/lib/api";

const FIELD_LABELS: Record<CustomerDuplicateMatch["matched_fields"][number], string> = {
  name: "name",
  email: "email",
  phone: "cell",
};

export const DUPLICATE_NAME_TAKEN =
  "A customer with this name already exists. Open the existing customer instead of creating another.";

export function CustomerDuplicateModal({
  open,
  matches,
  saving,
  error,
  onCancel,
  onCreateAnyway,
  onOpenExisting,
}: {
  open: boolean;
  matches: CustomerDuplicateMatch[];
  saving: boolean;
  error: string | null;
  onCancel: () => void;
  onCreateAnyway: () => void;
  onOpenExisting: (customerId: string) => void;
}) {
  return (
    <Modal
      open={open}
      modalHeading="Possible duplicate customer"
      primaryButtonText={saving ? "Creating…" : "Create anyway"}
      secondaryButtonText="Cancel"
      onRequestClose={onCancel}
      onRequestSubmit={onCreateAnyway}
      primaryButtonDisabled={saving}
      size="sm"
    >
      <Stack gap={4}>
        <p className="cds--type-body-01">
          A customer with the same name, email, or cell already exists.
        </p>
        {error ? (
          <InlineNotification
            kind="warning"
            title="Name already on file"
            subtitle={error}
            hideCloseButton
            lowContrast
          />
        ) : null}
        {matches.length === 0 ? (
          <p className="cds--type-body-01">
            The existing record could not be listed. Search customers by name and open it from there.
          </p>
        ) : (
          matches.map((match) => (
            <div key={match.id}>
              <p className="cds--type-body-compact-01" style={{ fontWeight: 600 }}>
                {match.name}
              </p>
              <p className="cds--type-body-compact-01 firstout-break-text">
                {match.email || "No email"} · {match.phone || "No cell"}
              </p>
              <p className="firstout-muted-text" style={{ marginBottom: "0.5rem" }}>
                Matched {match.matched_fields.map((field) => FIELD_LABELS[field]).join(", ")}
              </p>
              <Button
                kind="tertiary"
                size="sm"
                type="button"
                onClick={(event) => {
                  event.preventDefault();
                  event.stopPropagation();
                  onOpenExisting(match.id);
                }}
              >
                Open existing customer
              </Button>
            </div>
          ))
        )}
      </Stack>
    </Modal>
  );
}
