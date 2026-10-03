"use client";

import { Show, SignInButton, SignUpButton, UserButton } from "@clerk/nextjs";

export function HeaderAuth() {
  return (
    <>
      <Show when="signed-out">
        <SignInButton mode="redirect">
          <button type="button" className="header-auth">Sign in</button>
        </SignInButton>
        <SignUpButton mode="redirect">
          <button type="button" className="header-auth">Sign up</button>
        </SignUpButton>
      </Show>
      <Show when="signed-in">
        <UserButton />
      </Show>
    </>
  );
}
