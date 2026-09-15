"use client";

import { motion, useScroll, useTransform } from "motion/react";
import { useRef } from "react";

const rows = [
  ["SO-1042", "Bedfordview Interiors", "Oak dining table ×1, chairs ×6", "Picked", "R 24 150"],
  ["SO-1041", "M. Naidoo", "Linen 3-seater", "Packed", "R 12 990"],
  ["SO-1039", "Kramer Property Co.", "Reception desk, 2 × pedestals", "Loaded", "R 31 400"],
  ["SO-1037", "Walk-in", "Side table ×2", "Delivered", "R 3 780"],
];

const statusTone: Record<string, string> = {
  Picked: "bg-oak-2 text-ink-2",
  Packed: "bg-paper-3 text-ink-2",
  Loaded: "bg-ink text-paper",
  Delivered: "bg-moss/15 text-moss",
};

export function WorkspaceMock() {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start end", "center center"] });
  const rotateX = useTransform(scrollYProgress, [0, 1], [10, 0]);
  const y = useTransform(scrollYProgress, [0, 1], [40, 0]);

  return (
    <div ref={ref} className="[perspective:1600px]">
      <motion.div
        style={{ rotateX, y, transformOrigin: "50% 100%" }}
        className="rounded-2xl border border-line bg-paper-2 p-2 shadow-[0_40px_80px_-40px_rgba(22,22,22,.45),0_2px_0_rgba(255,255,255,.6)_inset]"
      >
        <div className="overflow-hidden rounded-xl border border-line bg-white">
          <div className="flex items-center gap-2 border-b border-line bg-paper px-4 py-2.5">
            <span className="h-2.5 w-2.5 rounded-full bg-paper-3" />
            <span className="h-2.5 w-2.5 rounded-full bg-paper-3" />
            <span className="h-2.5 w-2.5 rounded-full bg-paper-3" />
            <span className="ml-3 rounded-md bg-white px-3 py-1 text-[11px] text-muted">acme.stockroom.example/sales/orders</span>
          </div>
          <div className="grid grid-cols-[150px_1fr] max-md:grid-cols-1">
            <aside className="hidden border-r border-line bg-paper/60 p-4 text-[12px] md:block">
              <div className="font-display text-base">Acme Interiors</div>
              <ul className="mt-5 space-y-2 text-muted">
                <li>Dashboard</li>
                <li>Catalogue</li>
                <li className="rounded-md bg-ink px-2 py-1 text-paper">Sales orders</li>
                <li>Quotes</li>
                <li>Warehouse</li>
                <li>Invoices</li>
                <li>Books</li>
                <li>Settings</li>
              </ul>
            </aside>
            <div className="p-4 sm:p-5">
              <div className="grid grid-cols-3 gap-3">
                <Kpi label="Open orders" value="18" delta="+3 this week" />
                <Kpi label="Stock on hold" value="R 214k" delta="42 lines" />
                <Kpi label="Ready to invoice" value="R 61 900" delta="4 deliveries" accent />
              </div>
              <div className="mt-4 overflow-hidden rounded-lg border border-line">
                <table className="w-full text-left text-[12px]">
                  <thead className="bg-paper text-muted">
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
                          <span className={`rounded-full px-2 py-0.5 text-[11px] ${statusTone[r[3]]}`}>{r[3]}</span>
                        </td>
                        <td className="px-3 py-2 text-right mono-num">{r[4]}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      </motion.div>
    </div>
  );
}

function Kpi({ label, value, delta, accent = false }: { label: string; value: string; delta: string; accent?: boolean }) {
  return (
    <div className={`rounded-lg border border-line p-3 ${accent ? "bg-oak-2/50" : "bg-paper/50"}`}>
      <div className="text-[11px] text-muted">{label}</div>
      <div className="mt-1 font-display text-xl leading-none mono-num sm:text-2xl">{value}</div>
      <div className="mt-1 text-[11px] text-muted">{delta}</div>
    </div>
  );
}
