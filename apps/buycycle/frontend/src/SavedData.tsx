import { useState } from "react";
import { Button, Heading, Flash, Link } from "@f0rge/primer";
import { usePrimerForm } from "@f0rge/primer/forms";
import { ApiFailure } from "@f0rge/primer/api";
import type { StateResponse, Listing } from "./api/client";
import {
  costLabels,
  downloadJson,
  type BrowserState,
  type Category,
  type Kind,
} from "./state";
import { money, safeUrl } from "./format";

type Trade = Category["log"][number];
export function SavedData({
  kind,
  page,
  stored,
  rows,
  save,
  pending,
}: {
  kind: Kind;
  page: string;
  stored: StateResponse;
  rows: Listing[];
  save: (next: BrowserState) => Promise<void>;
  pending: boolean;
}) {
  const [editing, setEditing] = useState<number | null>(null);
  const category = stored.state[kind];
  const apply = async (change: (next: BrowserState) => void) => {
    const next = structuredClone(stored.state);
    change(next);
    await save(next);
  };
  return (
    <section className="stack">
      <div className="row between">
        <Heading as="h2">
          {page === "costs"
            ? "Cost assumptions"
            : "Watchlist and trade records"}{" "}
          · {kind}
        </Heading>
        <Button
          onClick={() =>
            downloadJson(
              { version: 1, ...stored.state },
              "buycycle-saved-data.json",
            )
          }
        >
          Export all saved data
        </Button>
      </div>
      {page === "costs" ? (
        <CostForm
          key={kind}
          costs={category.costs}
          save={(costs) =>
            apply((next) => {
              next[kind].costs = costs;
            })
          }
        />
      ) : (
        <>
          <section className="panel stack">
            <Heading as="h3">Watchlist</Heading>
            {Object.entries(category.watch).length ? (
              Object.entries(category.watch).map(([id, watch]) => (
                <div key={id} className="row between">
                  <div>
                    <Link href={safeUrl(watch.u)}>{watch.n}</Link>
                    <p className="muted">
                      Added {watch.t} at {money(watch.p)} · now{" "}
                      {money(rows.find((row) => row.id === id)?.price)}
                    </p>
                  </div>
                  <Button
                    disabled={pending}
                    onClick={() => {
                      void apply((next) => {
                        delete next[kind].watch[id];
                      }).catch(() => undefined);
                    }}
                  >
                    Remove {watch.n}
                  </Button>
                </div>
              ))
            ) : (
              <Flash>
                Your watchlist is empty. Choose Watch on a listing to follow it.
              </Flash>
            )}
          </section>
          <section className="panel stack">
            <Heading as="h3">Bought and sold log</Heading>
            <TradeForm
              key={editing === null ? "new" : `edit-${editing}`}
              initial={editing === null ? undefined : category.log[editing]}
              save={async (trade) => {
                await apply((next) => {
                  if (editing === null) next[kind].log.push(trade);
                  else next[kind].log[editing] = trade;
                });
                setEditing(null);
              }}
              cancel={editing === null ? undefined : () => setEditing(null)}
            />
            {category.log.length ? (
              <div className="table-scroll">
                <table>
                  <caption>
                    Personal records; realised profit is sale minus purchase
                    price
                  </caption>
                  <thead>
                    <tr>
                      <th>Item</th>
                      <th>Purchase</th>
                      <th>Sale</th>
                      <th>Realised profit</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {category.log.map((trade, index) => (
                      <tr key={trade.id ?? index}>
                        <td>
                          {safeUrl(trade.url) ? (
                            <Link href={safeUrl(trade.url)}>{trade.name}</Link>
                          ) : (
                            trade.name
                          )}
                        </td>
                        <td>
                          {money(trade.buy)} · {trade.bd}
                        </td>
                        <td>
                          {trade.sell
                            ? `${money(trade.sell)} · ${trade.sd ?? ""}`
                            : "Unsold"}
                        </td>
                        <td>
                          {trade.sell
                            ? money(trade.sell - trade.buy)
                            : "Not realised"}
                        </td>
                        <td>
                          <div className="row">
                            <Button
                              disabled={pending}
                              onClick={() => setEditing(index)}
                            >
                              Edit {trade.name}
                            </Button>
                            <Button
                              disabled={pending}
                              variant="danger"
                              onClick={() => {
                                if (
                                  window.confirm(
                                    `Delete the saved trade “${trade.name}”? Export a backup first if needed.`,
                                  )
                                )
                                  void apply((next) => {
                                    next[kind].log.splice(index, 1);
                                  }).catch(() => undefined);
                              }}
                            >
                              Delete {trade.name}
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <Flash>No trade records yet.</Flash>
            )}
          </section>
        </>
      )}
    </section>
  );
}
function TradeForm({
  initial,
  save,
  cancel,
}: {
  initial?: Trade;
  save: (trade: Trade) => Promise<void>;
  cancel?: () => void;
}) {
  const [error, setError] = useState<unknown>(null);
  const form = usePrimerForm({
    defaultValues: {
      name: initial?.name ?? "",
      url: initial?.url ?? "",
      buy: initial ? String(initial.buy) : "",
      bd: initial?.bd ?? "",
      sell: initial?.sell == null ? "" : String(initial.sell),
      sd: initial?.sd ?? "",
    },
    onSubmit: async ({ value }) => {
      setError(null);
      try {
        await save({
          ...initial,
          id: initial?.id ?? crypto.randomUUID(),
          name: value.name.trim(),
          url: value.url,
          buy: Number(value.buy),
          bd: value.bd,
          sell: value.sell === "" ? null : Number(value.sell),
          sd: value.sd || null,
        });
        if (!initial) form.reset();
      } catch (failure) {
        setError(failure);
      }
    },
  });
  const labels = {
    name: "Item name",
    url: "Listing URL",
    buy: "Purchase price €",
    bd: "Purchase date",
    sell: "Sale price € (optional)",
    sd: "Sale date (optional)",
  };
  return (
    <form.AppForm>
      <form
        className="stack"
        onSubmit={(event) => {
          event.preventDefault();
          void form.handleSubmit();
        }}
      >
        <div className="form-grid">
          {(Object.keys(labels) as (keyof typeof labels)[]).map((key) => (
            <form.AppField
              key={key}
              name={key}
              validators={{
                onChange: ({ value }) =>
                  key === "name" && !value.trim()
                    ? "Name is required."
                    : ["buy", "sell"].includes(key) &&
                        value !== "" &&
                        (!Number.isFinite(Number(value)) || Number(value) < 0)
                      ? "Enter a finite non-negative amount."
                      : key === "buy" && !value
                        ? "Purchase price is required."
                        : key === "url" && value && !safeUrl(value)
                          ? "Enter an HTTP or HTTPS listing URL."
                          : undefined,
              }}
            >
              {(field) => (
                <field.TextField
                  label={labels[key]}
                  type={
                    ["buy", "sell"].includes(key)
                      ? "number"
                      : ["bd", "sd"].includes(key)
                        ? "date"
                        : key === "url"
                          ? "url"
                          : "text"
                  }
                  required={key === "name" || key === "buy"}
                  serverError={
                    error instanceof ApiFailure
                      ? error.fields.find(
                          (issue) =>
                            issue.field === key ||
                            issue.field.endsWith("." + key),
                        )?.message
                      : undefined
                  }
                />
              )}
            </form.AppField>
          ))}
        </div>
        {error !== null && (
          <Flash variant="danger">
            <span role="alert">
              {error instanceof Error
                ? error.message
                : "Unable to save this trade."}
            </span>
          </Flash>
        )}
        <div className="row">
          <form.SubmitButton>
            {initial ? "Update trade" : "Add trade"}
          </form.SubmitButton>
          {cancel && <Button onClick={cancel}>Cancel edit</Button>}
        </div>
      </form>
    </form.AppForm>
  );
}
function CostForm({
  costs,
  save,
}: {
  costs: Category["costs"];
  save: (costs: Category["costs"]) => Promise<void>;
}) {
  const [error, setError] = useState<unknown>(null);
  const [saved, setSaved] = useState(false);
  const form = usePrimerForm({
    defaultValues: Object.fromEntries(
      Object.entries(costs).map(([key, value]) => [key, String(value)]),
    ),
    onSubmit: async ({ value }) => {
      setError(null);
      setSaved(false);
      try {
        await save(
          Object.fromEntries(
            Object.entries(value).map(([key, amount]) => [key, Number(amount)]),
          ),
        );
        setSaved(true);
      } catch (failure) {
        setError(failure);
      }
    },
  });
  return (
    <form.AppForm>
      <form
        className="panel stack"
        onSubmit={(event) => {
          event.preventDefault();
          void form.handleSubmit();
        }}
      >
        <p>
          These are your assumptions, not current fee advice. Profit uses the
          comparable median less the negotiation haircut, then subtracts all
          purchase, resale and fixed costs.
        </p>
        <div className="form-grid">
          {Object.keys(costs).map((key) => (
            <form.AppField
              key={key}
              name={key}
              validators={{
                onChange: ({ value }) =>
                  !Number.isFinite(Number(value)) || Number(value) < 0
                    ? "Enter a finite non-negative amount."
                    : ["bp", "pay", "haircut", "sellfee"].includes(key) &&
                        Number(value) > 100
                      ? "Percentage must be at most 100."
                      : undefined,
              }}
            >
              {(field) => (
                <field.TextField
                  label={costLabels[key] ?? `${key} (imported assumption)`}
                  type="number"
                  required
                  serverError={
                    error instanceof ApiFailure
                      ? error.fields.find((issue) =>
                          issue.field.endsWith("." + key),
                        )?.message
                      : undefined
                  }
                />
              )}
            </form.AppField>
          ))}
        </div>
        {error !== null && (
          <Flash variant="danger">
            <span role="alert">
              {error instanceof Error
                ? error.message
                : "Unable to save assumptions."}
            </span>
          </Flash>
        )}
        {saved && (
          <Flash variant="success">
            <span role="status">Cost assumptions saved.</span>
          </Flash>
        )}
        <form.SubmitButton>Save cost assumptions</form.SubmitButton>
      </form>
    </form.AppForm>
  );
}
