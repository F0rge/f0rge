import { Reveal } from "@/components/reveal";
import { SectionHeading } from "@/components/section-heading";

const roles = [
  {
    role: "Owner",
    does: "Users, locations, CSV import, settings, full books.",
    not: "Nothing hidden. This is the login created at signup.",
  },
  {
    role: "Warehouse",
    does: "Pick, pack, load, deliver, transfer, stocktake.",
    not: "Price lists, posting invoices, other companies’ hosts.",
  },
  {
    role: "Till / sales",
    does: "Quotes, sales orders, cash-up, layby, walk-in customers.",
    not: "Cost, if the permission is off. Books close and VAT201.",
  },
  {
    role: "Books",
    does: "Invoices, bills, credit notes, bank import, VAT201 draft.",
    not: "Skipping warehouse states to ‘make the invoice match’.",
  },
  {
    role: "Trade customer",
    does: "Catalogue at their prices. Draft sales orders on your hostname.",
    not: "Staff screens, cost, other customers, your books.",
  },
];

const documents = [
  ["Quote", "QT-", "No stock hold, no GL."],
  ["Sales order", "SO-", "Hold at a location. ATP drops."],
  ["Pick / pack / deliver", "—", "Warehouse quantity. Shorts recorded."],
  ["Customer deposit", "—", "GL 2300 Customer deposits."],
  ["Tax invoice", "INV-", "1100 Debtors, 4000 Sales, 2200 VAT output."],
  ["Credit note", "CN-", "Reverses tax and, where configured, stock."],
  ["VAT201", "draft", "A read of the ledger. You copy it into eFiling."],
];

export function CompanySetup() {
  return (
    <section id="company" className="scroll-mt-16 border-t border-line bg-paper-2">
      <div className="page-wrap py-16 sm:py-20">
        <Reveal>
          <SectionHeading
            number="03"
            eyebrow="Company model"
            title="Who signs in, and which document posts where."
            lede="Permissions are keys on the login, not a shared password in a drawer. Trade customers use a separate cookie on the same hostname. Staff tokens and customer tokens are not interchangeable."
          />
        </Reveal>

        <div className="mt-12 overflow-x-auto border border-line bg-white">
          <table className="w-full min-w-[40rem] border-collapse text-left text-sm">
            <caption className="sr-only">Roles and what each login can do</caption>
            <thead className="bg-paper-2 text-muted">
              <tr>
                <th className="h-12 px-4 font-medium">Login</th>
                <th className="h-12 px-4 font-medium">Can</th>
                <th className="h-12 px-4 font-medium">Cannot</th>
              </tr>
            </thead>
            <tbody>
              {roles.map((r) => (
                <tr key={r.role} className="border-t border-line">
                  <td className="px-4 py-4 font-medium">{r.role}</td>
                  <td className="px-4 py-4 text-muted">{r.does}</td>
                  <td className="px-4 py-4 text-muted">{r.not}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="mt-4 overflow-x-auto border border-line bg-white">
          <table className="w-full min-w-[40rem] border-collapse text-left text-sm">
            <caption className="sr-only">Documents and general ledger effect</caption>
            <thead className="bg-paper-2 text-muted">
              <tr>
                <th className="h-12 px-4 font-medium">Document</th>
                <th className="h-12 px-4 font-medium">Number</th>
                <th className="h-12 px-4 font-medium">What it does</th>
              </tr>
            </thead>
            <tbody>
              {documents.map((d) => (
                <tr key={d[0]} className="border-t border-line">
                  <td className="h-12 px-4 font-medium">{d[0]}</td>
                  <td className="h-12 px-4 font-mono text-muted">{d[1]}</td>
                  <td className="h-12 px-4 text-muted">{d[2]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-4 max-w-3xl text-sm text-muted">
          Chart of accounts is seeded for the owner. You can add accounts. You cannot delete ones the documents still post
          to. Opening balances and Cin7/Xero-shaped CSVs are in settings after the first login — there is no live two-way
          sync on day one.
        </p>
      </div>
    </section>
  );
}
