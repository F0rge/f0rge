interface CustomerLogoutActions {
  resetIdentity(): void;
  signOut(options: { redirectUrl: string }): Promise<unknown>;
  refresh(): void;
}

/** Clear browser capabilities before ending the verified customer session. */
export async function logoutCustomer({ resetIdentity, signOut, refresh }: CustomerLogoutActions): Promise<void> {
  const response = await fetch("/api/account/logout", { method: "POST", cache: "no-store" });
  if (!response.ok) throw new Error("Could not end your customer session");
  resetIdentity();
  await signOut({ redirectUrl: "/account" });
  refresh();
}
