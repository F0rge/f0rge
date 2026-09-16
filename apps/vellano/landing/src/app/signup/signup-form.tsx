"use client";

import { ArrowRight, Check, Eye, EyeOff, Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useId, useMemo, useState } from "react";

import { Button } from "@/components/button";
import { site, tenantBaseDomain, workspaceUrl } from "@/lib/site";
import { createSignup, fetchSlugAvailability } from "@/lib/platform";
import { checkSlug, passwordStrength, slugify } from "@/lib/slug";

type Field = "legalName" | "tradingName" | "slug" | "ownerName" | "email" | "password";

const emailPattern = /^[^\s@]+@[^\s@]+\.[a-z]{2,}$/i;

export function SignupForm() {
  const router = useRouter();
  const [values, setValues] = useState<Record<Field, string>>({
    legalName: "",
    tradingName: "",
    slug: "",
    ownerName: "",
    email: "",
    password: "",
  });
  const [slugTouched, setSlugTouched] = useState(false);
  const [authorised, setAuthorised] = useState(false);
  const [privacy, setPrivacy] = useState(false);
  const [showPw, setShowPw] = useState(false);
  const [touched, setTouched] = useState<Partial<Record<Field, boolean>>>({});
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  const [taken, setTaken] = useState(false);

  const companyLabel = values.tradingName || values.legalName || "your company";
  const slugCheck = checkSlug(values.slug);
  const strength = passwordStrength(values.password);

  useEffect(() => {
    if (slugTouched) return;
    const source = values.tradingName || values.legalName;
    setValues((v) => ({ ...v, slug: slugify(source) }));
  }, [values.tradingName, values.legalName, slugTouched]);

  useEffect(() => {
    if (!slugCheck.ok) {
      setTaken(false);
      return;
    }
    const handle = window.setTimeout(() => {
      void fetchSlugAvailability(values.slug).then((result) => {
        setTaken(!result.available && result.reason === "taken");
      });
    }, 300);
    return () => window.clearTimeout(handle);
  }, [values.slug, slugCheck.ok]);

  const errors = useMemo(() => {
    const e: Partial<Record<Field, string>> = {};
    if (values.legalName.trim().length < 2) e.legalName = "Enter the registered company name.";
    if (!slugCheck.ok) {
      e.slug =
        slugCheck.reason === "reserved"
          ? "That address is reserved. Try another."
          : slugCheck.reason === "short"
            ? "At least 3 characters."
            : "Lowercase letters, numbers, and dashes only.";
    }
    if (taken) e.slug = "That workspace address is taken. Try another.";
    if (values.ownerName.trim().length < 2) e.ownerName = "Enter your full name.";
    if (!emailPattern.test(values.email)) e.email = "Enter a work email address.";
    if (values.password.length < 12) e.password = "Use at least 12 characters.";
    return e;
  }, [values, slugCheck, taken]);

  const valid = Object.keys(errors).length === 0 && authorised && privacy;

  function update(field: Field, value: string) {
    setValues((v) => ({ ...v, [field]: value }));
    setServerError(null);
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!valid || submitting) return;
    setSubmitting(true);
    setServerError(null);
    try {
      const res = await createSignup({
          legal_name: values.legalName,
          trading_name: values.tradingName || null,
          slug: values.slug,
          owner_name: values.ownerName,
          email: values.email,
          password: values.password,
          authorised,
          privacy_accepted: privacy,
          privacy_version: site.privacyVersion,
        });
      const data = (await res.json().catch(() => null)) as {
        signup_id?: string;
        status?: string;
        detail?: unknown;
      } | null;
      const detail = typeof data?.detail === "string" ? data.detail.toLowerCase() : JSON.stringify(data?.detail ?? "");
      if (res.status === 409 || detail.includes("taken")) {
        setServerError("That workspace address was just taken. Pick another.");
        setSlugTouched(true);
        return;
      }
      if (!res.ok || !data?.signup_id) {
        setServerError("We could not start your signup. Check the form and try again.");
        return;
      }
      if (data.status === "provisioning" || data.status === "ready") {
        router.push(`/verify?id=${encodeURIComponent(data.signup_id)}`);
        return;
      }
      router.push(`/signup/check-email?email=${encodeURIComponent(values.email)}&id=${data.signup_id}`);
    } catch {
      setServerError("Network error. Try again in a moment.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mt-12 grid gap-8 lg:grid-cols-[1.1fr_0.9fr] lg:gap-14">
      <form onSubmit={onSubmit} noValidate className="border border-line bg-white p-6 sm:p-8">
        <fieldset className="space-y-6">
          <legend className="text-2xl font-light">The company</legend>
          <TextField
            label="Legal company name"
            hint="As registered with CIPC, e.g. Acme (Pty) Ltd"
            value={values.legalName}
            onChange={(v) => update("legalName", v)}
            onBlur={() => setTouched((t) => ({ ...t, legalName: true }))}
            error={touched.legalName ? errors.legalName : undefined}
            autoComplete="organization"
            required
          />
          <TextField
            label="Trading name"
            hint="Optional. What customers see on receipts and the header."
            value={values.tradingName}
            onChange={(v) => update("tradingName", v)}
          />
          <SlugField
            value={values.slug}
            onChange={(v) => {
              setSlugTouched(true);
              update("slug", v.toLowerCase());
            }}
            error={values.slug ? errors.slug : undefined}
            ok={slugCheck.ok}
          />
        </fieldset>

        <fieldset className="mt-10 space-y-6">
          <legend className="text-2xl font-light">You</legend>
          <TextField
            label="Your full name"
            value={values.ownerName}
            onChange={(v) => update("ownerName", v)}
            onBlur={() => setTouched((t) => ({ ...t, ownerName: true }))}
            error={touched.ownerName ? errors.ownerName : undefined}
            autoComplete="name"
            required
          />
          <TextField
            label="Work email"
            hint="We send the verification link here. This becomes the owner login."
            type="email"
            value={values.email}
            onChange={(v) => update("email", v)}
            onBlur={() => setTouched((t) => ({ ...t, email: true }))}
            error={touched.email ? errors.email : undefined}
            autoComplete="email"
            required
          />
          <PasswordField
            value={values.password}
            show={showPw}
            onToggle={() => setShowPw((s) => !s)}
            onChange={(v) => update("password", v)}
            onBlur={() => setTouched((t) => ({ ...t, password: true }))}
            error={touched.password ? errors.password : undefined}
            strength={strength}
          />
        </fieldset>

        <fieldset className="mt-10 space-y-4">
          <legend className="text-2xl font-light">Two confirmations</legend>
          <CheckField checked={authorised} onChange={setAuthorised}>
            I am authorised to register <strong className="font-medium text-ink">{companyLabel}</strong> and act on its behalf.
          </CheckField>
          <CheckField checked={privacy} onChange={setPrivacy}>
            I have read the{" "}
            <Link href="/legal/privacy" className="text-interactive underline-offset-2 hover:underline">
              privacy notice
            </Link>
            . I understand the software is operated for my company by {site.operatorName} and hosted outside South Africa.
          </CheckField>
        </fieldset>

        {serverError ? (
          <p role="alert" className="mt-6 border border-danger bg-[#fff1f1] px-4 py-3 text-sm text-danger">
            {serverError}
          </p>
        ) : null}

        <div className="mt-8 flex flex-wrap items-center gap-4">
          <Button type="submit" disabled={!valid || submitting} className="px-6 py-3.5 text-base">
            {submitting ? <Loader2 size={16} className="animate-spin" /> : null}
            Create {companyLabel === "your company" ? "your company" : companyLabel}
            <ArrowRight size={16} />
          </Button>
          <span className="text-sm text-muted">Next: verify your email. Nothing is created before that.</span>
        </div>
      </form>

      <Preview slug={values.slug} company={companyLabel} owner={values.ownerName} legal={values.legalName} />
    </div>
  );
}

function Preview({ slug, company, owner, legal }: { slug: string; company: string; owner: string; legal: string }) {
  const perks = ["Own database, own address", "Owner login for " + (owner || "you"), "Catalogue, till, quotes, sales orders", "Warehouse on the phone", "Books with a VAT201 draft", "Trade portal and Nia"];
  return (
    <aside className="lg:sticky lg:top-24 lg:self-start">
      <div className="border border-line bg-paper-2 p-6 sm:p-8">
        <p className="eyebrow">Workspace preview</p>
        <div className="mt-4 overflow-hidden border border-line bg-white">
          <div className="flex items-center border-b border-line bg-ink px-3 py-2">
            <span className="truncate font-mono text-[11px] text-white/80">
              https://{workspaceUrl(slug)}
            </span>
          </div>
          <div className="p-5">
            <div className="text-2xl font-light leading-tight">{company === "your company" ? "Your company" : company}</div>
            <div className="mt-1 text-xs text-muted">{legal || "Legal name appears on invoices"}</div>
            <div className="mt-5 grid grid-cols-3 gap-2">
              {["Open orders", "Stock", "Cash"].map((k) => (
                <div key={k} className="border border-line bg-paper-2 p-2.5">
                  <div className="text-[10px] text-muted">{k}</div>
                  <div className="mt-1 h-4 w-10 bg-paper-3" />
                </div>
              ))}
            </div>
          </div>
        </div>
        <ul className="mt-6 space-y-2.5 text-sm">
          {perks.map((p) => (
            <li key={p} className="flex items-start gap-2.5">
              <Check size={16} className="mt-0.5 shrink-0 text-moss" aria-hidden />
              <span>{p}</span>
            </li>
          ))}
        </ul>
        <p className="mt-6 text-xs leading-relaxed text-muted">
          Empty on arrival. Your data never sits in another company&rsquo;s database, and nobody else&rsquo;s sits in yours.
        </p>
      </div>
    </aside>
  );
}

const inputClass =
  "mt-2 h-10 w-full border-0 border-b border-field bg-paper-2 px-4 text-sm text-ink outline-none placeholder:text-muted focus:border-b-2 focus:border-interactive aria-[invalid=true]:border-danger";

function TextField({
  label,
  hint,
  error,
  value,
  onChange,
  onBlur,
  type = "text",
  autoComplete,
  required,
}: {
  label: string;
  hint?: string;
  error?: string;
  value: string;
  onChange: (v: string) => void;
  onBlur?: () => void;
  type?: string;
  autoComplete?: string;
  required?: boolean;
}) {
  const id = useId();
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium">
        {label} {required ? <span className="text-danger">*</span> : <span className="text-muted">(optional)</span>}
      </label>
      <input
        id={id}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onBlur={onBlur}
        autoComplete={autoComplete}
        aria-invalid={Boolean(error)}
        aria-describedby={`${id}-hint ${error ? `${id}-err` : ""}`}
        className={inputClass}
      />
      {hint ? (
        <p id={`${id}-hint`} className="mt-1.5 text-xs text-muted">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={`${id}-err`} className="mt-1.5 text-xs text-danger">
          {error}
        </p>
      ) : null}
    </div>
  );
}

function SlugField({ value, onChange, error, ok }: { value: string; onChange: (v: string) => void; error?: string; ok: boolean }) {
  const id = useId();
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium">
        Workspace address <span className="text-danger">*</span>
      </label>
      <div
        className={`mt-2 flex h-10 items-stretch bg-paper-2 focus-within:shadow-[inset_0_-2px_0_0_#0f62fe] ${error ? "shadow-[inset_0_-2px_0_0_#da1e28]" : ""}`}
      >
        <span className="hidden items-center border-r border-line px-3 font-mono text-sm text-muted sm:flex">https://</span>
        <input
          id={id}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          spellCheck={false}
          autoCapitalize="none"
          aria-invalid={Boolean(error)}
          aria-describedby={`${id}-hint ${error ? `${id}-err` : ""}`}
          className="min-w-0 flex-1 bg-transparent px-4 font-mono text-sm outline-none"
          placeholder="acme"
        />
        <span className="flex items-center border-l border-line px-3 font-mono text-sm text-muted">.{tenantBaseDomain}</span>
      </div>
      <p id={`${id}-hint`} className="mt-1.5 flex items-center gap-1.5 text-xs text-muted">
        {ok && value ? <Check size={14} className="text-moss" aria-hidden /> : null}
        Lowercase letters, numbers, dashes. 3–32 characters. You can add your own domain later.
      </p>
      {error ? (
        <p id={`${id}-err`} className="mt-1.5 text-xs text-danger">
          {error}
        </p>
      ) : null}
    </div>
  );
}

function PasswordField({
  value,
  show,
  onToggle,
  onChange,
  onBlur,
  error,
  strength,
}: {
  value: string;
  show: boolean;
  onToggle: () => void;
  onChange: (v: string) => void;
  onBlur: () => void;
  error?: string;
  strength: 0 | 1 | 2 | 3 | 4;
}) {
  const id = useId();
  const labels = ["", "Weak", "Okay", "Good", "Strong"];
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium">
        Password <span className="text-danger">*</span>
      </label>
      <div className="relative">
        <input
          id={id}
          type={show ? "text" : "password"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onBlur={onBlur}
          autoComplete="new-password"
          aria-invalid={Boolean(error)}
          aria-describedby={`${id}-hint ${error ? `${id}-err` : ""}`}
          className={`${inputClass} pr-12`}
        />
        <button
          type="button"
          onClick={onToggle}
          aria-label={show ? "Hide password" : "Show password"}
          className="absolute right-0 top-1/2 mt-1 grid h-10 w-10 -translate-y-1/2 place-items-center text-muted hover:bg-paper-3"
        >
          {show ? <EyeOff size={16} /> : <Eye size={16} />}
        </button>
      </div>
      <div className="mt-2 grid grid-cols-4 gap-1" aria-hidden>
        {[1, 2, 3, 4].map((n) => (
          <span key={n} className={`h-1 ${n <= strength ? (strength >= 3 ? "bg-moss" : "bg-interactive") : "bg-paper-3"}`} />
        ))}
      </div>
      <p id={`${id}-hint`} className="mt-1.5 text-xs text-muted">
        At least 12 characters. A sentence works well. {labels[strength] ? `Strength: ${labels[strength]}.` : ""}
      </p>
      {error ? (
        <p id={`${id}-err`} className="mt-1.5 text-xs text-danger">
          {error}
        </p>
      ) : null}
    </div>
  );
}

function CheckField({ checked, onChange, children }: { checked: boolean; onChange: (v: boolean) => void; children: React.ReactNode }) {
  const id = useId();
  return (
    <label htmlFor={id} className="flex cursor-pointer items-start gap-3 border border-line bg-paper-2 p-4 text-sm leading-relaxed text-ink-2 has-[:checked]:bg-white">
      <input id={id} type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} className="mt-0.5 h-4 w-4 shrink-0 accent-ink" />
      <span>{children}</span>
    </label>
  );
}
