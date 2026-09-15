import type { ReactNode } from "react";

export function SectionHeading({
  number,
  eyebrow,
  title,
  lede,
  align = "left",
}: {
  number: string;
  eyebrow: string;
  title: ReactNode;
  lede?: ReactNode;
  align?: "left" | "center";
}) {
  const center = align === "center";
  return (
    <div className={`max-w-3xl ${center ? "mx-auto text-center" : ""}`}>
      <div className={`flex items-center gap-3 ${center ? "justify-center" : ""}`}>
        <span className="font-display text-sm text-terracotta mono-num">{number}</span>
        <span className="h-px w-8 bg-line" aria-hidden />
        <span className="eyebrow">{eyebrow}</span>
      </div>
      <h2 className="mt-5 text-4xl leading-[1.05] sm:text-5xl">{title}</h2>
      {lede ? <p className="mt-5 text-lg leading-relaxed text-muted">{lede}</p> : null}
    </div>
  );
}
