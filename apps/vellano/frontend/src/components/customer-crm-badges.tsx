import { Tag } from "@carbon/react";

import { type CustomerCrm } from "@/lib/api";
import { formatIsoDate, laybyActiveBadgeLabel, overdueBadgeLabel } from "@/lib/customer-crm";

export function CustomerCrmBadges({ customer }: { customer: CustomerCrm }) {
  return (
    <div className="vellano-customer-badges">
      {customer.on_hold ? (
        <Tag type="red" size="sm">
          On hold
        </Tag>
      ) : null}
      {customer.overdue_invoices_count > 0 ? (
        <Tag type="red" size="sm">
          Overdue {overdueBadgeLabel(customer)}
        </Tag>
      ) : null}
      {customer.active_laybys_count > 0 ? (
        <Tag type="teal" size="sm">
          Layby active {laybyActiveBadgeLabel(customer)}
        </Tag>
      ) : null}
      <Tag type="gray" size="sm">
        Last purchase {formatIsoDate(customer.last_purchase_date)}
      </Tag>
    </div>
  );
}
