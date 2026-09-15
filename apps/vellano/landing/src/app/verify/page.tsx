import type { Metadata } from "next";
import { Suspense } from "react";

import { VerifyFlow } from "./verify-flow";

export const metadata: Metadata = { title: "Setting up your workspace" };

export default function VerifyPage() {
  return (
    <section className="mx-auto max-w-2xl px-5 py-20 sm:px-8 sm:py-28">
      <Suspense fallback={null}>
        <VerifyFlow />
      </Suspense>
    </section>
  );
}
