import { useEffect, useMemo, useRef, useState } from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
  type QueryClient,
} from "@tanstack/react-query";
import { useNavigate, useSearch } from "@tanstack/react-router";
import {
  Button,
  FormControl,
  TextInput,
  Select,
  Flash,
  Spinner,
  Heading,
  Label,
  Link,
} from "@f0rge/primer";
import { ApiFailure } from "@f0rge/primer/api";
import { api, type Listing } from "./api/client";
import { IdentitySession } from "./api/session";
import { numericFilters, type BrowserState, type Kind } from "./state";
import { money, number, returns, safeUrl } from "./format";
import { SavedData } from "./SavedData";
import { Insights, Alerts } from "./Insights";
import { ImportView } from "./ImportView";

const confidence: Record<string, number> = {
  none: 0,
  low: 1,
  medium: 2,
  high: 3,
};
const hardRisk = [
  "too-good-to-be-true",
  "implausibly low price",
  "zero-review seller",
];
type Enriched = Listing & {
  profit: number | null;
  roi: number | null;
  next_up_days: number | null;
  distance_km?: number | null;
  price_drop_percent?: number | null;
  price_reduced?: boolean;
};
function ErrorNotice({
  error,
  reload,
}: {
  error: unknown;
  reload: () => void;
}) {
  const failure = error instanceof ApiFailure ? error : undefined;
  return (
    <Flash variant="danger">
      <div role="alert">
        <strong>
          {failure?.conflict
            ? "Your data changed in another session."
            : (failure?.message ?? "Buycycle could not load this view.")}
        </strong>
        {failure?.conflict && (
          <p>
            Your draft has been kept on this page. Reload the saved version,
            compare it with your draft and retry deliberately.
          </p>
        )}
        {failure?.errorId && <p>Reference: {failure.errorId}</p>}
        <Button onClick={reload}>
          {failure?.conflict ? "Reload saved version" : "Retry"}
        </Button>
      </div>
    </Flash>
  );
}
export function App() {
  const client = useQueryClient();
  // This uncached identity probe establishes a subject before any private queries.
  const identity = useQuery({
    queryKey: ["buycycle", "identity"],
    queryFn: async ({ signal }) => (await api.status(signal)).identity.subject,
    staleTime: 0,
    gcTime: 0,
    refetchInterval: 60000,
    refetchOnWindowFocus: "always",
  });
  const current = useRef<IdentitySession | null>(null);
  const [session, setSession] = useState<IdentitySession | null>(null);
  const [denied, setDenied] = useState<ApiFailure | null>(null);
  useEffect(() => {
    const nextSubject = identity.data;
    const denial =
      identity.error instanceof ApiFailure && identity.error.denied
        ? identity.error
        : null;
    if (
      denial ||
      (nextSubject &&
        (!current.current?.active || current.current.subject !== nextSubject))
    ) {
      current.current?.invalidate();
      clearPrivateState(client);
      const next =
        denial || !nextSubject ? null : new IdentitySession(nextSubject);
      current.current = next;
      setSession(next);
      setDenied(denial);
    }
  }, [identity.data, identity.dataUpdatedAt, identity.error, client]);
  useEffect(
    () => () => {
      current.current?.invalidate();
    },
    [],
  );
  if (denied || (identity.error instanceof ApiFailure && identity.error.denied))
    return <PrivateDenied failure={denied ?? (identity.error as ApiFailure)} />;
  if (!session?.active || session.subject !== identity.data)
    return (
      <main className="shell">
        <Heading as="h1">Buycycle</Heading>
        <div role="status">
          <Spinner aria-label="Loading private workspace" /> Loading your
          private workspace…
        </div>
        {identity.error && (
          <ErrorNotice
            error={identity.error}
            reload={() => {
              void identity.refetch();
            }}
          />
        )}
      </main>
    );
  return (
    <Workspace
      key={session.epoch}
      session={session}
      onDenied={(failure) => {
        if (current.current !== session) return;
        current.current?.invalidate();
        current.current = null;
        clearPrivateState(client);
        setSession(null);
        setDenied(failure);
        void identity.refetch();
      }}
    />
  );
}
function clearPrivateState(client: QueryClient) {
  void client.cancelQueries({ queryKey: ["buycycle", "private"] });
  client.removeQueries({ queryKey: ["buycycle", "private"] });
  for (const mutation of client.getMutationCache().getAll()) {
    if (mutation.options.mutationKey?.[0] === "buycycle")
      client.getMutationCache().remove(mutation);
  }
}
function PrivateDenied({ failure }: { failure: ApiFailure }) {
  return (
    <main className="shell stack">
      <Heading as="h1">Private Buycycle</Heading>
      <Flash variant="danger">
        <p role="alert">
          {failure.status === 403
            ? "This account is not approved for Buycycle."
            : "Sign in with your approved email to view Buycycle."}
        </p>
      </Flash>
      <Link href="/cdn-cgi/access/login">
        Sign in through Cloudflare Access
      </Link>
      <p>No listing or saved account data is shown while access is denied.</p>
    </main>
  );
}
function Workspace({
  session,
  onDenied,
}: {
  session: IdentitySession;
  onDenied: (failure: ApiFailure) => void;
}) {
  const search = useSearch({ strict: false });
  const navigate = useNavigate();
  const kind: Kind = search.kind === "wheels" ? "wheels" : "bikes";
  const page = search.page ?? "deals";
  const change = (key: string, value: string) => {
    void navigate({
      to: "/",
      search: (previous) =>
        Object.fromEntries(
          Object.entries({ ...previous, [key]: value }).filter(
            (entry): entry is [string, string] => typeof entry[1] === "string",
          ),
        ),
    });
  };
  const subject = session.subject;
  const status = useQuery({
    queryKey: ["buycycle", "private", session.epoch, subject, "status"],
    queryFn: ({ signal }) => api.privateStatus(session, signal),
    refetchInterval: 60000,
  });
  const stateKey = ["buycycle", "private", session.epoch, subject, "state"];
  const state = useQuery({
    queryKey: stateKey,
    queryFn: ({ signal }) => api.state(session, signal),
  });
  const listings = useQuery({
    queryKey: ["buycycle", "private", session.epoch, subject, "listings", kind],
    queryFn: ({ signal }) => api.listings(kind, session, signal),
  });
  const client = useQueryClient();
  const [failure, setFailure] = useState<unknown>(null);
  const [notice, setNotice] = useState("");
  const mutation = useMutation({
    mutationKey: ["buycycle", "private", session.epoch, "state-write"],
    mutationFn: async (next: BrowserState) => {
      if (!state.data) throw new Error("Saved data not loaded");
      const actor = session;
      actor.assertActive();
      return api.save(
        { expected_revision: state.data.revision, state: next },
        actor,
      );
    },
    onSuccess: (result) => {
      if (!session.active) return;
      client.setQueryData(stateKey, result);
      setFailure(null);
      setNotice("Saved.");
    },
    onError: (error) => {
      if (!session.active) return;
      setFailure(error);
      setNotice("");
    },
  });
  const denied = [status.error, state.error, listings.error, failure].find(
    (error) => error instanceof ApiFailure && error.denied,
  );
  useEffect(() => {
    if (denied instanceof ApiFailure) onDenied(denied);
  }, [denied, onDenied]);
  const category = state.data?.state[kind];
  const rows = useMemo<Enriched[]>(
    () =>
      listings.data && category
        ? listings.data.items.map((item) => ({
            ...item,
            ...returns(item, category.costs),
            next_up_days: item.next_up?.days_listed ?? null,
          }))
        : [],
    [listings.data, category],
  );
  const filtered = useMemo(() => {
    const q = (search.q ?? "")
      .toLocaleLowerCase()
      .trim()
      .split(/\s+/)
      .filter(Boolean);
    const result = rows.filter(
      (item) =>
        !item.gone_at &&
        q.every((term) =>
          `${item.name} ${item.brand} ${item.model} ${item.country} ${item.brake} ${item.rim_material}`
            .toLowerCase()
            .includes(term),
        ) &&
        (!search.brand || item.brand === search.brand) &&
        (!search.country || item.country === search.country) &&
        (!search.size ||
          item.size?.toLowerCase().includes(search.size.toLowerCase())) &&
        (!search.brake || item.brake === search.brake) &&
        (!search.rim_material || item.rim_material === search.rim_material) &&
        (!search.wheel_system || item.wheel_system === search.wheel_system) &&
        (!search.conf ||
          (confidence[item.confidence] ?? 0) >=
            (confidence[search.conf] ?? 0)) &&
        (search.risk === "all" ||
          (search.risk === "none"
            ? !item.risk_flags.length
            : !item.risk_flags.some((flag) => hardRisk.includes(flag)))) &&
        (!search.flex ||
          (search.flex === "pr"
            ? item.price_reduced
            : search.flex === "drop"
              ? (item.price_drop_percent ?? 0) > 0
              : item.price_reduced || (item.price_drop_percent ?? 0) > 0)) &&
        numericFilters.every((filter) => {
          const threshold = search[filter.key];
          if (!threshold) return true;
          const numeric = Number(threshold);
          const value = item[filter.field];
          return (
            Number.isFinite(numeric) &&
            typeof value === "number" &&
            (filter.direction === "min" ? value >= numeric : value <= numeric)
          );
        }),
    );
    const key = search.sort ?? "profit";
    const asc = search.asc === "1";
    return result.sort((a, b) => {
      const av = a[key as keyof Enriched];
      const bv = b[key as keyof Enriched];
      if (av == null) return bv == null ? 0 : 1;
      if (bv == null) return -1;
      const order =
        typeof av === "number" && typeof bv === "number"
          ? av - bv
          : String(av).localeCompare(String(bv));
      return asc ? order : -order;
    });
  }, [rows, search]);
  const [limit, setLimit] = useState(100);
  const save = async (next: BrowserState) => {
    await mutation.mutateAsync(next);
  };
  const update = (updater: (draft: BrowserState) => void) => {
    if (!state.data) return;
    const next = structuredClone(state.data.state);
    updater(next);
    void save(next).catch(() => undefined);
  };
  const reload = () => {
    setFailure(null);
    void state.refetch();
    void listings.refetch();
    void status.refetch();
  };
  if (denied)
    return (
      <main className="shell stack">
        <Heading as="h1">Private Buycycle</Heading>
        <Flash variant="danger">
          <p role="alert">
            {denied instanceof ApiFailure && denied.status === 403
              ? "This account is not approved for Buycycle."
              : "Sign in with your approved email to view Buycycle."}
          </p>
        </Flash>
        <Link href="/cdn-cgi/access/login">
          Sign in through Cloudflare Access
        </Link>
        <p>No listing or saved account data is shown while access is denied.</p>
      </main>
    );
  if (status.isPending || state.isPending)
    return (
      <main className="shell">
        <Heading as="h1">Buycycle</Heading>
        <div role="status">
          <Spinner aria-label="Loading private workspace" /> Loading your
          private workspace…
        </div>
        {status.error && <ErrorNotice error={status.error} reload={reload} />}
      </main>
    );
  return (
    <>
      <a className="skip" href="#main">
        Skip to content
      </a>
      <main className="shell stack" id="main">
        <header>
          <div>
            <Heading as="h1">Buycycle deal finder</Heading>
            <p className="muted">
              Private workspace · Bikes and wheelsets · Asking prices are not
              realised sale prices
            </p>
          </div>
          <div className="row">
            <FormControl>
              <FormControl.Label>Category</FormControl.Label>
              <Select
                value={kind}
                onChange={(event) => change("kind", event.target.value)}
              >
                <Select.Option value="bikes">Bikes</Select.Option>
                <Select.Option value="wheels">Wheelsets</Select.Option>
              </Select>
            </FormControl>
            <Link href="/cdn-cgi/access/logout">Sign out</Link>
          </div>
        </header>
        <nav aria-label="Workspace sections">
          {[
            ["deals", "Deals"],
            ["insights", "Insights"],
            ["alerts", "Daily alerts"],
            ["watch", "Watchlist and trades"],
            ["costs", "Cost assumptions"],
            ["import", "Bring saved data"],
            ["status", "Collection status"],
            ["method", "Method"],
          ].map(([value, label]) => (
            <Button
              key={value}
              aria-current={page === value ? "page" : undefined}
              variant={page === value ? "primary" : "default"}
              onClick={() => change("page", value ?? "deals")}
            >
              {label}
            </Button>
          ))}
        </nav>
        {(failure || state.error || listings.error || status.error) && (
          <ErrorNotice
            error={failure || state.error || listings.error || status.error}
            reload={reload}
          />
        )}
        {notice && (
          <Flash variant="success">
            <span role="status">{notice}</span>
          </Flash>
        )}
        {status.data?.stale && (
          <Flash variant="warning">
            The collection is stale. Showing the last available observations;
            missing values are not estimates.
          </Flash>
        )}
        {status.data?.blocked && (
          <Flash variant="warning">
            Collection is safely paused after a blocked or uncertain request. Do
            not reset the safety ledger to resume it.
          </Flash>
        )}
        {status.data?.status === "partial" && (
          <Flash variant="warning">
            <span role="status">
              The latest collection is partial or interrupted. Some detail
              requests failed; retain the last good observations and treat
              missing data as unobserved.
            </span>
          </Flash>
        )}
        {!!listings.data?.quarantined?.length && (
          <Flash variant="warning">
            <div role="status">
              <strong>
                {listings.data.quarantined.length} source listing(s) excluded
                from estimates.
              </strong>
              <p>
                Their asking prices are missing or invalid. No zero price was
                invented; the original records and history remain retained for
                reconciliation.
              </p>
              <details>
                <summary>Review excluded source IDs</summary>
                <ul>
                  {listings.data.quarantined.map((item) => (
                    <li key={item.id}>
                      {item.id} — missing or invalid asking price
                    </li>
                  ))}
                </ul>
              </details>
            </div>
          </Flash>
        )}
        {state.data && category && page === "deals" && (
          <div className="grid">
            <details className="panel filters" open>
              <summary>Search and filters</summary>
              <div className="stack">
                <FormControl>
                  <FormControl.Label>Search model or brand</FormControl.Label>
                  <TextInput
                    block
                    value={search.q ?? ""}
                    onChange={(event) => change("q", event.target.value)}
                  />
                </FormControl>
                {(
                  [
                    "brand",
                    "country",
                    "brake",
                    "rim_material",
                    "wheel_system",
                  ] as const
                ).map((key) => (
                  <FormControl key={key}>
                    <FormControl.Label>
                      {key === "rim_material"
                        ? "Rim material"
                        : key === "wheel_system"
                          ? "Tyre system"
                          : key[0]?.toUpperCase() + key.slice(1)}
                    </FormControl.Label>
                    <Select
                      value={search[key] ?? ""}
                      onChange={(event) => change(key, event.target.value)}
                    >
                      <Select.Option value="">All</Select.Option>
                      {[...new Set(rows.map((row) => row[key]).filter(Boolean))]
                        .sort()
                        .map((value) => (
                          <Select.Option key={value} value={value}>
                            {value}
                          </Select.Option>
                        ))}
                    </Select>
                  </FormControl>
                ))}
                <FormControl>
                  <FormControl.Label>Size contains</FormControl.Label>
                  <TextInput
                    block
                    value={search.size ?? ""}
                    onChange={(event) => change("size", event.target.value)}
                  />
                </FormControl>
                <FormControl>
                  <FormControl.Label>Comparables confidence</FormControl.Label>
                  <Select
                    value={search.conf ?? ""}
                    onChange={(event) => change("conf", event.target.value)}
                  >
                    {["", "low", "medium", "high"].map((value) => (
                      <Select.Option key={value} value={value}>
                        {value || "Any"}
                      </Select.Option>
                    ))}
                  </Select>
                </FormControl>
                <FormControl>
                  <FormControl.Label>Risk flags</FormControl.Label>
                  <Select
                    value={search.risk ?? ""}
                    onChange={(event) => change("risk", event.target.value)}
                  >
                    <Select.Option value="">Hide hard risk</Select.Option>
                    <Select.Option value="all">Show all</Select.Option>
                    <Select.Option value="none">No flags</Select.Option>
                  </Select>
                </FormControl>
                <FormControl>
                  <FormControl.Label>Seller flexibility</FormControl.Label>
                  <Select
                    value={search.flex ?? ""}
                    onChange={(event) => change("flex", event.target.value)}
                  >
                    <Select.Option value="">Any</Select.Option>
                    <Select.Option value="pr">Price reduced flag</Select.Option>
                    <Select.Option value="drop">
                      Observed price drop
                    </Select.Option>
                    <Select.Option value="any">Either signal</Select.Option>
                  </Select>
                </FormControl>
                <details>
                  <summary>Price, return, sample size and age</summary>
                  <div className="stack">
                    {numericFilters.map((filter) => (
                      <FormControl key={filter.key}>
                        <FormControl.Label>{filter.label}</FormControl.Label>
                        <TextInput
                          block
                          type="number"
                          value={search[filter.key] ?? ""}
                          onChange={(event) =>
                            change(filter.key, event.target.value)
                          }
                        />
                      </FormControl>
                    ))}
                  </div>
                </details>
                <Button
                  onClick={() => {
                    void navigate({ to: "/", search: { kind, page: "deals" } });
                  }}
                >
                  Reset filters
                </Button>
                <p className="muted">
                  Filters and sort are kept in this private URL for bookmarking.
                </p>
              </div>
            </details>
            <section className="stack" aria-label="Deals">
              <div className="row between">
                <Heading as="h2">{filtered.length} matching listings</Heading>
                <div className="row">
                  <FormControl>
                    <FormControl.Label>Sort by</FormControl.Label>
                    <Select
                      value={search.sort ?? "profit"}
                      onChange={(event) => change("sort", event.target.value)}
                    >
                      {[
                        ["profit", "Profit"],
                        ["roi", "ROI"],
                        ["price", "Price"],
                        ["average_ask", "Average ask"],
                        ["comparables", "Comparables"],
                        ["days_listed", "Days listed"],
                        ["z_score", "Z-score"],
                        ["cut_per_day", "€/day cut"],
                        ["sold_percent", "Disappeared within 30d"],
                        ["versus_typical", "Days vs typical"],
                        ["next_up_days", "Next-up days"],
                      ].map(([key, label]) => (
                        <Select.Option key={key} value={key ?? "profit"}>
                          {label}
                        </Select.Option>
                      ))}
                    </Select>
                  </FormControl>
                  <Button
                    onClick={() =>
                      change("asc", search.asc === "1" ? "0" : "1")
                    }
                  >
                    {search.asc === "1" ? "Ascending" : "Descending"}
                  </Button>
                </div>
              </div>
              {listings.isFetching && (
                <span role="status">Refreshing observations…</span>
              )}
              {!filtered.length && !listings.isPending ? (
                <Flash>
                  No listings match these filters. Reset filters or switch
                  category.
                </Flash>
              ) : (
                <div className="cards">
                  {filtered.slice(0, limit).map((item) => (
                    <Deal
                      key={item.id}
                      item={item}
                      watched={!!category.watch[item.id]}
                      pending={mutation.isPending}
                      watch={() =>
                        update((draft) => {
                          const watches = draft[kind].watch;
                          if (watches[item.id]) delete watches[item.id];
                          else
                            watches[item.id] = {
                              n: item.name,
                              u: item.url,
                              p: item.price,
                              t: new Date().toISOString().slice(0, 10),
                            };
                        })
                      }
                      all={rows}
                    />
                  ))}
                </div>
              )}
              {limit < filtered.length && (
                <Button onClick={() => setLimit(limit + 100)}>
                  Show 100 more
                </Button>
              )}
              <p className="muted">
                {listings.data?.active ?? 0} priced active ·{" "}
                {listings.data?.gone ?? 0} priced disappeared · Data generated{" "}
                {listings.data?.generated ?? "not yet"}
              </p>
            </section>
          </div>
        )}
        {page === "insights" && (
          <Insights
            rows={filtered}
            allRows={rows}
            models={listings.data?.models ?? []}
          />
        )}
        {page === "alerts" && (
          <Alerts items={listings.data?.alerts ?? []} kind={kind} />
        )}
        {state.data && ["watch", "costs"].includes(page) && (
          <SavedData
            key={`${kind}-${page}`}
            kind={kind}
            page={page}
            stored={state.data}
            rows={rows}
            save={save}
            pending={mutation.isPending}
          />
        )}
        {state.data && page === "import" && (
          <ImportView
            stored={state.data}
            kind={kind}
            session={session}
            onDenied={onDenied}
            saved={(result) => {
              if (!session.active) return;
              client.setQueryData(stateKey, result);
              setNotice(
                "Imported saved data. The original document is retained in the server archive.",
              );
            }}
          />
        )}
        {page === "status" && status.data && (
          <section className="panel stack">
            <Heading as="h2">Collection status</Heading>
            <dl className="metrics">
              <div>
                <dt>Last successful collection</dt>
                <dd>{status.data.last_success ?? "Not observed"}</dd>
              </div>
              <div>
                <dt>Daily detail attempts</dt>
                <dd>
                  {status.data.detail_attempts} / {status.data.detail_limit}
                </dd>
              </div>
              <div>
                <dt>Status</dt>
                <dd>
                  {status.data.blocked ? "Safely paused" : status.data.status}
                </dd>
              </div>
              <div>
                <dt>Version</dt>
                <dd>{status.data.version}</dd>
              </div>
            </dl>
            <p>
              At least 1.6 seconds between feeds and 2.2 seconds between detail
              requests. Failed attempts count. A 403/429 persists the block,
              backs off once for 120 seconds, then stops for the Luxembourg day.
            </p>
            <p>
              Missing or uncertain prior usage holds collection. The interface
              cannot bypass quota, reset the ledger or start an unsafe rerun.
            </p>
          </section>
        )}
        {page === "method" && (
          <section className="panel stack">
            <Heading as="h2">How to interpret the data</Heading>
            <p>
              Comparables exclude the listing itself and disappeared listings.
              Bikes match brand/model and year ±1 when known; wheelsets also
              match brake and rim material. The reference is the eligible median
              with at least three comparables; average ask is separate.
            </p>
            <p>
              Z-score is missing below two comparables or zero spread. Values
              with fewer than five comparables have limited evidence.
              Disappeared means sold or withdrawn, never a confirmed sale.
              Disappearance share and typical disappearance time require at
              least five eligible observations.
            </p>
            <p>
              Next up is the lowest strictly higher eligible asking price. Its
              age is a lower bound where marked. No reference, history or
              comparator means “Not observed”, not zero.
            </p>
            <p>
              Profit and ROI use the reference and your saved cost assumptions.
              Assumptions are editable estimates rather than current fee advice.
              History begins when collection started.
            </p>
          </section>
        )}
      </main>
    </>
  );
}
function Deal({
  item,
  watched,
  pending,
  watch,
  all,
}: {
  item: Enriched;
  watched: boolean;
  pending: boolean;
  watch: () => void;
  all: Enriched[];
}) {
  const comparable = all.filter(
    (other) =>
      other.id !== item.id &&
      !other.gone_at &&
      other.brand.toLowerCase() === item.brand.toLowerCase() &&
      other.model === item.model &&
      other.brake === item.brake &&
      other.rim_material === item.rim_material &&
      (item.kind === "wheels" ||
        item.year == null ||
        other.year == null ||
        Math.abs(item.year - other.year) <= 1),
  );
  return (
    <article className="panel stack">
      <div className="row between">
        <Heading as="h3">
          {safeUrl(item.url) ? (
            <Link
              href={safeUrl(item.url)}
              target="_blank"
              rel="noopener noreferrer"
            >
              {item.name}
            </Link>
          ) : (
            item.name
          )}
        </Heading>
        <Button onClick={watch} disabled={pending} aria-pressed={watched}>
          {watched ? "Remove watch" : "Watch"}
        </Button>
      </div>
      <p className="muted">
        {item.brand} {item.model} · {item.year ?? "Year unknown"} ·{" "}
        {item.size ?? "Size unknown"} · {item.country || "Country unknown"}
      </p>
      <div className="row">
        <Label>
          {item.confidence} confidence · {item.comparables} comps
        </Label>
        {item.risk_flags.map((flag) => (
          <Label key={flag} variant="attention">
            {flag}
          </Label>
        ))}
      </div>
      <dl className="metrics">
        {[
          ["Asking price", money(item.price)],
          ["Reference", money(item.reference_price)],
          ["Average ask", money(item.average_ask)],
          ["Estimated profit", money(item.profit)],
          ["ROI", item.roi == null ? "Not observed" : number(item.roi) + "%"],
          ["Z-score", number(item.z_score)],
          ["€/day cut", number(item.cut_per_day)],
          [
            "Disappeared within 30d",
            item.sold_percent == null
              ? "Not observed"
              : number(item.sold_percent) + "% · n=" + item.sold_sample,
          ],
          ["Days vs typical", number(item.versus_typical)],
          ["Days listed", number(item.days_listed, 0)],
        ].map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
      <p>
        Next up:{" "}
        {item.next_up ? (
          <>
            <Link
              href={safeUrl(item.next_up.url)}
              target="_blank"
              rel="noopener noreferrer"
            >
              {money(item.next_up.price)}
            </Link>{" "}
            (+{money(item.next_up.price - item.price)}) ·{" "}
            {item.next_up.age_lower_bound ? "≥" : ""}
            {item.next_up.days_listed ?? "unknown"} days{" "}
            {item.next_up.ties ? ` · +${item.next_up.ties} ties` : ""}
          </>
        ) : item.comparables ? (
          "Priciest among observed comparables"
        ) : (
          "Not observed"
        )}
      </p>
      <details>
        <summary>Comparable listings ({comparable.length})</summary>
        <div className="table-scroll">
          <table>
            <caption>Observed asking prices; this listing is excluded</caption>
            <thead>
              <tr>
                <th>Listing</th>
                <th>Ask</th>
                <th>Days</th>
              </tr>
            </thead>
            <tbody>
              {comparable.map((other) => (
                <tr key={other.id}>
                  <td>
                    <Link href={safeUrl(other.url)}>{other.name}</Link>
                  </td>
                  <td>{money(other.price)}</td>
                  <td>{number(other.days_listed, 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
      <details>
        <summary>Price history ({item.history.length})</summary>
        {item.history.length ? (
          <ol>
            {item.history.map((point) => (
              <li key={point.day}>
                {point.day}: {money(point.price)}
              </li>
            ))}
          </ol>
        ) : (
          <p>No snapshots observed.</p>
        )}
      </details>
    </article>
  );
}
