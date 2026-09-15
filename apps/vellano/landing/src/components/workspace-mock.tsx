"use client";

const rows = [
  ["SO-1042", "Northridge Wholesale", "SKU-4412 ×4, SKU-1088 ×12", "Picked", "R 24 150"],
  ["SO-1041", "M. Naidoo", "SKU-2201 ×1", "Packed", "R 12 990"],
  ["SO-1039", "Harbour Logistics", "SKU-0190 ×2, SKU-0191 ×2", "Loaded", "R 31 400"],
  ["SO-1037", "Walk-in", "SKU-7740 ×2", "Delivered", "R 3 780"],
];

const statusTone: Record<string, string> = {
  Picked: "bg-[#d0e2ff] text-[#002d9c]",
  Packed: "bg-paper-2 text-ink-2",
  Loaded: "bg-ink text-white",
  Delivered: "bg-[#a7f0ba] text-[#044317]",
};

export function WorkspaceMock() {
  return (
    <div className="border border-line bg-white shadow-[0_2px_6px_rgba(0,0,0,.12)]">
      <div className="flex h-8 items-center gap-2 bg-ink px-3">
        <span className="truncate font-mono text-[11px] text-white/70">acme.stockroom.example / sales / orders</span>
      </div>
      <div className="grid grid-cols-[11rem_1fr] max-md:grid-cols-1">
        <aside className="hidden border-r border-line bg-paper-2 text-[12px] md:block">
          <div className="border-b border-line px-3 py-3 font-semibold">Acme (Pty) Ltd</div>
          <ul>
            {["Dashboard", "Catalogue", "Sales orders", "Quotes", "Warehouse", "Invoices", "Books", "Settings"].map((item) => (
              <li
                key={item}
                className={`px-3 py-2 ${item === "Sales orders" ? "border-l-4 border-interactive bg-white font-medium" : "text-muted"}`}
              >
                {item}
              </li>
            ))}
          </ul>
        </aside>
        <div className="p-3 sm:p-4">
          <div className="grid grid-cols-3 gap-px bg-line">
            <Kpi label="Open orders" value="18" delta="3 raised this week" />
            <Kpi label="Stock on hold" value="R 214 000" delta="42 lines" />
            <Kpi label="Ready to invoice" value="R 61 900" delta="4 deliveries" accent />
          </div>
          <table className="mt-3 w-full border-collapse text-left text-[12px]">
            <thead className="bg-paper-2 text-muted">
              <tr>
                <th className="px-3 py-2 font-medium">Order</th>
                <th className="px-3 py-2 font-medium">Customer</th>
                <th className="hidden px-3 py-2 font-medium sm:table-cell">Lines</th>
                <th className="px-3 py-2 font-medium">Status</th>
                <th className="px-3 py-2 text-right font-medium">Total</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r[0]} className="border-t border-line">
                  <td className="px-3 py-2 font-medium mono-num">{r[0]}</td>
                  <td className="px-3 py-2">{r[1]}</td>
                  <td className="hidden px-3 py-2 text-muted sm:table-cell">{r[2]}</td>
                  <td className="px-3 py-2">
                    <span className={`inline-block px-2 py-0.5 text-[11px] ${statusTone[r[3]]}`}>{r[3]}</span>
                  </td>
                  <td className="px-3 py-2 text-right mono-num">{r[4]}</td>
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
    <div className={`bg-white p-3 ${accent ? "outline outline-1 outline-blue" : ""}`}>
      <div className="text-[11px] text-muted">{label}</div>
      <div className="mt-1 text-xl leading-none mono-num sm:text-2xl">{value}</div>
      <div className="mt-1 text-[11px] text-muted">{delta}</div>
    </div>
  );
}
