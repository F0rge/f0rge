"use client";

import { Button } from "@carbon/react";
import { useClerk } from "@clerk/nextjs";

export function ClerkAccountButton() {
  const { openUserProfile } = useClerk();
  return <Button kind="tertiary" type="button" onClick={() => openUserProfile()}>Manage sign-in and security</Button>;
}
