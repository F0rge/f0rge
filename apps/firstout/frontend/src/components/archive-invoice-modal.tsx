"use client";

import { Modal, Stack } from "@carbon/react";

/** Archiving is explained before it happens; open while `invoiceNumber` is set. */
export function ArchiveInvoiceModal({
  invoiceNumber,
  onClose,
  onConfirm,
}: {
  invoiceNumber: string | null;
  onClose: () => void;
  onConfirm: () => void;
}) {
  return (
    <Modal
      open={invoiceNumber !== null}
      size="sm"
      modalHeading={`Archive ${invoiceNumber ?? "invoice"}?`}
      primaryButtonText="Archive"
      secondaryButtonText="Cancel"
      onRequestClose={onClose}
      onRequestSubmit={onConfirm}
    >
      <Stack gap={4}>
        <p>
          Archived invoices stay in the books, the VAT return and every report. Archiving only hides them
          from the default list.
        </p>
        <p className="cds--type-helper-text-01">
          You can restore an archived invoice at any time from the Archived view. Invoices can&apos;t be
          deleted. To reverse a sale, issue a credit note.
        </p>
      </Stack>
    </Modal>
  );
}
