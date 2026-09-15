import { NextResponse } from "next/server";

import { createMockSignup, signupSchema, slugTaken } from "@/lib/mock-signup";

export async function POST(request: Request) {
  const body = await request.json().catch(() => null);
  const parsed = signupSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { detail: "invalid", issues: parsed.error.issues.map((i) => ({ path: i.path.join("."), message: i.message })) },
      { status: 422 },
    );
  }
  if (slugTaken(parsed.data.slug)) {
    return NextResponse.json({ detail: "slug_taken" }, { status: 409 });
  }
  const record = createMockSignup(parsed.data);
  return NextResponse.json({ signup_id: record.id, status: record.status }, { status: 202 });
}
