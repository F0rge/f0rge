import type { CustomerCrm } from "@/lib/api";

/** Mirrors apps/firstout/backend/app/services/customer_match.py */
export const CUSTOMER_SEARCH_PLACEHOLDER = "Search by name, email or cell";

const NON_DIGIT = /\D+/g;

export function nationalPhoneDigits(raw: string | null | undefined): string {
  if (!raw || !raw.trim()) {
    return "";
  }
  let digits = raw.replace(NON_DIGIT, "");
  if (!digits) {
    return "";
  }
  if (digits.startsWith("0027")) {
    digits = digits.slice(4);
  } else if (digits.startsWith("27") && digits.length >= 11) {
    digits = digits.slice(2);
  }
  if (digits.startsWith("0")) {
    digits = digits.slice(1);
  }
  return digits;
}

export function phoneSearchNeedles(raw: string): string[] {
  const digits = raw.replace(NON_DIGIT, "");
  if (digits.length < 3) {
    return [];
  }
  const needles: string[] = [];
  const add = (value: string) => {
    if (value.length >= 2 && !needles.includes(value)) {
      needles.push(value);
    }
  };
  add(nationalPhoneDigits(raw));
  if (digits.startsWith("0027")) {
    add(nationalPhoneDigits(digits.slice(4)));
  } else if (digits.startsWith("27")) {
    let rest = digits.slice(2);
    if (rest.startsWith("0")) {
      rest = rest.slice(1);
    }
    add(rest);
  } else if (digits.startsWith("0")) {
    add(digits.slice(1));
  }
  return needles;
}

export function customerMatchesQuery(
  customer: Pick<CustomerCrm, "name" | "email" | "phone">,
  query: string,
): boolean {
  const trimmed = query.trim();
  if (!trimmed) {
    return true;
  }
  const folded = trimmed.toLowerCase();
  if (customer.name.toLowerCase().includes(folded)) {
    return true;
  }
  if ((customer.email ?? "").toLowerCase().includes(folded)) {
    return true;
  }
  const stored = nationalPhoneDigits(customer.phone);
  if (!stored) {
    return false;
  }
  return phoneSearchNeedles(trimmed).some((needle) => stored.includes(needle));
}
