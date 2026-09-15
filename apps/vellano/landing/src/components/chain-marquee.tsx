const steps = ["Quote", "Accept", "Sales order", "Hold stock", "Pick", "Pack", "Load", "Deliver", "Invoice", "Paid"];

export function ChainMarquee() {
  const doubled = [...steps, ...steps];
  return (
    <section aria-label="Order chain" className="group border-y border-line bg-paper-2/70 py-5">
      <div className="relative overflow-hidden [mask-image:linear-gradient(90deg,transparent,black_8%,black_92%,transparent)]">
        <ul className="flex w-max animate-marquee items-center gap-10 whitespace-nowrap px-5 group-hover:[animation-play-state:paused]">
          {doubled.map((s, i) => (
            <li key={`${s}-${i}`} className="flex items-center gap-10">
              <span className="font-display text-2xl sm:text-3xl">{s}</span>
              <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-terracotta" />
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
