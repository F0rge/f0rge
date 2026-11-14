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
import { InlineNotification, Loading } from "@carbon/react";
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
  const pathname = usePathname();
  const trade = pathname.startsWith("/trade");
  // Only active sessions enter the app; personal sessions can choose a workspace.
  const { isLoaded, isSignedIn, getToken, orgId, sessionId } = useClerkAuth();
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
        key={`${sessionId ?? "none"}:${orgId ?? "none"}:${trade ? "trade" : "staff"}`}
        loadIdentity={!trade}
        onSignOut={(redirectUrl) => signOut({ redirectUrl: redirectUrl ?? (trade ? "/trade/login" : "/clerk-login") })}
      >
        {children}
      </AuthProvider>
    </StaffSessionContext.Provider>
  );
}
export function StaffProvider({ children }: { children: ReactNode }) {
  const trade = usePathname().startsWith("/trade");
  if (!clerkEnabled) return <main className="firstout-login-page"><InlineNotification kind="error" title="Sign-in unavailable" subtitle="Clerk sign-in has not been configured. Contact the administrator." hideCloseButton /></main>;
  return (
    <ClerkProvider
      appearance={appearance}
      signInUrl={trade ? "/trade/login" : "/clerk-login"}
      signUpUrl={trade ? "/trade/sign-up" : "/sign-up"}
      signInFallbackRedirectUrl={trade ? "/trade/catalogue" : "/onboarding"}
      signUpFallbackRedirectUrl={trade ? "/trade/catalogue" : "/onboarding"}
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
        organizationProfileMode="navigation"
        organizationProfileUrl="/organisation"
        createOrganizationMode="navigation"
        createOrganizationUrl="/onboarding"
        afterSelectOrganizationUrl={(organisation) => organisation.slug
          ? organisationDestination(organisation.slug, window.location.host)
          : "/onboarding"}
        appearance={{
          ...appearance,
          elements: {
            rootBox: "firstout-organisation-switcher",
            organizationSwitcherTrigger: "firstout-organisation-switcher-trigger",
            organizationPreviewMainIdentifier: "firstout-organisation-switcher-name",
          },
        }}
      />
  );
}
export function StaffOrganizationSwitcher() {
  return clerkEnabled ? <SignedInSwitcher /> : null;
}
function ClerkSignInOrOrganisation() {
  // Clerk must finish pending MFA/password-reset/organisation tasks before continuing.
  const { isSignedIn } = useClerkAuth();
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
      Sign-in is unavailable. Contact the administrator.
    </p>
  );
}

function ClerkSignUpOrOrganisation() {
  const { isSignedIn } = useClerkAuth();
  return isSignedIn ? <ContinueToOnboarding /> : <SignUp routing="path" path="/sign-up" appearance={appearance} forceRedirectUrl="/onboarding" signInUrl="/clerk-login" />;
}

export function ClerkStaffSignUp() {
  return clerkEnabled ? <ClerkSignUpOrOrganisation /> : <p>Sign-up is unavailable. Contact the administrator.</p>;
}
