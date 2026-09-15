import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";

type Variant = "primary" | "secondary" | "ghost";

const base =
  "inline-flex items-center justify-center gap-2 rounded-full px-5 py-3 text-sm font-medium transition-[transform,background-color,color,box-shadow] duration-200 ease-out will-change-transform hover:-translate-y-0.5 active:translate-y-0 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:translate-y-0";

const variants: Record<Variant, string> = {
  primary: "bg-ink text-paper shadow-[0_1px_0_rgba(0,0,0,.2),0_10px_30px_-12px_rgba(22,22,22,.55)] hover:bg-ink-2",
  secondary: "border border-ink/20 bg-transparent text-ink hover:border-ink/50 hover:bg-paper-2",
  ghost: "text-ink hover:bg-paper-2",
};

export function buttonClass(variant: Variant = "primary", extra = ""): string {
  return `${base} ${variants[variant]} ${extra}`;
}

export function ButtonLink({
  variant = "primary",
  className = "",
  children,
  ...props
}: ComponentProps<typeof Link> & { variant?: Variant; children: ReactNode }) {
  return (
    <Link className={buttonClass(variant, className)} {...props}>
      {children}
    </Link>
  );
}

export function Button({
  variant = "primary",
  className = "",
  children,
  ...props
}: ComponentProps<"button"> & { variant?: Variant; children: ReactNode }) {
  return (
    <button className={buttonClass(variant, className)} {...props}>
      {children}
    </button>
  );
}
