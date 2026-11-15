import { useId, useState } from "react";
import { Heading, Flash, Link, Select, FormControl } from "@f0rge/primer";
import type { Alert, Listing, ModelMarket } from "./api/client";
import { money, number, safeUrl } from "./format";
import type { Kind } from "./state";
type Row = Listing & { profit: number | null; roi: number | null };
type Point = { label: string; x: number; y: number; url?: string };
function Scatter({
  title,
  xLabel,
  yLabel,
  points,
}: {
  title: string;
  xLabel: string;
  yLabel: string;
  points: Point[];
}) {
  const id = useId();
  const xmin = Math.min(0, ...points.map((p) => p.x)),
    xmax = Math.max(1, ...points.map((p) => p.x)),
    ymin = Math.min(0, ...points.map((p) => p.y)),
    ymax = Math.max(1, ...points.map((p) => p.y));
  return (
    <section className="panel stack">
      <Heading as="h3">{title}</Heading>
      {points.length ? (
        <>
          <svg
            className="chart"
            viewBox="0 0 640 260"
            role="group"
            aria-labelledby={id}
          >
            <title id={id}>
              {title}. Exact observations are also available in the data table.
            </title>
            <line x1="45" y1="225" x2="620" y2="225" stroke="currentColor" />
            <line x1="45" y1="15" x2="45" y2="225" stroke="currentColor" />
            <text x="240" y="255">
              {xLabel}
            </text>
            <text x="50" y="15">
              {yLabel}
            </text>
            {points.map((p, index) => (
              <a key={index} href={p.url ? safeUrl(p.url) : undefined}>
                <circle
                  className="dot"
                  cx={45 + ((p.x - xmin) / (xmax - xmin)) * 570}
                  cy={225 - ((p.y - ymin) / (ymax - ymin)) * 200}
                  r="4"
                >
                  <title>
                    {p.label}: {number(p.x)}, {number(p.y)}
                  </title>
                </circle>
              </a>
            ))}
          </svg>
          <details>
            <summary>Accessible data table ({points.length})</summary>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Observation</th>
                    <th>{xLabel}</th>
                    <th>{yLabel}</th>
                  </tr>
                </thead>
                <tbody>
                  {points.map((p, index) => (
                    <tr key={index}>
                      <td>
                        {p.url ? (
                          <Link href={safeUrl(p.url)}>{p.label}</Link>
                        ) : (
                          p.label
                        )}
                      </td>
                      <td>{number(p.x)}</td>
                      <td>{number(p.y)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </>
      ) : (
        <p className="muted">Not enough observations.</p>
      )}
    </section>
  );
}
function Bars({
  title,
  values,
  unit,
}: {
  title: string;
  values: { label: string; value: number }[];
  unit: string;
}) {
  const maximum = Math.max(1, ...values.map((v) => v.value));
  return (
    <section className="panel stack">
      <Heading as="h3">{title}</Heading>
      {values.length ? (
        <table>
          <thead>
            <tr>
              <th>Group</th>
              <th>{unit}</th>
              <th aria-label="Relative amount" />
            </tr>
          </thead>
          <tbody>
            {values.map((value) => (
              <tr key={value.label}>
                <td>{value.label}</td>
                <td>{number(value.value)}</td>
                <td>
                  <meter
                    min="0"
                    max={maximum}
                    value={value.value}
                    aria-label={`${value.label}: ${number(value.value)} ${unit}`}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="muted">Not enough observations.</p>
      )}
    </section>
  );
}
export function Insights({
  rows,
  allRows,
  models,
}: {
  rows: Row[];
  allRows: Row[];
  models: ModelMarket[];
}) {
  const [model, setModel] = useState("");
  const modelNames = new Set(rows.map((row) => row.brand + " " + row.model));
  const visibleModels = models.filter((item) => modelNames.has(item.name));
  const selected = models.find((item) => item.name === model);
  const observations = rows.filter(
    (row) => row.profit != null && row.roi != null,
  );
  const age = new Map<string, number>();
  for (const row of rows) {
    const lower = Math.floor(row.days_listed / 10) * 10;
    const label = `${lower}–${lower + 9} days`;
    age.set(label, (age.get(label) ?? 0) + 1);
  }
  const risks = new Map<string, number>();
  for (const row of observations.filter((row) => (row.profit ?? 0) > 0))
    for (const flag of row.risk_flags)
      risks.set(flag, (risks.get(flag) ?? 0) + 1);
  const compared = allRows.filter(
    (row) => row.brand + " " + row.model === model,
  );
  return (
    <section className="stack">
      <Heading as="h2">Market insights</Heading>
      <p>
        Charts use the current category and filters; reference-based return
        charts use your saved costs. Missing observations stay missing.
        “Disappeared” includes sold or withdrawn listings.
      </p>
      <div className="cards">
        <Scatter
          title="Profit vs ROI"
          xLabel="Estimated profit (€)"
          yLabel="ROI (%)"
          points={observations.map((row) => ({
            label: row.name,
            x: row.profit ?? 0,
            y: row.roi ?? 0,
            url: row.url,
          }))}
        />
        <Scatter
          title="Discount vs days listed"
          xLabel="Days listed"
          yLabel="Below reference (%)"
          points={rows.flatMap((row) =>
            row.discount_percent == null
              ? []
              : [
                  {
                    label: row.name,
                    x: row.days_listed,
                    y: row.discount_percent,
                    url: row.url,
                  },
                ],
          )}
        />
        <Bars
          title="Fastest-disappearing models (30 days)"
          unit="Median days"
          values={visibleModels
            .flatMap((item) =>
              item.median_days == null
                ? []
                : [{ label: item.name, value: item.median_days }],
            )
            .sort((a, b) => a.value - b.value)
            .slice(0, 15)}
        />
        <Bars
          title="Model disappearance share (30 days)"
          unit="Percent"
          values={visibleModels
            .flatMap((item) =>
              item.sell_through == null
                ? []
                : [{ label: item.name, value: item.sell_through }],
            )
            .sort((a, b) => b.value - a.value)
            .slice(0, 15)}
        />
        <Bars
          title="Days listed"
          unit="Listings"
          values={[...age]
            .map(([label, value]) => ({ label, value }))
            .sort((a, b) => parseInt(a.label) - parseInt(b.label))}
        />
        <Bars
          title="Risk flags among profitable listings"
          unit="Listings"
          values={[...risks]
            .map(([label, value]) => ({ label, value }))
            .sort((a, b) => b.value - a.value)}
        />
      </div>
      <section className="panel stack">
        <Heading as="h3">Compare a model</Heading>
        <FormControl>
          <FormControl.Label>Model</FormControl.Label>
          <Select
            value={model}
            onChange={(event) => setModel(event.target.value)}
          >
            <Select.Option value="">Choose a model</Select.Option>
            {models.map((item) => (
              <Select.Option key={item.name} value={item.name}>
                {item.name}
              </Select.Option>
            ))}
          </Select>
        </FormControl>
        {selected && (
          <>
            <p>
              {selected.active} active · {selected.gone30} disappeared in 30
              days ·{" "}
              {selected.sell_through == null
                ? "Not observed"
                : number(selected.sell_through) + "%"}{" "}
              disappearance share ·{" "}
              {selected.median_days == null
                ? "Not observed"
                : number(selected.median_days) + " days"}{" "}
              median time to disappear.
            </p>
            <Scatter
              title="Daily median asks and disappeared asking prices"
              xLabel="Days since first plotted date"
              yLabel="Asking price (€)"
              points={(() => {
                const data = [
                  ...selected.trend.map((point) => ({
                    day: point.day,
                    price: point.median_price,
                    label: `${point.day} median (n=${point.n})`,
                  })),
                  ...selected.disappeared.map((point) => ({
                    day: point.day,
                    price: point.price,
                    label: `${point.day} disappeared last ask`,
                  })),
                ];
                const first = Math.min(
                  ...data.map((point) => Date.parse(point.day + "T00:00:00Z")),
                );
                return data.map((point) => ({
                  label: point.label,
                  x: (Date.parse(point.day + "T00:00:00Z") - first) / 86400000,
                  y: point.price,
                }));
              })()}
            />
            <div className="table-scroll">
              <table>
                <caption>Observed listings for {model}</caption>
                <thead>
                  <tr>
                    <th>Listing</th>
                    <th>Ask</th>
                    <th>Days</th>
                    <th>State</th>
                  </tr>
                </thead>
                <tbody>
                  {compared.map((row) => (
                    <tr key={row.id}>
                      <td>
                        <Link href={safeUrl(row.url)}>{row.name}</Link>
                      </td>
                      <td>{money(row.price)}</td>
                      <td>{number(row.days_listed)}</td>
                      <td>
                        {row.gone_at ? `Disappeared ${row.gone_at}` : "Active"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>
    </section>
  );
}
export function Alerts({ items, kind }: { items: Alert[]; kind: Kind }) {
  return (
    <section className="stack">
      <Heading as="h2">Daily new or price-dropped alerts</Heading>
      <p>
        Legacy collection criteria: at least 5 comparables, estimated profit ≥{" "}
        {kind === "bikes" ? "€300" : "€100"} and ROI ≥ 15%, no hard risk flags.
        This uses the collector’s dated default assumptions, separately from
        your editable cost estimates.
      </p>
      {!items.length ? (
        <Flash>
          No qualifying new or price-dropped listings were observed today.
        </Flash>
      ) : (
        <div className="cards">
          {items.map((item) => (
            <article className="panel stack" key={item.id}>
              <Heading as="h3">
                <Link href={safeUrl(item.url)}>{item.name}</Link>
              </Heading>
              <p>
                {money(item.price)} ask · {money(item.reference_price)}{" "}
                reference · {item.comparables} comparables ({item.confidence})
              </p>
              <p>
                {money(item.estimated_profit)} estimated profit ·{" "}
                {number(item.roi_percent)}% ROI
              </p>
              <p>
                {item.reason} · {item.country}
              </p>
              <p>{item.risk_flags.join(", ") || "No risk flags observed"}</p>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
