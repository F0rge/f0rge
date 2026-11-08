"use client";

import {
  ClerkProvider,
  OrganizationSwitcher,
  SignIn,
  SignUp,
  useAuth as useClerkAuth,
  useClerk,
} from "@clerk/nextjs";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Loading } from "@carbon/react";
import { createContext, useContext, useEffect, useSyncExternalStore, type ReactNode } from "react";
import { AuthProvider } from "@/lib/auth";
import { organisationDestination } from "@/lib/organisations";
import {
  setStaffTokenGetter,
  subscribeStaffTransport,
  staffTransportReady,
  staffTransportServerReady,
} from "@/lib/staff-fetch";

export const clerkEnabled = Boolean(
  process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY,
);
const StaffSessionContext = createContext({ signedIn: false });
export const useStaffSession = () => useContext(StaffSessionContext);

const appearance = {
  variables: {
    colorPrimary: "#0f62fe",
    borderRadius: "0",
    fontFamily: '"IBM Plex Sans", sans-serif',
  },
};
function ClerkSession({ children }: { children: ReactNode }) {
  // Pending choose-organisation sessions can call onboarding, never business APIs.
  const { isLoaded, isSignedIn, getToken, orgId, sessionId } = useClerkAuth({ treatPendingAsSignedOut: false });
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
    return <div className="firstout-shell-loading"><Loading withOverlay={false} description="Loading sign-in…" /></div>;
  // Drop all mounted tenant UI state whenever the signed active organisation changes.
  return (
    <StaffSessionContext.Provider value={{ signedIn: Boolean(isSignedIn) }}>
      <AuthProvider
        key={`${sessionId ?? "legacy"}:${orgId ?? "none"}`}
        onSignOut={() => signOut()}
      >
        {children}
      </AuthProvider>
    </StaffSessionContext.Provider>
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
      signUpUrl="/sign-up"
      signInFallbackRedirectUrl="/onboarding"
      signUpFallbackRedirectUrl="/onboarding"
      taskUrls={{ "choose-organization": "/onboarding" }}
    >
      <ClerkSession>{children}</ClerkSession>
    </ClerkProvider>
  );
}
function SignedInSwitcher() {
  const { isSignedIn } = useClerkAuth();
  if (!isSignedIn) return null;
  return (
    <>
      <OrganizationSwitcher
        hidePersonal
        organizationProfileMode="navigation"
        organizationProfileUrl="/organisation"
        createOrganizationMode="navigation"
        createOrganizationUrl="/onboarding"
        afterSelectOrganizationUrl={(organisation) => organisation.slug
          ? organisationDestination(organisation.slug, window.location.host)
          : "/onboarding"}
        appearance={appearance}
      />
      <Link className="cds--link firstout-header-create" href="/onboarding">Create organisation</Link>
    </>
  );
}
export function StaffOrganizationSwitcher() {
  return clerkEnabled ? <SignedInSwitcher /> : null;
}
function ClerkSignInOrOrganisation() {
  const { isSignedIn } = useClerkAuth({ treatPendingAsSignedOut: false });
  return isSignedIn ? <ContinueToOnboarding /> : <SignIn routing="path" path="/clerk-login" appearance={appearance} forceRedirectUrl="/onboarding" signUpUrl="/sign-up" />;
}

function ContinueToOnboarding() {
  const router = useRouter();
  useEffect(() => { router.replace("/onboarding"); }, [router]);
  return <Link className="cds--link" href="/onboarding">Continue to your organisations</Link>;
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

function ClerkSignUpOrOrganisation() {
  const { isSignedIn } = useClerkAuth({ treatPendingAsSignedOut: false });
  return isSignedIn ? <ContinueToOnboarding /> : <SignUp routing="path" path="/sign-up" appearance={appearance} forceRedirectUrl="/onboarding" signInUrl="/clerk-login" />;
}

export function ClerkStaffSignUp() {
  return clerkEnabled ? <ClerkSignUpOrOrganisation /> : <p>Organisation signup is not enabled yet. Use your existing Firstout login.</p>;
}
