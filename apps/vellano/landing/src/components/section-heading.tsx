import type { ReactNode } from "react";

export function SectionHeading({
  number,
  eyebrow,
  title,
  lede,
}: {
  number: string;
  eyebrow: string;
  title: ReactNode;
  lede?: ReactNode;
  align?: "left" | "center";
}) {
  return (
    <div className="max-w-3xl">
      <p className="eyebrow">
        <span className="mono-num text-interactive">{number}</span>
        <span className="mx-3 text-line">/</span>
        {eyebrow}
      </p>
      <h2 className="mt-4 font-serif text-3xl leading-tight sm:text-4xl">{title}</h2>
      {lede ? <p className="mt-4 text-base leading-relaxed text-muted sm:text-lg">{lede}</p> : null}
    </div>
  );
}
