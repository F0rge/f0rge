import type { Metadata } from "next";
import { Suspense } from "react";

import { VerifyFlow } from "./verify-flow";

export const metadata: Metadata = { title: "Setting up your workspace" };

export default function VerifyPage() {
  return (
    <section className="mx-auto w-full max-w-2xl px-4 py-16 sm:px-8 sm:py-24">
      <Suspense fallback={null}>
        <VerifyFlow />
      </Suspense>
    </section>
  );
}
