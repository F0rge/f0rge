"use client";

import { Button, PasswordInput, Stack, TextInput } from "@carbon/react";
import { FormEvent } from "react";

export default function LoginPage() {
  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
  }

  return (
    <Stack gap={6} as="section" style={{ maxWidth: "24rem" }}>
      <h1 className="cds--type-productive-heading-04">Log in</h1>
      <p className="cds--type-body-01">
        Placeholder only. Authentication lands in S1. The session cookie will be{" "}
        <code>vellano_session</code>.
      </p>
      <form onSubmit={onSubmit}>
        <Stack gap={5}>
          <TextInput id="email" labelText="Email" type="email" autoComplete="username" disabled />
          <PasswordInput
            id="password"
            labelText="Password"
            autoComplete="current-password"
            disabled
          />
          <Button type="submit" disabled>
            Log in
          </Button>
        </Stack>
      </form>
    </Stack>
  );
}
