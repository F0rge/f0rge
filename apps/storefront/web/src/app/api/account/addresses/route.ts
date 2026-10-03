import { NextRequest, NextResponse } from "next/server";
import { CustomerAuthError, customerMedusaFetch, getCustomerContext } from "@/lib/customer-auth";
import { isSameOrigin } from "@/lib/same-origin";

export const dynamic = "force-dynamic";

type Address = Record<string, unknown> & { id: string };
const fields = ["id", "first_name", "last_name", "address_1", "address_2", "city", "province", "postal_code", "country_code", "phone", "is_default_shipping"] as const;

function privateReply<T>(body: T, status = 200): NextResponse<T> {
  const response = NextResponse.json(body, { status });
  response.headers.set("Cache-Control", "private, no-store, max-age=0");
  response.headers.set("X-Robots-Tag", "noindex, nofollow, noarchive");
  return response;
}

function publicAddress(value: unknown): Address | null {
  if (!value || typeof value !== "object" || typeof (value as { id?: unknown }).id !== "string") return null;
  const address = value as Record<string, unknown>;
  return { id: address.id as string, ...Object.fromEntries(fields.filter((field) => field !== "id").map((field) => [field, address[field]])) };
}

function addressInput(value: unknown, partial = false): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const input = value as Record<string, unknown>;
  const stringFields = ["first_name", "last_name", "address_1", "address_2", "city", "province", "postal_code", "phone"] as const;
  const output: Record<string, unknown> = { country_code: "za" };
  for (const field of stringFields) {
    if (input[field] === undefined && partial) continue;
    if (field === "address_2" || field === "phone") {
      if (input[field] !== undefined && (typeof input[field] !== "string" || input[field].length > 150)) return null;
      if (input[field] !== undefined) output[field] = (input[field] as string).trim();
      continue;
    }
    if (typeof input[field] !== "string" || !input[field].trim() || input[field].length > 250) return null;
    output[field] = input[field].trim();
  }
  if (output.postal_code !== undefined && !/^\d{4}$/.test(output.postal_code as string)) return null;
  if (partial && Object.keys(output).length === 1) return null;
  return output;
}

export async function GET(): Promise<NextResponse> {
  try {
    const context = await getCustomerContext();
    if (!context) return privateReply({ message: "Sign in to view saved addresses" }, 401);
    const { status, payload } = await customerMedusaFetch(context, "/store/customers/me/addresses");
    if (status < 200 || status >= 300) return privateReply({ message: "Saved addresses are unavailable" }, status === 401 ? 401 : 503);
    const addresses = Array.isArray(payload.addresses) ? payload.addresses.map(publicAddress).filter((address): address is Address => address !== null) : [];
    return privateReply({ addresses });
  } catch (error) {
    const status = error instanceof CustomerAuthError ? error.status : 503;
    return privateReply({ message: "Saved addresses are unavailable" }, status);
  }
}

export async function POST(request: NextRequest): Promise<NextResponse> {
  if (!isSameOrigin(request)) return privateReply({ message: "Invalid request origin" }, 403);
  try {
    const context = await getCustomerContext();
    if (!context) return privateReply({ message: "Sign in to save an address" }, 401);
    const input = addressInput(await request.json());
    if (!input) return privateReply({ message: "Enter a valid South African address" }, 400);
    const { status } = await customerMedusaFetch(context, "/store/customers/me/addresses", "POST", input);
    if (status < 200 || status >= 300) return privateReply({ message: "Address could not be saved" }, status === 401 ? 401 : 400);
    return privateReply({ ok: true }, 201);
  } catch (error) {
    const status = error instanceof CustomerAuthError ? error.status : 400;
    return privateReply({ message: "Address could not be saved" }, status);
  }
}
