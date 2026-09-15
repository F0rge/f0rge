import { z } from "zod";

import { RESERVED_SLUGS, SLUG_PATTERN } from "./slug";

/**
 * Stand-in for the platform signup API. Nothing here persists beyond the
 * dev-server process; the real endpoints are specified in the tenancy epic.
 */
export const signupSchema = z.object({
  legalName: z.string().trim().min(2).max(200),
  tradingName: z.string().trim().max(200).optional().or(z.literal("")),
  slug: z
    .string()
    .regex(SLUG_PATTERN)
    .refine((s) => !RESERVED_SLUGS.has(s), { message: "reserved" }),
  ownerName: z.string().trim().min(2).max(120),
  email: z.string().trim().email().max(254),
  password: z.string().min(12).max(200),
  authorised: z.literal(true),
  privacyAccepted: z.literal(true),
  privacyVersion: z.string().min(1),
});

export type SignupInput = z.infer<typeof signupSchema>;

type Record = {
  id: string;
  slug: string;
  email: string;
  status: "pending_verify" | "verified" | "provisioning" | "ready";
  createdAt: number;
};

const store = new Map<string, Record>();

export function createMockSignup(input: SignupInput): Record {
  const id = crypto.randomUUID();
  const record: Record = {
    id,
    slug: input.slug,
    email: input.email,
    status: "pending_verify",
    createdAt: Date.now(),
  };
  store.set(id, record);
  return record;
}

export function slugTaken(slug: string): boolean {
  for (const r of store.values()) if (r.slug === slug) return true;
  return false;
}
