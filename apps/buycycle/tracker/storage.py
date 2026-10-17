"""Embedded, local Turso (tursodatabase/turso, Rust SQLite rewrite) storage. No cloud, no sync."""

import os
import turso

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.environ.get("BUYCYCLE_DB", os.path.join(BASE, "buycycle.turso.db"))
SCHEMA = [
    """create table if not exists listing(id text primary key, kind text, slug text, name text, brand text, year int, size text, cond text, msrp int,
  price int, original_price int, activated_at int, updated_at int, country_id int, seller_id int, favs int, offers int, high_demand int,
  n_media int, desc_len int, spec text, first_seen text, last_seen text, gone_at text, last_fetch text, fetch_price int, pr int)""",
    "create table if not exists price_history(id text, day text, price int, primary key(id, day))",
    """create table if not exists detail(id text primary key, fetched text, status text, can_buy int, country text, city text, seller_reviews int,
  seller_rating text, member_since text, listings text, n_images int, shipping text, bp text, total text, badge text)""",
    "create table if not exists runs(day text, kind text, complete int, n int, new int, gone int, fetched int, note text, primary key(day, kind))",
    "create table if not exists country_map(cid int primary key, country text)",
    "create index if not exists listing_kind on listing(kind)",
    "create index if not exists listing_slug on listing(slug)",
]
TABLES = ["listing", "price_history", "detail", "runs", "country_map"]


def connect(path=DB):
    c = turso.connect(path)
    c.row_factory = turso.Row
    for s in SCHEMA:
        c.execute(s)
    c.commit()
    return c
