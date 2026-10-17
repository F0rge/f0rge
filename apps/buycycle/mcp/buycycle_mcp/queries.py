"""Read-only listing queries. Net margin uses tracker/fees.py and is labelled estimate."""

from __future__ import annotations

import os
import statistics
import time
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

import fees
import market

from buycycle_mcp.db import db_path, readonly_db

LUX = ZoneInfo("Europe/Luxembourg")
MAX_LIMIT = 50
SORTS = ("net_margin", "price", "days_on_market", "price_drop_percent", "brand")
_LISTING_SQL = """
select l.*,
       d.country as dcountry, d.city, d.seller_reviews, d.seller_rating, d.member_since,
       d.status as dstatus, d.fetched, d.n_images, d.badge
from listing l
left join detail d on d.id = l.id
where l.kind = ?
"""
# country_map.country is selected separately so it cannot clash with detail.country.
_COUNTRY_SQL = "select cid, country from country_map"


def luxembourg_today(now: Optional[datetime] = None) -> str:
    current = now or datetime.now(LUX)
    if current.tzinfo is None:
        current = current.replace(tzinfo=LUX)
    return current.astimezone(LUX).date().isoformat()


def normalize_kind(kind: Optional[str]) -> Optional[str]:
    if kind is None or not str(kind).strip():
        return None
    key = str(kind).strip().lower()
    if key in ("bike", "bikes"):
        return "bikes"
    if key in ("wheel", "wheels", "wheelset", "wheelsets"):
        return "wheels"
    raise ValueError("kind must be bike or wheels")


def clamp_limit(limit: int) -> int:
    return max(1, min(int(limit), MAX_LIMIT))


def _blank(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _country(row: dict, country_map: dict) -> str:
    return row.get("dcountry") or country_map.get(row.get("country_id")) or ""


def _days_on_market(row: dict, now: float) -> Optional[float]:
    if row.get("activated_at"):
        start = float(row["activated_at"])
    elif row.get("first_seen"):
        start = datetime.fromisoformat(row["first_seen"]).timestamp()
    else:
        return None
    end = datetime.fromisoformat(row["gone_at"]).timestamp() if row.get("gone_at") else now
    return round((end - start) / 86400, 1)


def _price_drop_percent(row: dict) -> float:
    original = row.get("original_price") or row.get("price") or 0
    price = row.get("price") or 0
    if not original:
        return 0.0
    return round((original - price) / original * 100, 1)


def _history_map(conn, kind: str) -> dict:
    history: dict = {}
    sql = (
        "select h.id, h.day, h.price from price_history h "
        "join listing l on l.id = h.id where l.kind = ? order by h.day"
    )
    for row in conn.execute(sql, (kind,)):
        history.setdefault(row["id"], []).append({"day": row["day"], "price_eur": row["price"]})
    return history


def _load_kind(conn, kind: str) -> tuple:
    country_map = {row["cid"]: row["country"] for row in conn.execute(_COUNTRY_SQL)}
    rows = []
    for raw in conn.execute(_LISTING_SQL, (kind,)):
        row = dict(raw)
        if not market.annotate(row, kind):
            continue
        rows.append(row)
    return rows, country_map, _history_map(conn, kind)


def _public_listing(row: dict, country: str, history: list, comps: list) -> dict:
    reference = (
        float(statistics.median(item["price"] for item in comps)) if len(comps) >= 3 else None
    )
    estimate = fees.estimate_net_margin(row["kind"], row["price"], reference)
    net = None if estimate is None else round(estimate["net_margin_eur"], 2)
    roi = None if estimate is None or estimate["roi_pct"] is None else round(estimate["roi_pct"], 1)
    slug = row.get("slug") or ""
    return {
        "id": row["id"],
        "kind": row["kind"],
        "name": row.get("name"),
        "brand": row.get("brand"),
        "size": row.get("size"),
        "year": row.get("year"),
        "condition": row.get("cond"),
        "price_eur": row.get("price"),
        "original_price_eur": row.get("original_price"),
        "price_drop_percent": _price_drop_percent(row),
        "days_on_market": row.get("_days"),
        "country": country,
        "city": row.get("city"),
        "url": "https://buycycle.com/en-lu/product/" + slug if slug else None,
        "first_seen": row.get("first_seen"),
        "last_seen": row.get("last_seen"),
        "gone_at": row.get("gone_at"),
        "reference_eur": reference,
        "comps": len(comps),
        "net_margin_eur_estimate": net,
        "roi_pct_estimate": roi,
        "margin_label": "estimate",
        "price_history": history,
    }


def _prepare(conn, kind: str, now: float) -> list:
    rows, country_map, history = _load_kind(conn, kind)
    comps = market.comparable_listings(rows, kind)
    prepared = []
    for row in rows:
        row["_days"] = _days_on_market(row, now)
        prepared.append(
            _public_listing(
                row, _country(row, country_map), history.get(row["id"], []), comps[row["id"]]
            )
        )
    return prepared


def _matches(row: dict, filters: dict) -> bool:
    if row.get("gone_at"):
        return False
    if filters["price_min"] is not None and (row["price_eur"] or 0) < filters["price_min"]:
        return False
    if filters["price_max"] is not None and (row["price_eur"] or 0) > filters["price_max"]:
        return False
    days = row["days_on_market"]
    if filters["days_min"] is not None and (days is None or days < filters["days_min"]):
        return False
    if filters["days_max"] is not None and (days is None or days > filters["days_max"]):
        return False
    if filters["min_drop"] is not None and row["price_drop_percent"] < filters["min_drop"]:
        return False
    if filters["min_net"] is not None:
        net = row["net_margin_eur_estimate"]
        if net is None or net < filters["min_net"]:
            return False
    if filters["brand"] and (row["brand"] or "").lower() != filters["brand"].lower():
        return False
    if filters["size"] and filters["size"].lower() not in (row["size"] or "").lower():
        return False
    if filters["country"] and (row["country"] or "").lower() != filters["country"].lower():
        return False
    return True


def _sort_rows(rows: list, sort: str, descending: bool) -> list:
    if sort not in SORTS:
        raise ValueError("sort must be one of: " + ", ".join(SORTS))

    def key(row: dict):
        if sort == "brand":
            return (row["brand"] or "").lower()
        value = {
            "net_margin": row["net_margin_eur_estimate"],
            "price": row["price_eur"],
            "days_on_market": row["days_on_market"],
            "price_drop_percent": row["price_drop_percent"],
        }[sort]
        if value is None:
            return (1, 0)
        return (0, -value if descending else value)

    if sort == "brand":
        return sorted(rows, key=key, reverse=descending)
    return sorted(rows, key=key)


def search_listings(
    kind: Optional[str] = None,
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
    days_on_market_min: Optional[float] = None,
    days_on_market_max: Optional[float] = None,
    min_price_drop_percent: Optional[float] = None,
    min_net_margin: Optional[float] = None,
    brand: Optional[str] = None,
    size: Optional[str] = None,
    country: Optional[str] = None,
    sort: str = "net_margin",
    descending: bool = True,
    limit: int = 50,
    now: Optional[float] = None,
) -> dict:
    """Search active listings.

    kind is bike or wheels. price_min and price_max are EUR. days_on_market_min and
    days_on_market_max are days listed. min_price_drop_percent is the drop from the
    original price. min_net_margin is estimated net profit in EUR after the dashboard
    default fees; every margin is labelled "estimate". brand, size, and country filter
    the row. sort is net_margin, price, days_on_market, price_drop_percent, or brand.
    limit is capped at 50.
    """
    selected = normalize_kind(kind)
    kinds = [selected] if selected else ["bikes", "wheels"]
    filters = {
        "price_min": price_min,
        "price_max": price_max,
        "days_min": days_on_market_min,
        "days_max": days_on_market_max,
        "min_drop": min_price_drop_percent,
        "min_net": min_net_margin,
        "brand": _blank(brand),
        "size": _blank(size),
        "country": _blank(country),
    }
    clock = time.time() if now is None else now
    matched: list = []
    with readonly_db() as conn:
        for item_kind in kinds:
            matched.extend(
                row for row in _prepare(conn, item_kind, clock) if _matches(row, filters)
            )
    ordered = _sort_rows(matched, sort, descending)
    capped = clamp_limit(limit)
    page = ordered[:capped]
    for row in page:
        row.pop("price_history", None)
    return {
        "margin_label": "estimate",
        "limit": capped,
        "returned": len(page),
        "matched": len(ordered),
        "listings": page,
    }


def get_listing(listing_id: str, now: Optional[float] = None) -> dict:
    """One listing, its details, and the full price history.

    net_margin_eur_estimate and roi_pct_estimate use the dashboard fee config and
    margin_label is "estimate".
    """
    if not listing_id or not str(listing_id).strip():
        raise ValueError("id is required")
    wanted = str(listing_id)
    clock = time.time() if now is None else now
    with readonly_db() as conn:
        found = conn.execute("select kind from listing where id = ?", (wanted,)).fetchone()
        if found is None:
            raise ValueError(f"listing not found: {wanted}")
        rows = _prepare(conn, found["kind"], clock)
    for row in rows:
        if row["id"] == wanted:
            return row
    raise ValueError(f"listing not found: {wanted}")


def _is_drop(history: list, today: str) -> bool:
    if len(history) < 2 or history[-1]["day"] != today:
        return False
    return history[-1]["price_eur"] < history[-2]["price_eur"]


def todays_deals(now: Optional[datetime] = None, clock: Optional[float] = None) -> dict:
    """Today's new listings and price drops in Europe/Luxembourg, ranked by estimated net margin."""
    today = luxembourg_today(now)
    unix = time.time() if clock is None else clock
    deals = []
    with readonly_db() as conn:
        for kind in ("bikes", "wheels"):
            for row in _prepare(conn, kind, unix):
                if row.get("gone_at"):
                    continue
                reasons = []
                if row.get("first_seen") == today:
                    reasons.append("new listing")
                if _is_drop(row.get("price_history") or [], today):
                    reasons.append("price drop")
                if not reasons:
                    continue
                item = dict(row)
                item.pop("price_history", None)
                item["why"] = reasons
                deals.append(item)
    deals = _sort_rows(deals, "net_margin", True)
    return {
        "margin_label": "estimate",
        "timezone": "Europe/Luxembourg",
        "day": today,
        "returned": len(deals),
        "deals": deals,
    }


def stats(now: Optional[datetime] = None) -> dict:
    """Last tracker run, listing counts, and how fresh the snapshots are."""
    today = luxembourg_today(now)
    with readonly_db() as conn:
        runs = [
            dict(row)
            for row in conn.execute(
                "select day, kind, complete, n, new, gone, fetched, note from runs order by day"
            )
        ]
        counts = {
            "listings": 0,
            "active": 0,
            "gone": 0,
            "bikes": 0,
            "wheels": 0,
            "active_bikes": 0,
            "active_wheels": 0,
        }
        grouped = conn.execute(
            "select kind, (gone_at is null) as active, count(*) as n "
            "from listing group by kind, (gone_at is null)"
        )
        for row in grouped:
            counts["listings"] += row["n"]
            if row["kind"] == "bikes":
                counts["bikes"] += row["n"]
                if row["active"]:
                    counts["active_bikes"] += row["n"]
            elif row["kind"] == "wheels":
                counts["wheels"] += row["n"]
                if row["active"]:
                    counts["active_wheels"] += row["n"]
            if row["active"]:
                counts["active"] += row["n"]
            else:
                counts["gone"] += row["n"]
        history_n = conn.execute("select count(*) as n from price_history").fetchone()["n"]
        latest = conn.execute("select max(day) as day from price_history").fetchone()["day"]
    last_day = runs[-1]["day"] if runs else None
    latest_day = max([day for day in (latest, last_day) if day], default=None)
    age = None
    if latest_day:
        age = (datetime.fromisoformat(today) - datetime.fromisoformat(latest_day)).days
    mtime = datetime.fromtimestamp(os.path.getmtime(db_path()), LUX).isoformat(timespec="seconds")
    return {
        "margin_label": "estimate",
        "timezone": "Europe/Luxembourg",
        "as_of": (now or datetime.now(LUX)).astimezone(LUX).isoformat(timespec="seconds"),
        "last_run_day": last_day,
        "last_run_time": mtime,
        "runs": [row for row in runs if row["day"] == last_day] if last_day else [],
        "counts": {**counts, "price_history": history_n},
        "freshness": {
            "latest_snapshot_day": latest_day,
            "age_days": age,
            "timezone": "Europe/Luxembourg",
        },
        "fee_assumptions": {kind: dict(values) for kind, values in fees.ASSUMPTIONS.items()},
    }
