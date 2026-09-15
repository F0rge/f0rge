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
}) {
  return (
    <div className="max-w-3xl">
      <p className="eyebrow">
        <span className="mono-num text-interactive">{number}</span>
        <span className="mx-3 text-line">/</span>
        {eyebrow}
      </p>
      <h2 className="type-display mt-4 text-[2rem] sm:text-[2.625rem]">{title}</h2>
      {lede ? <p className="mt-4 max-w-2xl text-base leading-relaxed text-muted">{lede}</p> : null}
    </div>
  );
}
