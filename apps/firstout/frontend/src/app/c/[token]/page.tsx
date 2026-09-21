"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { useParams } from "next/navigation";

import {
  ApiError,
  beaconPublicLookbookEvents,
  formatZarAmount,
  getPublicLookbook,
  postPublicLookbookEvents,
  requestPublicLookbookQuote,
  type PublicLookbookEvent,
  type PublicLookbookItem,
} from "@/lib/api";

const HEARTS_KEY = (token: string) => `lookbook-hearts:${token}`;
const VISITOR_KEY = "lookbook-visitor-id";

function readHearts(token: string): Set<string> {
  if (typeof window === "undefined") {
    return new Set();
  }
  try {
    const raw = window.localStorage.getItem(HEARTS_KEY(token));
    if (!raw) {
      return new Set();
    }
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) {
      return new Set();
    }
    return new Set(parsed.filter((value): value is string => typeof value === "string"));
  } catch {
    return new Set();
  }
}

function writeHearts(token: string, hearts: Set<string>) {
  window.localStorage.setItem(HEARTS_KEY(token), JSON.stringify([...hearts]));
}

function visitorId(): string {
  let id = window.localStorage.getItem(VISITOR_KEY);
  if (!id || id.length < 8) {
    id = crypto.randomUUID();
    window.localStorage.setItem(VISITOR_KEY, id);
  }
  return id;
}

function skipContinuousDwell(): boolean {
  const nav = navigator as Navigator & { msDoNotTrack?: string };
  const dnt = nav.doNotTrack || nav.msDoNotTrack;
  if (dnt === "1" || dnt === "yes") {
    return true;
  }
  return window.matchMedia("(prefers-reduced-data: reduce)").matches;
}

export default function PublicLookbookPage() {
  const params = useParams<{ token: string }>();
  const token = params.token;
  const [items, setItems] = useState<PublicLookbookItem[] | null>(null);
  const [companyName, setCompanyName] = useState("");
  const [name, setName] = useState("");
  const [priceMode, setPriceMode] = useState<"retail" | "price_list" | "hidden">("retail");
  const [missing, setMissing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [heartsVersion, setHeartsVersion] = useState(0);
  const [detail, setDetail] = useState<PublicLookbookItem | null>(null);
  const [guestName, setGuestName] = useState("");
  const [contact, setContact] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);
  const pending = useRef<PublicLookbookEvent[]>([]);
  const opened = useRef(false);
  const visibleSince = useRef(new Map<string, number>());
  const hearts = useMemo(() => {
    void heartsVersion;
    return token ? readHearts(token) : new Set<string>();
  }, [token, heartsVersion]);

  const flush = useCallback(
    (useBeacon: boolean) => {
      if (!token || pending.current.length === 0) {
        return;
      }
      const events = pending.current;
      pending.current = [];
      if (useBeacon) {
        beaconPublicLookbookEvents(token, visitorId(), events);
        return;
      }
      void postPublicLookbookEvents(token, visitorId(), events).catch(() => {
        pending.current = [...events, ...pending.current];
      });
    },
    [token],
  );

  const enqueue = useCallback(
    (event: PublicLookbookEvent) => {
      pending.current = [...pending.current, event];
      if (pending.current.length >= 8) {
        flush(false);
      }
    },
    [flush],
  );

  const snapshotDwell = useCallback(() => {
    const now = Date.now();
    visibleSince.current.forEach((started, skuId) => {
      const duration = now - started;
      if (duration >= 1000) {
        enqueue({ event_type: "sku_visible", sku_id: skuId, duration_ms: duration });
      }
      visibleSince.current.set(skuId, now);
    });
  }, [enqueue]);

  useEffect(() => {
    if (!token) {
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const lookbook = await getPublicLookbook(token);
        if (cancelled) {
          return;
        }
        setCompanyName(lookbook.company_name);
        setName(lookbook.name);
        setPriceMode(lookbook.price_mode);
        setItems(lookbook.items);
      } catch (err) {
        if (cancelled) {
          return;
        }
        if (err instanceof ApiError && err.status === 404) {
          setMissing(true);
          return;
        }
        setError(err instanceof Error ? err.message : "Could not open this lookbook.");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  useEffect(() => {
    if (!token || items === null || opened.current) {
      return;
    }
    opened.current = true;
    enqueue({ event_type: "open" });
    flush(false);
  }, [enqueue, flush, items, token]);

  useEffect(() => {
    const onPageHide = () => {
      snapshotDwell();
      flush(true);
    };
    const onVisibility = () => {
      if (document.visibilityState === "hidden") {
        snapshotDwell();
        flush(true);
      }
    };
    window.addEventListener("pagehide", onPageHide);
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      window.removeEventListener("pagehide", onPageHide);
      document.removeEventListener("visibilitychange", onVisibility);
      snapshotDwell();
      flush(true);
    };
  }, [flush, snapshotDwell]);

  useEffect(() => {
    if (!items || skipContinuousDwell()) {
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        const now = Date.now();
        for (const entry of entries) {
          const skuId = entry.target.getAttribute("data-sku-id");
          if (!skuId) {
            continue;
          }
          if (entry.isIntersecting) {
            if (!visibleSince.current.has(skuId)) {
              visibleSince.current.set(skuId, now);
            }
            continue;
          }
          const started = visibleSince.current.get(skuId);
          if (started == null) {
            continue;
          }
          visibleSince.current.delete(skuId);
          const duration = now - started;
          if (duration >= 1000) {
            enqueue({ event_type: "sku_visible", sku_id: skuId, duration_ms: duration });
          }
        }
      },
      { threshold: 0.5 },
    );
    document.querySelectorAll("[data-sku-id]").forEach((node) => observer.observe(node));
    return () => {
      snapshotDwell();
      observer.disconnect();
    };
  }, [enqueue, items, snapshotDwell]);

  const toggleHeart = useCallback(
    (skuId: string) => {
      if (!token) {
        return;
      }
      const next = readHearts(token);
      const saving = !next.has(skuId);
      if (saving) {
        next.add(skuId);
      } else {
        next.delete(skuId);
      }
      writeHearts(token, next);
      setHeartsVersion((version) => version + 1);
      enqueue({ event_type: saving ? "heart" : "unheart", sku_id: skuId });
    },
    [enqueue, token],
  );

  const openDetail = useCallback(
    (item: PublicLookbookItem) => {
      setDetail(item);
      enqueue({ event_type: "sku_open", sku_id: item.sku_id });
    },
    [enqueue],
  );

  const heartCount = hearts.size;
  const grid = useMemo(() => items ?? [], [items]);
  const canQuote = priceMode !== "hidden";

  async function onSend(event: FormEvent) {
    event.preventDefault();
    if (!token || heartCount === 0) {
      return;
    }
    setFormError(null);
    setSending(true);
    try {
      await requestPublicLookbookQuote(token, {
        name: guestName.trim(),
        contact: contact.trim(),
        sku_ids: [...hearts],
      });
      setSent(true);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Could not send to the showroom.");
    } finally {
      setSending(false);
    }
  }

  if (missing) {
    return (
      <main className="lookbook-public lookbook-public--empty">
        <p>This lookbook is not available.</p>
      </main>
    );
  }

  if (error) {
    return (
      <main className="lookbook-public lookbook-public--empty">
        <p>{error}</p>
      </main>
    );
  }

  if (items === null) {
    return (
      <main className="lookbook-public lookbook-public--empty">
        <p>Loading…</p>
      </main>
    );
  }

  return (
    <main className="lookbook-public">
      <header className="lookbook-public__header">
        <p className="lookbook-public__company">{companyName}</p>
        <h1>{name}</h1>
      </header>
      <section className="lookbook-public__grid">
        {grid.map((item) => (
          <article key={item.id} className="lookbook-public__card" data-sku-id={item.sku_id}>
            <button
              type="button"
              className="lookbook-public__photo-btn"
              onClick={() => openDetail(item)}
            >
              {item.photo_path ? (
                <img src={item.photo_path} alt={item.name} />
              ) : (
                <span className="lookbook-public__placeholder" aria-hidden />
              )}
            </button>
            <div className="lookbook-public__meta">
              <h2>{item.name}</h2>
              {item.unit_inc_vat ? <p>{formatZarAmount(item.unit_inc_vat)}</p> : null}
              <button
                type="button"
                className={
                  hearts.has(item.sku_id)
                    ? "lookbook-public__heart lookbook-public__heart--on"
                    : "lookbook-public__heart"
                }
                onClick={() => toggleHeart(item.sku_id)}
                aria-pressed={hearts.has(item.sku_id)}
              >
                {hearts.has(item.sku_id) ? "Saved" : "Save"}
              </button>
            </div>
          </article>
        ))}
      </section>
      {heartCount > 0 ? (
        <div className="lookbook-public__bar">
          {sent ? (
            <p>Thanks — the showroom has your shortlist.</p>
          ) : canQuote ? (
            <form className="lookbook-public__form" onSubmit={(event) => void onSend(event)}>
              <p>
                Send {heartCount} item{heartCount === 1 ? "" : "s"} to the showroom
              </p>
              <label>
                Name
                <input
                  value={guestName}
                  onChange={(event) => setGuestName(event.target.value)}
                  required
                  autoComplete="name"
                />
              </label>
              <label>
                WhatsApp or email
                <input
                  value={contact}
                  onChange={(event) => setContact(event.target.value)}
                  required
                  minLength={3}
                  autoComplete="email"
                />
              </label>
              {formError ? <p className="lookbook-public__form-error">{formError}</p> : null}
              <button type="submit" disabled={sending || guestName.trim().length === 0 || contact.trim().length < 3}>
                {sending ? "Sending…" : "Send to the showroom"}
              </button>
            </form>
          ) : (
            <p>{heartCount} saved for the showroom</p>
          )}
        </div>
      ) : null}
      {detail ? (
        <div className="lookbook-public__detail" role="dialog" aria-modal="true">
          <button
            type="button"
            className="lookbook-public__detail-backdrop"
            aria-label="Close"
            onClick={() => setDetail(null)}
          />
          <div className="lookbook-public__detail-card">
            {detail.photo_path ? <img src={detail.photo_path} alt={detail.name} /> : null}
            <h2>{detail.name}</h2>
            {detail.unit_inc_vat ? <p>{formatZarAmount(detail.unit_inc_vat)}</p> : null}
            <button type="button" onClick={() => setDetail(null)}>
              Close
            </button>
          </div>
        </div>
      ) : null}
    </main>
  );
}
