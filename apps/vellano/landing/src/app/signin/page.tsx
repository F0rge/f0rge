import type { Metadata } from "next";

import { SigninPicker } from "./signin-picker";

export const metadata: Metadata = { title: "Sign in" };

export default function SigninPage() {
  return (
    <section className="mx-auto max-w-2xl px-5 py-20 sm:px-8 sm:py-28">
      <p className="eyebrow">Sign in</p>
      <h1 className="mt-4 text-4xl leading-[1.02] sm:text-5xl">
        Where does your company <span className="display-italic">live?</span>
      </h1>
      <p className="mt-5 text-lg text-muted">Every company has its own address. Enter yours and we will take you to its login.</p>
      <SigninPicker />
    </section>
  );
}
