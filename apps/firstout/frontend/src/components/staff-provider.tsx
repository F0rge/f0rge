"use client";

import {
  ClerkProvider,
  OrganizationSwitcher,
  SignIn,
  useAuth as useClerkAuth,
  useClerk,
} from "@clerk/nextjs";
import { usePathname } from "next/navigation";
import { useEffect, useSyncExternalStore, type ReactNode } from "react";
import { AuthProvider } from "@/lib/auth";
import { frontendHost } from "@/lib/tenant-host";
import {
  setStaffTokenGetter,
  subscribeStaffTransport,
  staffTransportReady,
  staffTransportServerReady,
} from "@/lib/staff-fetch";

export const clerkEnabled = Boolean(
  process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY,
);
const appearance = {
  variables: {
    colorPrimary: "#0f62fe",
    borderRadius: "0",
    fontFamily: '"IBM Plex Sans", sans-serif',
  },
};
function ClerkSession({ children }: { children: ReactNode }) {
  const { isLoaded, getToken, orgId, sessionId } = useClerkAuth();
  const { signOut } = useClerk();
  const ready = useSyncExternalStore(
    subscribeStaffTransport,
    staffTransportReady,
    staffTransportServerReady,
  );
  useEffect(() => {
    if (!isLoaded) return;
    setStaffTokenGetter(() => getToken({ skipCache: true }));
    return () => setStaffTokenGetter(null);
  }, [isLoaded, getToken]);
  if (!ready || !isLoaded)
    return <AuthProvider key="legacy-loading">{children}</AuthProvider>;
  // Drop all mounted tenant UI state whenever the signed active organisation changes.
  return (
    <AuthProvider
      key={`${sessionId ?? "legacy"}:${orgId ?? "none"}`}
      onSignOut={() => signOut()}
    >
      {children}
    </AuthProvider>
  );
}
export function StaffProvider({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  if (!clerkEnabled || pathname.startsWith("/trade"))
    return <AuthProvider>{children}</AuthProvider>;
  return (
    <ClerkProvider
      appearance={appearance}
      signInUrl="/clerk-login"
      signInFallbackRedirectUrl="/"
    >
      <ClerkSession>{children}</ClerkSession>
    </ClerkProvider>
  );
}
function SignedInSwitcher() {
  const { isSignedIn } = useClerkAuth();
  if (!isSignedIn) return null;
  return (
    <OrganizationSwitcher
      hidePersonal
      afterSelectOrganizationUrl={(organisation) => {
        if (
          window.location.hostname === "localhost" ||
          window.location.hostname === "127.0.0.1"
        )
          return "/";
        const host = frontendHost(`${organisation.slug}.app.firstout.co.za`);
        return host ? `https://${host}/` : "https://app.firstout.co.za/";
      }}
      appearance={appearance}
    />
  );
}
export function StaffOrganizationSwitcher() {
  return clerkEnabled ? <SignedInSwitcher /> : null;
}
function ClerkSignInOrOrganisation() {
  const { isSignedIn } = useClerkAuth();
  return isSignedIn ? <div><p>Choose your organisation to continue.</p><SignedInSwitcher /></div> : <SignIn appearance={appearance} />;
}
export function ClerkStaffSignIn() {
  return clerkEnabled ? (
    <ClerkSignInOrOrganisation />
  ) : (
    <p>
      Organisation sign-in is not enabled. Use your existing Firstout login.
    </p>
  );
}
