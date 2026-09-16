"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";

import { ApiError, formatZarAmount, getPublicLookbook, type PublicLookbookItem } from "@/lib/api";

const HEARTS_KEY = (token: string) => `lookbook-hearts:${token}`;

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

export default function PublicLookbookPage() {
  const params = useParams<{ token: string }>();
  const token = params.token;
  const [items, setItems] = useState<PublicLookbookItem[] | null>(null);
  const [companyName, setCompanyName] = useState("");
  const [name, setName] = useState("");
  const [missing, setMissing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [heartsVersion, setHeartsVersion] = useState(0);
  const [detail, setDetail] = useState<PublicLookbookItem | null>(null);
  const hearts = useMemo(() => {
    void heartsVersion;
    return token ? readHearts(token) : new Set<string>();
  }, [token, heartsVersion]);

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

  const toggleHeart = useCallback(
    (skuId: string) => {
      if (!token) {
        return;
      }
      const next = readHearts(token);
      if (next.has(skuId)) {
        next.delete(skuId);
      } else {
        next.add(skuId);
      }
      writeHearts(token, next);
      setHeartsVersion((version) => version + 1);
    },
    [token],
  );

  const heartCount = hearts.size;
  const grid = useMemo(() => items ?? [], [items]);

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
          <article key={item.id} className="lookbook-public__card">
            <button
              type="button"
              className="lookbook-public__photo-btn"
              onClick={() => setDetail(item)}
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
        <div className="lookbook-public__bar">{heartCount} saved for the showroom</div>
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
