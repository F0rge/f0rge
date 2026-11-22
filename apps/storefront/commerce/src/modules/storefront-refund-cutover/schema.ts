export const refundCutoverSchema = [
  `CREATE TABLE IF NOT EXISTS storefront_refund_cutover (
    id text PRIMARY KEY CHECK (id = 'medusa-refunds'),
    phase text NOT NULL CHECK (phase IN ('legacy_open', 'legacy_closed', 'upgrade_ready'))
  );`,
  `INSERT INTO storefront_refund_cutover (id, phase) VALUES ('medusa-refunds', 'legacy_open')
     ON CONFLICT (id) DO NOTHING;`,
  `CREATE TABLE IF NOT EXISTS storefront_refund_writer (
    id uuid PRIMARY KEY,
    operation text NOT NULL CHECK (operation IN ('native_refund', 'admin_cancel', 'paystack_dispatch', 'paystack_reconcile')),
    reference_id text NOT NULL,
    admitted_at timestamptz NOT NULL DEFAULT now()
  );`,
] as const;
