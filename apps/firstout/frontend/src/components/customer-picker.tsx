"use client";

import { ComboBox } from "@carbon/react";

import type { CustomerCrm } from "@/lib/api";
import { CUSTOMER_SEARCH_PLACEHOLDER, customerMatchesQuery } from "@/lib/customer-search";

export function customerItemLabel(item: CustomerCrm | null): string {
  return item ? item.name : "";
}

export function CustomerPicker({
  id,
  titleText = "Customer",
  customers,
  selectedId,
  onChange,
  disabled,
}: {
  id: string;
  titleText?: string;
  customers: CustomerCrm[];
  selectedId: string;
  onChange: (customerId: string) => void;
  disabled?: boolean;
}) {
  const selected = customers.find((customer) => customer.id === selectedId) ?? null;
  return (
    <ComboBox
      id={id}
      titleText={titleText}
      placeholder={CUSTOMER_SEARCH_PLACEHOLDER}
      items={customers}
      itemToString={customerItemLabel}
      selectedItem={selected}
      disabled={disabled}
      shouldFilterItem={({ item, inputValue }) => customerMatchesQuery(item, inputValue ?? "")}
      onChange={({ selectedItem }) => onChange(selectedItem?.id ?? "")}
    />
  );
}
