import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";

type Variant = "primary" | "secondary" | "ghost" | "header";

const base =
  "inline-flex h-12 items-center justify-center gap-2 px-4 text-sm font-normal transition-colors duration-100 disabled:cursor-not-allowed disabled:bg-[#c6c6c6] disabled:text-[#8d8d8d] disabled:hover:bg-[#c6c6c6]";

const variants: Record<Variant, string> = {
  primary: "bg-interactive text-white hover:bg-interactive-hover active:bg-interactive-active",
  secondary: "bg-ink-2 text-white hover:bg-[#474747] active:bg-[#6f6f6f]",
  ghost: "bg-transparent text-ink hover:bg-paper-2",
  header: "bg-interactive text-white hover:bg-interactive-hover",
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
