import { SkeletonPlaceholder, SkeletonText } from "@carbon/react";
import Link from "next/link";
import type { ReactNode } from "react";
import { LoadingRegion } from "@/components/page-loading";
import styles from "./auth-loading.module.css";

type AuthCardKind = "staff-login" | "staff-sign-up" | "trade-login" | "trade-sign-up";

const TITLES: Record<AuthCardKind, string> = {
  "staff-login": "Organisation sign-in",
  "staff-sign-up": "Create your organisation",
  "trade-login": "Trade customer sign-in",
  "trade-sign-up": "Trade customer sign-up",
};

export function ClerkAuthCard({ kind, children }: { kind: AuthCardKind; children: ReactNode }) {
  return (
    <main className="firstout-login-page">
      <section className="firstout-login-card firstout-auth-card">
        <h1 className="cds--type-productive-heading-04">{TITLES[kind]}</h1>
        {kind === "staff-sign-up" && (
          <p className="cds--type-body-01">Start free with up to five staff members. Verify your email, then set up your business.</p>
        )}
        {(kind === "trade-login" || kind === "trade-sign-up") && (
          <p className="cds--type-body-01">Use the email on your trade invitation. Access is approved separately by the business.</p>
        )}
        {children}
        {kind === "staff-sign-up" && (
          <Link href="/clerk-login" className="cds--link">Already have an account? Sign in</Link>
        )}
      </section>
    </main>
  );
}

export function ClerkWidgetLoading({
  mode = "login",
  expandedStep = false,
}: {
  mode?: "login" | "sign-up";
  expandedStep?: boolean;
}) {
  return (
    <LoadingRegion
      className={`${styles.widget} firstout-loading-motion`}
      label={mode === "login" ? "Loading sign-in…" : "Loading sign-up…"}
    >
      <div aria-hidden="true">
        <div className={styles.body}>
          <div className={styles.intro}>
            <SkeletonText heading width="9rem" />
            <SkeletonText width="12rem" />
            {expandedStep && <SkeletonText width="8rem" />}
          </div>
          <div className={styles.field}>
            <SkeletonText width="5rem" />
            <SkeletonPlaceholder className={styles.input} />
          </div>
          <SkeletonPlaceholder className={styles.action} />
          <div className={styles.alternative}><SkeletonText width="7rem" /></div>
        </div>
        <div className={styles.footer}>Secured by <strong>Clerk</strong></div>
      </div>
    </LoadingRegion>
  );
}

export function ClerkSignInLoading({ pathname }: { pathname: string }) {
  const [, root, step, tradeStep] = pathname.split("/");
  const expandedStep = (root === "trade" ? tradeStep : step) === "factor-one";
  return <ClerkWidgetLoading expandedStep={expandedStep} />;
}

export function AuthPageLoading({ pathname, fallback = null }: { pathname: string; fallback?: ReactNode }) {
  const [, root, step] = pathname.split("/");
  let kind: AuthCardKind;
  if (root === "trade" && step === "login") {
    kind = "trade-login";
  } else if (root === "trade" && step === "sign-up") {
    kind = "trade-sign-up";
  } else if (root === "sign-up") {
    kind = "staff-sign-up";
  } else if (root === "clerk-login" || root === "login" || root === "forgot-password" || root === "reset-password") {
    kind = "staff-login";
  } else {
    return fallback;
  }

  return (
    <ClerkAuthCard kind={kind}>
      {kind === "staff-login" || kind === "trade-login"
        ? <ClerkSignInLoading pathname={pathname} />
        : <ClerkWidgetLoading mode="sign-up" />}
    </ClerkAuthCard>
  );
}
