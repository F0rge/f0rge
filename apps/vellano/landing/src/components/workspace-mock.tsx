"use client";

import { ChevronDown, LogOut, Menu, Search, User } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useState } from "react";

type Screen = "home" | "till" | "quotes" | "orders" | "picks" | "invoices" | "vat201";

const menus: { id: string; label: string; items: { id: Screen; label: string }[] }[] = [
  {
    id: "sales",
    label: "Sales",
    items: [
      { id: "quotes", label: "Quotes" },
      { id: "orders", label: "Orders" },
    ],
  },
  {
    id: "warehouse",
    label: "Warehouse",
    items: [{ id: "picks", label: "Picks" }],
  },
  {
    id: "books",
    label: "Books",
    items: [
      { id: "invoices", label: "Invoices" },
      { id: "vat201", label: "VAT201" },
    ],
  },
];

const titles: Record<Screen, { title: string; crumb: string; action?: string }> = {
  home: { title: "Home", crumb: "home" },
  till: { title: "Till", crumb: "till" },
  quotes: { title: "Quotes", crumb: "sales / quotes", action: "New quote" },
  orders: { title: "Orders", crumb: "sales / orders", action: "New order" },
  picks: { title: "Picks", crumb: "warehouse / picks", action: "New pick" },
  invoices: { title: "Invoices", crumb: "books / invoices", action: "New invoice" },
  vat201: { title: "VAT201", crumb: "books / vat201" },
};

const orders = [
  ["SO-1042", "Northridge Wholesale", "4 lines", "Picked", "R 24 150"],
  ["SO-1041", "M. Naidoo", "1 line", "Packed", "R 12 990"],
  ["SO-1039", "Harbour Logistics", "2 lines", "Loaded", "R 31 400"],
  ["SO-1037", "Walk-in", "2 lines", "Delivered", "R 3 780"],
];
const quotes = [
  ["QT-220", "Northridge Wholesale", "6 lines", "Sent", "R 41 200"],
  ["QT-219", "Harbour Logistics", "3 lines", "Accepted", "R 18 400"],
  ["QT-218", "Delta Parts", "2 lines", "Draft", "R 9 660"],
];
const picks = [
  ["PK-088", "SO-1042", "WH-A", "Open", "4 / 12"],
  ["PK-087", "SO-1041", "WH-A", "Packed", "1 / 1"],
  ["PK-086", "SO-1039", "WH-B", "Short", "1 / 2"],
];
const invoices = [
  ["INV-910", "Northridge Wholesale", "15 Sep", "R 0", "Paid"],
  ["INV-909", "M. Naidoo", "14 Sep", "R 12 990", "Open"],
  ["INV-908", "Walk-in", "12 Sep", "R 0", "Paid"],
];

const tagClass: Record<string, string> = {
  Picked: "bg-tag-blue text-tag-blue-text",
  Packed: "bg-tag-gray text-ink-2",
  Loaded: "bg-ink text-white",
  Delivered: "bg-tag-green text-tag-green-text",
  Sent: "bg-tag-blue text-tag-blue-text",
  Accepted: "bg-tag-green text-tag-green-text",
  Draft: "bg-tag-gray text-ink-2",
  Open: "bg-tag-blue text-tag-blue-text",
  Short: "bg-[#ffd7d9] text-[#750e13]",
  Paid: "bg-tag-green text-tag-green-text",
};

export function WorkspaceMock() {
  const reduce = useReducedMotion();
  const [expanded, setExpanded] = useState(true);
  const [screen, setScreen] = useState<Screen>("orders");
  const [openMenus, setOpenMenus] = useState<Record<string, boolean>>({
    sales: true,
    warehouse: false,
    books: false,
  });
  const [selected, setSelected] = useState("SO-1042");
  const [query, setQuery] = useState("");
  const meta = titles[screen];

  function go(next: Screen) {
    setScreen(next);
    setQuery("");
    if (next === "quotes") setSelected("QT-220");
    if (next === "orders") setSelected("SO-1042");
    if (next === "picks") setSelected("PK-088");
    if (next === "invoices") setSelected("INV-909");
    const parent = menus.find((m) => m.items.some((i) => i.id === next));
    if (parent) setOpenMenus((s) => ({ ...s, [parent.id]: true }));
  }

  return (
    <div className="overflow-hidden border border-line bg-paper-2 text-left shadow-[0_2px_6px_rgba(0,0,0,.08)]">
      <header className="flex h-12 items-center gap-1 bg-ink text-white">
        <button
          type="button"
          className="grid h-12 w-12 shrink-0 place-items-center text-white transition-colors duration-200 hover:bg-[#353535]"
          aria-label={expanded ? "Collapse navigation" : "Expand navigation"}
          onClick={() => setExpanded((v) => !v)}
        >
          <Menu size={20} />
        </button>
        <span className="hidden items-baseline gap-2 pr-4 sm:flex">
          <span className="text-sm text-[#c6c6c6]">Stockroom</span>
          <span className="text-sm font-semibold">Acme</span>
        </span>
        <label className="relative ml-auto hidden h-8 w-48 lg:block">
          <Search size={14} className="pointer-events-none absolute left-2 top-1/2 -translate-y-1/2 text-[#c6c6c6]" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search"
            aria-label="Search this screen"
            className="h-8 w-full bg-[#393939] pl-7 pr-2 text-sm text-[#f4f4f4] outline-none placeholder:text-[#c6c6c6] focus:shadow-[inset_0_-2px_0_0_#0f62fe]"
          />
        </label>
        <span className="hidden px-3 text-sm text-[#c6c6c6] sm:block">A. Patel</span>
        <span className="grid h-12 w-12 place-items-center text-[#c6c6c6]" aria-hidden>
          <User size={18} />
        </span>
        <span className="grid h-12 w-12 place-items-center text-[#c6c6c6]" aria-hidden>
          <LogOut size={18} />
        </span>
      </header>

      <div className={`grid ${expanded ? "md:grid-cols-[16rem_minmax(0,1fr)]" : "md:grid-cols-[3rem_minmax(0,1fr)]"}`}>
        <nav aria-label="Workspace" className="hidden border-r border-line bg-paper-2 md:block">
          <NavLink label="Home" active={screen === "home"} rail={!expanded} onClick={() => go("home")} />
          <NavLink label="Till" active={screen === "till"} rail={!expanded} onClick={() => go("till")} />
          {expanded
            ? menus.map((menu) => (
                <div key={menu.id}>
                  <button
                    type="button"
                    className="flex h-12 w-full items-center justify-between px-4 text-left text-sm transition-colors duration-200 hover:bg-[#e8e8e8]"
                    aria-expanded={openMenus[menu.id]}
                    onClick={() => setOpenMenus((s) => ({ ...s, [menu.id]: !s[menu.id] }))}
                  >
                    {menu.label}
                    <ChevronDown
                      size={16}
                      className={`text-muted transition-transform duration-200 ${openMenus[menu.id] ? "rotate-0" : "-rotate-90"}`}
                    />
                  </button>
                  {openMenus[menu.id]
                    ? menu.items.map((item) => (
                        <NavLink
                          key={item.id}
                          label={item.label}
                          nested
                          active={screen === item.id}
                          onClick={() => go(item.id)}
                        />
                      ))
                    : null}
                </div>
              ))
            : null}
        </nav>

        <div className="min-w-0 bg-paper-2 p-4 sm:p-6">
          <div className="mb-3 flex gap-1 overflow-x-auto md:hidden">
            {(
              [
                ["orders", "Orders"],
                ["quotes", "Quotes"],
                ["picks", "Picks"],
                ["invoices", "Invoices"],
                ["till", "Till"],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                onClick={() => go(id)}
                className={`h-8 shrink-0 px-3 text-sm transition-colors duration-200 ${
                  screen === id ? "bg-ink text-white" : "bg-white text-muted hover:bg-[#e8e8e8]"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
            <div>
              <p className="font-mono text-[11px] text-muted">{meta.crumb}</p>
              <h3 className="text-xl font-normal">{meta.title}</h3>
            </div>
            {meta.action ? (
              <button
                type="button"
                className="h-10 bg-interactive px-4 text-sm text-white transition-colors duration-200 hover:bg-interactive-hover"
              >
                {meta.action}
              </button>
            ) : null}
          </div>
          <AnimatePresence mode="wait">
            <motion.div
              key={screen}
              initial={reduce ? false : { opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={reduce ? undefined : { opacity: 0, y: -8 }}
              transition={{ duration: 0.22, ease: [0.2, 0, 0.38, 0.9] }}
            >
              {screen === "home" ? <HomeView onJump={go} /> : null}
              {screen === "till" ? <TillView /> : null}
              {screen === "quotes" ? (
                <DataView
                  headers={["Reference", "Customer", "Items", "Status", "Total"]}
                  rows={filterRows(quotes, query)}
                  selected={selected}
                  onSelect={setSelected}
                />
              ) : null}
              {screen === "orders" ? (
                <DataView
                  headers={["Reference", "Customer", "Items", "Status", "Total"]}
                  rows={filterRows(orders, query)}
                  selected={selected}
                  onSelect={setSelected}
                />
              ) : null}
              {screen === "picks" ? (
                <DataView
                  headers={["Pick", "Order", "Location", "Status", "Qty"]}
                  rows={filterRows(picks, query)}
                  selected={selected}
                  onSelect={setSelected}
                />
              ) : null}
              {screen === "invoices" ? (
                <DataView
                  headers={["Number", "Customer", "Issued", "Balance", "Status"]}
                  rows={filterRows(invoices, query)}
                  selected={selected}
                  onSelect={setSelected}
                />
              ) : null}
              {screen === "vat201" ? <VatView /> : null}
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}

function filterRows(rows: string[][], query: string) {
  const q = query.trim().toLowerCase();
  if (!q) return rows;
  return rows.filter((r) => r.some((c) => c.toLowerCase().includes(q)));
}

function NavLink({
  label,
  active,
  nested = false,
  rail = false,
  onClick,
}: {
  label: string;
  active: boolean;
  nested?: boolean;
  rail?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={label}
      className={`flex h-12 w-full items-center border-l-4 text-left text-sm transition-colors duration-200 ${
        active ? "border-interactive bg-white font-medium" : "border-transparent text-muted hover:bg-[#e8e8e8]"
      } ${nested ? "pl-8" : "pl-4"} ${rail ? "justify-center px-0 pl-0" : ""}`}
    >
      {rail ? label.slice(0, 1) : label}
    </button>
  );
}

function DataView({
  headers,
  rows,
  selected,
  onSelect,
}: {
  headers: string[];
  rows: string[][];
  selected: string;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="overflow-x-auto border border-line bg-white">
      <table className="w-full border-collapse text-left text-[14px]">
        <thead className="bg-paper-2 text-muted">
          <tr>
            {headers.map((h, i) => (
              <th key={h} className={`h-12 px-4 font-medium ${i === headers.length - 1 ? "text-right" : ""}`}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={headers.length} className="h-12 px-4 text-sm text-muted">
                No matching rows.
              </td>
            </tr>
          ) : (
            rows.map((r) => {
              const id = r[0];
              const on = id === selected;
              return (
                <tr
                  key={id}
                  tabIndex={0}
                  onClick={() => onSelect(id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      onSelect(id);
                    }
                  }}
                  className={`cursor-pointer border-t border-line transition-colors duration-150 ${
                    on ? "bg-[#edf5ff]" : "hover:bg-paper-2"
                  }`}
                >
                  {r.map((c, i) => (
                    <td
                      key={headers[i]}
                      className={`h-12 whitespace-nowrap px-4 ${i === 0 ? "font-medium mono-num" : ""} ${
                        i === r.length - 1 && !tagClass[c] ? "text-right mono-num" : ""
                      }`}
                    >
                      {tagClass[c] ? (
                        <span className={`inline-block rounded-full px-2.5 py-0.5 text-[12px] ${tagClass[c]}`}>{c}</span>
                      ) : (
                        c
                      )}
                    </td>
                  ))}
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}

function HomeView({ onJump }: { onJump: (s: Screen) => void }) {
  const tiles = [
    { label: "Open orders", value: "18", delta: "3 this week", screen: "orders" as const },
    { label: "Stock on hold", value: "R 214 000", delta: "42 lines", screen: "picks" as const },
    { label: "Ready to invoice", value: "R 61 900", delta: "4 deliveries", screen: "invoices" as const },
  ];
  return (
    <div className="grid grid-cols-3 gap-px border border-line bg-line">
      {tiles.map((t) => (
        <button
          key={t.label}
          type="button"
          onClick={() => onJump(t.screen)}
          className="bg-white p-4 text-left transition-colors duration-200 hover:bg-[#edf5ff]"
        >
          <div className="text-[12px] text-muted">{t.label}</div>
          <div className="mt-1 text-2xl font-light leading-none mono-num">{t.value}</div>
          <div className="mt-1 text-[12px] text-muted">{t.delta}</div>
        </button>
      ))}
    </div>
  );
}

function TillView() {
  const lines = [
    ["SKU-4412", "R 14 500"],
    ["SKU-1088 ×6", "R 8 400"],
    ["Layby deposit", "− R 5 000"],
  ];
  return (
    <div className="max-w-sm border border-line bg-white p-4 font-mono text-[13px]">
      <div className="text-center">Acme (Pty) Ltd — till 1</div>
      <div className="mt-3 border-t border-dashed border-line pt-3">
        {lines.map(([l, r]) => (
          <div key={l} className="flex justify-between text-muted">
            <span>{l}</span>
            <span className="mono-num">{r}</span>
          </div>
        ))}
      </div>
      <div className="mt-3 flex justify-between border-t border-line pt-3 font-medium">
        <span>Balance</span>
        <span className="mono-num">R 20 585</span>
      </div>
    </div>
  );
}

function VatView() {
  const boxes = [
    ["Box 1", "Output", "R 186 400"],
    ["Box 4", "Input", "R 41 220"],
    ["Box 14", "Payable", "R 145 180"],
  ];
  return (
    <div className="border border-line bg-white">
      <p className="border-b border-line px-4 py-3 text-sm text-muted">Draft for the current period. Copy into eFiling — we do not submit it.</p>
      <dl>
        {boxes.map(([k, l, v]) => (
          <div key={k} className="grid grid-cols-3 border-b border-line last:border-0">
            <dt className="px-4 py-3 font-mono text-sm">{k}</dt>
            <dd className="px-4 py-3 text-sm text-muted">{l}</dd>
            <dd className="px-4 py-3 text-right text-sm mono-num">{v}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
