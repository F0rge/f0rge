import { Reveal } from "@/components/reveal";
import { SectionHeading } from "@/components/section-heading";

export function Pillars() {
  return (
    <section id="product" className="mx-auto max-w-7xl scroll-mt-20 px-5 py-24 sm:px-8 sm:py-32">
      <Reveal>
        <SectionHeading
          number="01"
          eyebrow="What you run on it"
          title={
            <>
              Three jobs, <span className="display-italic">one set of numbers.</span>
            </>
          }
          lede="Stock, sales, and books stop living in three systems and a spreadsheet. Every quote, pick, and invoice posts to the same ledger."
        />
      </Reveal>
      <div className="mt-14 grid gap-5 md:grid-cols-3">
        <Reveal delay={0}>
          <Card
            title="Stock & warehouse"
            bullets={["Locations, bins, transfers, stocktakes", "Phone-first pick, pack, load, deliver", "Landed cost from purchase order to shelf"]}
          >
            <StockMock />
          </Card>
        </Reveal>
        <Reveal delay={0.08}>
          <Card
            title="Sell"
            bullets={["Till with layby and cash-up", "Quotes → sales orders with stock holds", "Trade portal for your B2B customers"]}
          >
            <TillMock />
          </Card>
        </Reveal>
        <Reveal delay={0.16}>
          <Card
            title="Books"
            bullets={["Invoices, bills, credit notes, deposits", "Bank import and reconciliation", "Aged AR/AP and a VAT201 draft"]}
          >
            <LedgerMock />
          </Card>
        </Reveal>
      </div>
    </section>
  );
}

function Card({ title, bullets, children }: { title: string; bullets: string[]; children: React.ReactNode }) {
  return (
    <article className="group flex h-full flex-col rounded-2xl border border-line bg-white/60 p-6 transition-[transform,box-shadow] duration-300 hover:-translate-y-1 hover:shadow-[0_30px_60px_-40px_rgba(22,22,22,.5)]">
      <div className="rounded-xl border border-line bg-paper p-4">{children}</div>
      <h3 className="mt-6 text-2xl">{title}</h3>
      <ul className="mt-4 space-y-2 text-sm text-muted">
        {bullets.map((b) => (
          <li key={b} className="flex gap-3">
            <span aria-hidden className="mt-2 h-1 w-3 shrink-0 bg-terracotta" />
            {b}
          </li>
        ))}
      </ul>
    </article>
  );
}

function StockMock() {
  const locs = [
    ["Warehouse A", 82],
    ["Showroom", 46],
    ["Returns", 12],
    ["In transit", 28],
  ] as const;
  return (
    <div className="space-y-2.5 text-[12px]">
      {locs.map(([name, pct]) => (
        <div key={name}>
          <div className="flex justify-between text-muted">
            <span>{name}</span>
            <span className="mono-num">{pct}%</span>
          </div>
          <div className="mt-1 h-2 overflow-hidden rounded-full bg-paper-3">
            <div className="h-full rounded-full bg-ink transition-[width] duration-700 group-hover:bg-terracotta" style={{ width: `${pct}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}

function TillMock() {
  return (
    <div className="mx-auto max-w-[220px] rounded-md border border-line bg-white p-3 text-[12px] shadow-sm">
      <div className="text-center font-display text-sm">Acme Interiors</div>
      <div className="mt-2 border-t border-dashed border-line pt-2">
        <Line l="Oak dining table" r="R 14 500" />
        <Line l="Dining chair ×6" r="R 8 400" />
        <Line l="Layby deposit" r="− R 5 000" />
      </div>
      <div className="mt-2 border-t border-line pt-2">
        <Line l="Subtotal" r="R 17 900" />
        <Line l="VAT 15%" r="R 2 685" />
        <Line l="Balance" r="R 20 585" bold />
      </div>
    </div>
  );
}

function LedgerMock() {
  const lines = [
    ["1100", "Debtors control", "24 150", ""],
    ["4000", "Sales", "", "21 000"],
    ["2200", "VAT output", "", "3 150"],
    ["2300", "Customer deposits", "5 000", ""],
    ["1000", "Bank", "", "5 000"],
  ];
  return (
    <table className="w-full text-[11px]">
      <tbody>
        {lines.map((l) => (
          <tr key={l[0] + l[1]} className="border-b border-line/70 last:border-0">
            <td className="py-1 pr-2 text-muted mono-num">{l[0]}</td>
            <td className="py-1">{l[1]}</td>
            <td className="py-1 text-right mono-num">{l[2]}</td>
            <td className="py-1 text-right text-muted mono-num">{l[3]}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Line({ l, r, bold = false }: { l: string; r: string; bold?: boolean }) {
  return (
    <div className={`flex justify-between ${bold ? "font-medium" : "text-muted"}`}>
      <span>{l}</span>
      <span className="mono-num">{r}</span>
    </div>
  );
}
