"use client";

const rows = [
  ["SO-1042", "Northridge Wholesale", "SKU-4412 ×4", "Picked", "R 24 150"],
  ["SO-1041", "M. Naidoo", "SKU-2201 ×1", "Packed", "R 12 990"],
  ["SO-1039", "Harbour Logistics", "SKU-0190 ×2", "Loaded", "R 31 400"],
  ["SO-1037", "Walk-in", "SKU-7740 ×2", "Delivered", "R 3 780"],
];

const statusTone: Record<string, string> = {
  Picked: "bg-tag-blue text-tag-blue-text",
  Packed: "bg-tag-gray text-ink-2",
  Loaded: "bg-ink text-white",
  Delivered: "bg-tag-green text-tag-green-text",
};

const nav = ["Dashboard", "Catalogue", "Sales orders", "Quotes", "Warehouse", "Invoices", "Books", "Settings"];

export function WorkspaceMock() {
  return (
    <div className="border border-line bg-white">
      <div className="flex h-12 items-center gap-3 border-b border-[#393939] bg-ink px-4">
        <span aria-hidden className="grid h-6 w-6 place-items-center bg-white">
          <span className="block h-2.5 w-2.5 bg-ink" />
        </span>
        <span className="text-sm font-semibold text-white">Acme (Pty) Ltd</span>
        <span className="ml-auto truncate font-mono text-[11px] text-[#c6c6c6]">acme.stockroom.example / sales / orders</span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-[12rem_minmax(0,1fr)]">
        <aside className="hidden border-r border-line bg-paper-2 text-[14px] md:block">
          <ul>
            {nav.map((item) => (
              <li
                key={item}
                className={`h-12 px-4 leading-[3rem] ${
                  item === "Sales orders"
                    ? "border-l-4 border-interactive bg-white font-medium"
                    : "border-l-4 border-transparent text-muted"
                }`}
              >
                {item}
              </li>
            ))}
          </ul>
        </aside>
        <div className="p-0">
          <div className="grid grid-cols-3 divide-x divide-line border-b border-line">
            <Kpi label="Open orders" value="18" delta="3 raised this week" />
            <Kpi label="Stock on hold" value="R 214 000" delta="42 lines" />
            <Kpi label="Ready to invoice" value="R 61 900" delta="4 deliveries" accent />
          </div>
          <table className="w-full border-collapse text-left text-[14px]">
            <thead className="bg-paper-2 text-muted">
              <tr>
                <th className="h-12 px-4 font-medium">Order</th>
                <th className="h-12 px-4 font-medium">Customer</th>
                <th className="hidden h-12 px-4 font-medium sm:table-cell">Lines</th>
                <th className="h-12 px-4 font-medium">Status</th>
                <th className="h-12 px-4 text-right font-medium">Total</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r[0]} className="border-t border-line">
                  <td className="h-12 whitespace-nowrap px-4 font-medium mono-num">{r[0]}</td>
                  <td className="h-12 px-4">{r[1]}</td>
                  <td className="hidden h-12 px-4 text-muted sm:table-cell">{r[2]}</td>
                  <td className="h-12 whitespace-nowrap px-4">
                    <span className={`inline-block px-2 py-0.5 text-[12px] ${statusTone[r[3]]}`}>{r[3]}</span>
                  </td>
                  <td className="h-12 whitespace-nowrap px-4 text-right mono-num">{r[4]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function Kpi({ label, value, delta, accent = false }: { label: string; value: string; delta: string; accent?: boolean }) {
  return (
    <div className={`bg-white p-4 ${accent ? "outline outline-1 outline-interactive" : ""}`}>
      <div className="text-[12px] text-muted">{label}</div>
      <div className="mt-1 text-2xl font-light leading-none mono-num">{value}</div>
      <div className="mt-1 text-[12px] text-muted">{delta}</div>
    </div>
  );
}
