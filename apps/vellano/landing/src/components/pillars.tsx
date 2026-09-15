import { Reveal } from "@/components/reveal";
import { SectionHeading } from "@/components/section-heading";

export function Pillars() {
  return (
    <section id="product" className="scroll-mt-16">
      <div className="page-wrap section-y">
        <Reveal>
          <SectionHeading
            number="01"
            eyebrow="What posts"
            title="Stock, till, and books already share a chart of accounts."
            lede="Built for companies that buy stock, hold it at locations, and sell it on account or at a till. If you only need a catalogue website, this will feel heavy."
          />
        </Reveal>
        <div className="mt-12 grid gap-px bg-line lg:grid-cols-3">
          <Reveal>
            <Card
              title="Stock and warehouse"
              body="Locations, transfers, stocktakes, landed cost from the purchase order. Pick, pack, load, deliver on a phone — the warehouse console is the same quantities as the desk."
              facts={[
                "Bin-level if you set bins. Location-level if you do not.",
                "A hold from a sales order is visible to the next picker.",
                "A short pick is recorded. It does not become ‘delivered’.",
              ]}
            >
              <StockMock />
            </Card>
          </Reveal>
          <Reveal delay={0.04}>
            <Card
              title="Sell"
              body="Till with cash-up. Layby. Quotes that become sales orders with stock held. Trade customers log in on your hostname and place orders that land as drafts."
              facts={["Walk-in and account customers on the same till.", "Deposit on GL 2300, not a note in a comment field."]}
            >
              <TillMock />
            </Card>
          </Reveal>
          <Reveal delay={0.08}>
            <Card
              title="Books"
              body="Invoices, bills, credit notes, bank import, aged AR/AP. The VAT201 is a draft you copy into eFiling. We do not file it."
              facts={["15% on the line. Credit notes reverse the tax, not just the total.", "Opening balances and Cin7/Xero-shaped CSVs after you are in."]}
            >
              <LedgerMock />
            </Card>
          </Reveal>
        </div>
      </div>
    </section>
  );
}

function Card({ title, body, facts, children }: { title: string; body: string; facts: string[]; children: React.ReactNode }) {
  return (
    <article className="flex h-full flex-col bg-white p-6 sm:p-8">
      <div className="border border-line bg-paper-2 p-4">{children}</div>
      <h3 className="mt-6 text-xl font-normal">{title}</h3>
      <p className="mt-3 text-sm leading-relaxed text-muted">{body}</p>
      <ul className="mt-4 space-y-2 text-sm text-ink-2">
        {facts.map((b) => (
          <li key={b} className="flex gap-3">
            <span aria-hidden className="mt-2 h-px w-4 shrink-0 bg-interactive" />
            {b}
          </li>
        ))}
      </ul>
    </article>
  );
}

function StockMock() {
  const locs = [
    ["WH-A", 82],
    ["WH-B", 46],
    ["Returns", 12],
    ["Transit", 28],
  ] as const;
  return (
    <div className="space-y-2 text-[12px]">
      {locs.map(([name, pct]) => (
        <div key={name}>
          <div className="flex justify-between text-muted">
            <span>{name}</span>
            <span className="mono-num">{pct}%</span>
          </div>
          <div className="mt-1 h-1 bg-paper-3">
            <div className="h-full bg-ink" style={{ width: `${pct}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}

function TillMock() {
  return (
    <div className="border border-line bg-white p-3 font-mono text-[12px]">
      <div className="text-center text-sm">Acme (Pty) Ltd — till 1</div>
      <div className="mt-2 border-t border-dashed border-line pt-2">
        <Line l="SKU-4412" r="R 14 500" />
        <Line l="SKU-1088 ×6" r="R 8 400" />
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
          <tr key={l[0] + l[1]} className="border-b border-line last:border-0">
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
