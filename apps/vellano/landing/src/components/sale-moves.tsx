const steps = [
  { n: "01", name: "Quote", note: "Lines, tax, validity. Numbered QT-." },
  { n: "02", name: "Accept", note: "The customer accepts. There is no second document type invented at this step." },
  { n: "03", name: "Sales order", note: "The quote becomes an SO. Stock is reserved at a location." },
  { n: "04", name: "Hold", note: "Available-to-promise drops. Other quotes cannot take the same units." },
  { n: "05", name: "Pick", note: "Phone or desk. Short, over, substitute — recorded on the line." },
  { n: "06", name: "Pack", note: "What left the bin is what the packing sheet says." },
  { n: "07", name: "Load", note: "A load has a status. Tracking is optional." },
  { n: "08", name: "Deliver", note: "Proof of delivery closes the warehouse step." },
  { n: "09", name: "Invoice", note: "Remainder after any deposit. A tax invoice, not a screenshot of the quote." },
  { n: "10", name: "Paid", note: "Cash, EFT, or allocation against the debtor. The VAT201 draft can see it." },
];

export function SaleMoves() {
  return (
    <section id="sale" className="scroll-mt-16 border-b border-line">
      <div className="page-wrap py-16 sm:py-20">
        <p className="eyebrow">
          <span className="mono-num text-interactive">00</span>
          <span className="mx-3 text-line">/</span>
          How a sale moves
        </p>
        <h2 className="type-display mt-4 max-w-2xl text-[2rem] sm:text-[2.625rem]">
          Ten states. Skip one and the next is blocked.
        </h2>
        <p className="mt-4 max-w-2xl text-base text-muted">
          That is slower at the till on day one. It is cheaper in a dispute six months later, when someone asks what left the
          building and what was invoiced.
        </p>
        <ol className="mt-10 divide-y divide-line border-y border-line">
          {steps.map((s) => (
            <li key={s.n} className="grid gap-1 py-4 sm:grid-cols-[4.5rem_12rem_1fr] sm:items-baseline">
              <span className="font-mono text-sm text-muted">{s.n}</span>
              <span className="font-medium">{s.name}</span>
              <span className="text-sm text-muted">{s.note}</span>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
