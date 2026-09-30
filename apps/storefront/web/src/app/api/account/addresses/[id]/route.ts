import { NextRequest, NextResponse } from "next/server";
import { CustomerAuthError, customerMedusaFetch, getCustomerContext } from "@/lib/customer-auth";
import { isSameOrigin } from "@/lib/same-origin";

type Context = { params: Promise<{ id: string }> };
const validId = (id: string) => /^cuaddr_[A-Za-z0-9_-]+$/.test(id);

function privateReply<T>(body: T, status = 200): NextResponse<T> {
  const response = NextResponse.json(body, { status });
  response.headers.set("Cache-Control", "private, no-store, max-age=0");
  response.headers.set("X-Robots-Tag", "noindex, nofollow, noarchive");
  return response;
}

function addressInput(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const input = value as Record<string, unknown>;
  const output: Record<string, unknown> = { country_code: "za" };
  for (const field of ["first_name", "last_name", "address_1", "address_2", "city", "province", "postal_code", "phone"] as const) {
    if (input[field] === undefined) continue;
    if (typeof input[field] !== "string" || input[field].length > 250 || (field !== "address_2" && field !== "phone" && !input[field].trim())) return null;
    output[field] = input[field].trim();
  }
  if (output.postal_code !== undefined && !/^\d{4}$/.test(output.postal_code as string)) return null;
  if (Object.keys(output).length === 1) return null;
  return output;
}

export async function POST(request: NextRequest, { params }: Context): Promise<NextResponse> {
  if (!isSameOrigin(request)) return privateReply({ message: "Invalid request origin" }, 403);
  const { id } = await params;
  if (!validId(id)) return privateReply({ message: "Address not found" }, 404);
  try {
    const customer = await getCustomerContext();
    if (!customer) return privateReply({ message: "Sign in to edit saved addresses" }, 401);
    const input = addressInput(await request.json());
    if (!input) return privateReply({ message: "Enter a valid South African address" }, 400);
    const { status } = await customerMedusaFetch(customer, `/store/customers/me/addresses/${encodeURIComponent(id)}`, "POST", input);
    if (status < 200 || status >= 300) return privateReply({ message: "Address could not be updated" }, status === 401 ? 401 : 404);
    return privateReply({ ok: true });
  } catch (error) {
    const status = error instanceof CustomerAuthError ? error.status : 400;
    return privateReply({ message: "Address could not be updated" }, status);
  }
}

export async function DELETE(request: NextRequest, { params }: Context): Promise<NextResponse> {
  if (!isSameOrigin(request)) return privateReply({ message: "Invalid request origin" }, 403);
  const { id } = await params;
  if (!validId(id)) return privateReply({ message: "Address not found" }, 404);
  try {
    const customer = await getCustomerContext();
    if (!customer) return privateReply({ message: "Sign in to remove saved addresses" }, 401);
    const { status } = await customerMedusaFetch(customer, `/store/customers/me/addresses/${encodeURIComponent(id)}`, "DELETE");
    if (status < 200 || status >= 300) return privateReply({ message: "Address could not be removed" }, status === 401 ? 401 : 404);
    return privateReply({ ok: true });
  } catch (error) {
    const status = error instanceof CustomerAuthError ? error.status : 503;
    return privateReply({ message: "Address could not be removed" }, status);
  }
}
