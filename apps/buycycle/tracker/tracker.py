#!/usr/bin/env python3
"""Gentle daily Buycycle tracker: one feed pass/day, embedded Turso history, writes data.json + alerts.json.
Usage: tracker.py [--kind bikes|wheels|all] [--no-fetch] [--seed-checks file.json ...]"""

import json
import re
import time
import statistics as st
import collections
import datetime as dt
import urllib.request
import urllib.error
import os
import argparse

BASE = os.path.dirname(os.path.abspath(__file__))
import storage  # noqa: E402

DB = storage.DB
OUT = {
    "bikes": os.environ.get("BUYCYCLE_OUT_BIKES", "/home/leo/bikes-dashboard"),
    "wheels": os.environ.get("BUYCYCLE_OUT_WHEELS", "/home/leo/wheels-dashboard"),
}
K = os.environ.get("BUYCYCLE_API_KEY", "")  # buycycle public feed key; set in tracker.env (not committed)
UA = "Mozilla/5.0 (X11; Linux aarch64) personal-price-tracker (1 pass/day)"
FEED_PAUSE, PAGE_PAUSE, PAGE_CAP = 1.6, 2.2, 150
FEEDS = {
    "bikes": [f"group_id/road-gravel-category-{g}?filters%5BeBike%5D=0&filters%5Bis_frameset%5D=0&" for g in ("gravel", "road")],
    "wheels": ["category_slug/complete-wheels?"],
}
COUNTRY = {
    152: "Italy",
    156: "Spain",
    136: "Slovenia",
    151: "France",
    138: "Slovakia",
    150: "Germany",
    154: "Portugal",
    137: "Czech Republic",
    142: "Netherlands",
    161: "Austria",
    145: "Ireland",
    146: "Belgium",
    155: "Poland",
}
# approx road km from Luxembourg City to country's main population centre
KM = {
    "Luxembourg": 0,
    "Belgium": 210,
    "France": 380,
    "Germany": 350,
    "Netherlands": 380,
    "Switzerland": 420,
    "Austria": 800,
    "Italy": 900,
    "Spain": 1500,
    "Portugal": 2000,
    "Czech Republic": 730,
    "Poland": 1100,
    "Slovenia": 1000,
    "Slovakia": 1100,
    "Denmark": 900,
    "Ireland": 1300,
    "United Kingdom": 750,
    "Hungary": 1200,
    "Croatia": 1200,
    "Sweden": 1500,
    "Finland": 2300,
    "Greece": 2500,
    "Romania": 1900,
    "Bulgaria": 2100,
    "Norway": 1500,
    "Estonia": 2000,
    "Latvia": 1800,
    "Lithuania": 1500,
}


class Blocked(Exception):
    pass


def log(*a):
    print(dt.datetime.now().strftime("%H:%M:%S"), *a, flush=True)


def get(u, js=True):
    for attempt in range(2):
        try:
            r = (
                urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA, "Accept-Language": "en"}), timeout=60)
                .read()
                .decode("utf-8", "replace")
            )
            return json.loads(r) if js else r
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):
                log("HTTP", e.code, "-> backing off")
                time.sleep(120 if attempt == 0 else 0)
                if attempt == 1:
                    raise Blocked(e.code)
            else:
                raise


def db():
    c = storage.connect(DB)
    for k, v in COUNTRY.items():
        c.execute("insert or ignore into country_map values(?,?)", (k, v))
    c.commit()
    return c


def scrape(c, kind, today):
    seen = {}
    complete = True
    try:
        for f in FEEDS[kind]:
            for p in range(1, 120):
                d = get(f"https://ac.cnstrc.com/browse/{f}key={K}&num_results_per_page=200&page={p}&c=ciojs-client-2")["response"]
                r = d["results"]
                for x in r:
                    x = x["data"] | {"value": x["value"]}
                    seen[x["id"]] = x
                log(kind, f[:40], "page", p, len(r), "total", len(seen))
                time.sleep(FEED_PAUSE)
                if len(r) < 200:
                    break
    except Exception as e:
        log("feed incomplete:", e)
        complete = False
    new = 0
    for i, x in seen.items():
        if not x.get("price"):
            continue
        row = c.execute("select price from listing where id=?", (i,)).fetchone()
        vals = (
            kind,
            x.get("slug"),
            ((x.get("brand_name") or "") + " " + x["value"]).strip() if kind == "wheels" else x["value"],
            (x.get("brand_name") or "unknown").strip(),
            int(x["year"]) if str(x.get("year", "")).isdigit() else None,
            x.get("product_size") or x.get("frame_size_in_string"),
            x.get("condition_code"),
            x.get("msrp") or None,
            int(x["price"]),
            x.get("original_price"),
            x.get("activated_at"),
            x.get("updated_at_timestamp"),
            x.get("country_id"),
            x.get("seller_id"),
            x.get("favorite_count"),
            x.get("unique_buyer_offers"),
            x.get("is_high_demand"),
            len(x.get("media") or []),
            len(x.get("description") or ""),
            x.get("is_price_reduced"),
            json.dumps({"spec": x.get("specifications"), "cat": x.get("category_name"), "comp": x.get("component_name")}),
        )
        if row is None:
            new += 1
            c.execute(
                "insert into listing(kind,slug,name,brand,year,size,cond,msrp,price,original_price,activated_at,updated_at,country_id,seller_id,favs,offers,high_demand,n_media,desc_len,pr,spec,first_seen,last_seen,id) values("
                + ",".join("?" * 24)
                + ")",
                vals + (today, today, i),
            )
        else:
            c.execute(
                "update listing set kind=?,slug=?,name=?,brand=?,year=?,size=?,cond=?,msrp=?,price=?,original_price=?,activated_at=?,updated_at=?,country_id=?,seller_id=?,favs=?,offers=?,high_demand=?,n_media=?,desc_len=?,pr=?,spec=?,last_seen=?,gone_at=null where id=?",
                vals + (today, i),
            )
        c.execute("insert or replace into price_history values(?,?,?)", (i, today, int(x["price"])))
    gone = 0
    if complete and len(seen) > 500:  # only infer "sold" from a full, healthy pass
        gone = c.execute("update listing set gone_at=? where kind=? and gone_at is null and last_seen<?", (today, kind, today)).rowcount
    c.execute("insert or replace into runs values(?,?,?,?,?,?,0,?)", (today, kind, int(complete), len(seen), new, gone, ""))
    c.commit()
    log(kind, "seen", len(seen), "new", new, "gone", gone, "complete", complete)
    return complete


def fetch_detail(c, i, slug):
    h = get(f"https://buycycle.com/en-lu/product/{slug}", js=False)
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)</script>', h, re.S)
    full = "".join(json.loads('"' + ch + '"') for ch in chunks)
    k = full.find(f'"slug":"{slug}","price"')
    o = {}
    if k > 0:
        try:
            o, _ = json.JSONDecoder().raw_decode(full[full.rfind('{"id"', 0, k) :])
        except Exception:
            o = {}
    s = o.get("seller") or {}

    def f(p):
        m = re.search(p, full)
        return m.group(1) if m else None

    rec = (
        i,
        dt.date.today().isoformat(),
        o.get("status"),
        int(bool(o.get("can_buy_product"))),
        o.get("country"),
        o.get("city"),
        s.get("user_reviews_count"),
        s.get("avg_rating"),
        s.get("member_since") or f(r"Member since[^A-Za-z]*([A-Z][a-z]+ \d{4})"),
        None,
        len(o.get("images") or []),
        None,
        None,
        (o.get("total_with_fee_short") or {}).get("total_price"),
        (o.get("price_badge") or {}).get("text_value"),
    )
    c.execute("insert or replace into detail values(" + ",".join("?" * 15) + ")", rec)
    if o.get("country") and o.get("country_id"):
        c.execute("insert or replace into country_map values(?,?)", (o["country_id"], o["country"]))
    return rec


STOPB = set(
    "road gravel bike bicycle disc disk di2 etap axs ultegra dura ace dura-ace 105 grx sram shimano campagnolo rival force red apex tiagra sora claris super record chorus centaur ekar potenza edition team limited the and with carbon alu aluminium aluminum frameset complete new mechanical hydraulic hrd ltd 1x 2x 11 12 speed 12s 11s rim custom size cm".split()
)
STOPW = set(
    "complete wheels wheel wheelset wheelsets laufradsatz laufräder laufrad set pair paire de roues ruote coppia par ruedas disc disk disco brake brakes rim rims carbon carbone carbono alloy aluminium aluminum alu tubeless tubular clincher tle tl cl centerlock center centre lock 6-bolt 6 bolt 700c 700 28 29 27.5 650b 26 zoll inch mm thru axle ta qr shimano sram hg xdr xd 11s 12s 11 12 speed road gravel mtb new with and for the front rear tyres tires tyre tire freehub hub hubs body only".split()
)
WBR = {"1430": "disc", "1431": "rim"}
WMAT = {"1433": "carbon", "1432": "aluminium", "1434": "steel"}
WSYS = {"1435": "tubeless", "1436": "tubular", "1437": "clincher"}


def model_key(kind, name, brand):
    b = brand.lower()
    n = " " + name.lower() + " "
    for w in b.split():
        n = re.sub(r"(?<![a-z0-9])" + re.escape(w) + r"(?![a-z0-9])", " ", n)
    n = re.sub(r"\b(19|20)\d\d\b", " ", n)
    n = re.sub(r"(\d+)\s*mm\b", r"\1", n)
    toks = [w for w in re.findall(r"[a-z0-9.+-]+", n) if w not in (STOPW if kind == "wheels" else STOPB) and w.strip(".-+")]
    return " ".join(toks[: 3 if kind == "wheels" else 2])


def build(c, kind, today):
    cmap = dict(c.execute("select cid,country from country_map").fetchall())
    rows = [
        dict(r)
        for r in c.execute(
            "select l.*, d.seller_reviews, d.seller_rating, d.member_since, d.n_images, d.country dcountry, d.city, d.status dstatus, d.fetched from listing l left join detail d on d.id=l.id where l.kind=?",
            (kind,),
        )
    ]
    hist = collections.defaultdict(list)
    for r in c.execute("select h.id,h.day,h.price from price_history h join listing l on l.id=h.id where l.kind=? order by h.day", (kind,)):
        hist[r[0]].append((r[1], r[2]))
    L = []
    for r in rows:
        sp = json.loads(r["spec"] or "{}")
        s = sp.get("spec") or {}
        if kind == "wheels" and s.get("wheel-type") not in ("1372", None):
            continue
        r["mk"] = model_key(kind, r["name"], r["brand"])
        r["bk"] = r["brand"].lower()
        r["brake"] = WBR.get(s.get("complete-wheels-brakes-type"), "") if kind == "wheels" else ""
        r["mat"] = WMAT.get(s.get("rim-material"), "") if kind == "wheels" else ""
        r["wsys"] = WSYS.get(s.get("wheel-system"), "") if kind == "wheels" else ""
        r["cat"] = sp.get("cat") or ""
        r["comp"] = sp.get("comp") or ""
        L.append(r)
    act = [r for r in L if not r["gone_at"]]
    G = collections.defaultdict(list)
    for r in act:
        if r["mk"]:
            G[(r["bk"], r["mk"], r["brake"], r["mat"])].append(r)
    now = time.time()
    D = []
    for r in L:
        g = G.get((r["bk"], r["mk"], r["brake"], r["mat"]), [])
        comps = [x for x in g if x["id"] != r["id"] and (kind == "wheels" or r["year"] is None or x["year"] is None or abs(x["year"] - r["year"]) <= 1)]
        ref = st.median(x["price"] for x in comps) if len(comps) >= 3 else None
        # mean ask of the same live comps (any count). None when there are none, so the column is a dash.
        av = round(st.fmean(x["price"] for x in comps), 2) if comps else None
        disp = None
        if len(comps) >= 4:
            q = st.quantiles([x["price"] for x in comps], n=4)
            disp = round((q[2] - q[0]) / ref * 100) if ref else None
        conf = "none" if ref is None else "high" if len(comps) >= 10 and (disp or 0) <= 40 else "medium" if len(comps) >= 5 else "low"
        disc = round((ref - r["price"]) / ref * 100, 1) if ref else None
        h = hist.get(r["id"], [])
        drops = sum(1 for a, b in zip(h, h[1:]) if b[1] < a[1])
        orig = r["original_price"] or r["price"]
        start = r["activated_at"] or (dt.datetime.fromisoformat(r["first_seen"]).timestamp())
        end = dt.datetime.fromisoformat(r["gone_at"]).timestamp() if r["gone_at"] else now
        country = r["dcountry"] or cmap.get(r["country_id"]) or ""
        risk = []
        if disc is not None and disc >= 55:
            risk.append("too-good-to-be-true")
        if r["price"] < (60 if kind == "wheels" else 250):
            risk.append("implausibly low price")
        if ref is not None and len(comps) < 5:
            risk.append("few comparables")
        if ref is None:
            risk.append("no comparables")
        if r["seller_reviews"] == 0:
            risk.append("zero-review seller")
        if (r["n_media"] or 0) < 4:
            risk.append("few photos")
        if (r["desc_len"] or 0) < 60:
            risk.append("thin description")
        if disp is not None and disp > 60:
            risk.append("wide comp spread")
        D.append(
            {
                "i": r["id"],
                "n": r["name"],
                "b": r["brand"],
                "m": r["mk"],
                "y": r["year"],
                "s": r["size"],
                "c": r["cond"],
                "p": r["price"],
                "op": orig,
                "ms": r["msrp"],
                "u": "https://buycycle.com/en-lu/product/" + r["slug"],
                "r": ref,
                "nc": len(comps),
                "av": av,
                "cf": conf,
                "sp": disp,
                "d": disc,
                "dl": round((end - start) / 86400, 1),
                "ld": 1 if r["activated_at"] else 0,
                "fs": r["first_seen"],
                "g": r["gone_at"],
                "pr": r["pr"] or 0,
                "flex": (2 if r["pr"] else 0)
                + min(drops, 3)
                + (1 if (r["activated_at"] and (now - r["activated_at"]) / 86400 > 90) else 0)
                + (1 if orig > r["price"] else 0),
                "pd": drops + (1 if orig > r["price"] and drops == 0 else 0),
                "pdp": round((orig - r["price"]) / orig * 100, 1) if orig else 0,
                "h": h[-30:] if len(h) > 1 else [],
                "co": country,
                "km": KM.get(country),
                "city": r["city"],
                "sr": r["seller_reviews"],
                "sra": r["seller_rating"],
                "msn": r["member_since"],
                "ph": r["n_images"] or r["n_media"],
                "fv": r["favs"],
                "of": r["offers"],
                "hd": r["high_demand"],
                "k": r["brake"],
                "mt": r["mat"],
                "w": r["wsys"],
                "ct": r["cat"],
                "cp": r["comp"],
                "rk": risk,
                "cu": [["https://buycycle.com/en-lu/product/" + x["slug"], x["price"]] for x in sorted(comps, key=lambda x: x["price"])[:10]]
                if disc is not None and disc > 20
                else [],
            }
        )
    # per-model market stats: sell-through (30d), days-to-sell, daily median ask, sold (last-ask) points
    M = collections.defaultdict(lambda: {"active": 0, "gone30": 0, "dts": [], "sold": []})
    cut = (dt.date.fromisoformat(today) - dt.timedelta(days=30)).isoformat()
    for x in D:
        key = x["b"] + " " + x["m"]
        m = M[key]
        if not x["g"]:
            m["active"] += 1
        elif x["g"] >= cut:
            m["gone30"] += 1
            m["dts"].append(x["dl"])
            m["sold"].append([x["g"], x["p"]])
    trend = collections.defaultdict(lambda: collections.defaultdict(list))
    idx = {x["i"]: x["b"] + " " + x["m"] for x in D}
    for i, hh in hist.items():
        if i in idx:
            for day, p in hh:
                trend[idx[i]][day].append(p)
    models = {}
    for key, m in M.items():
        n = m["active"] + m["gone30"]
        if n < 3:
            continue
        models[key] = {
            "a": m["active"],
            "g30": m["gone30"],
            "str": round(m["gone30"] / n * 100, 1) if n else None,
            "dts": round(st.median(m["dts"]), 1) if m["dts"] else None,
            "sold": sorted(m["sold"])[-40:],
            "t": [[d, round(st.median(v)), len(v)] for d, v in sorted(trend[key].items())][-120:],
        }
    dtsm = {k: v["dts"] for k, v in models.items()}
    for x in D:
        x["mdts"] = dtsm.get(x["b"] + " " + x["m"])
        x["str"] = (models.get(x["b"] + " " + x["m"]) or {}).get("str")
    runs = [dict(r) for r in c.execute("select * from runs where kind=? order by day", (kind,))]
    meta = {
        "kind": kind,
        "generated": dt.datetime.now().astimezone().isoformat(timespec="minutes"),
        "today": today,
        "runs": runs,
        "active": sum(1 for x in D if not x["g"]),
        "gone": sum(1 for x in D if x["g"]),
    }
    os.makedirs(OUT[kind], exist_ok=True)
    write_split(kind, meta, [x for x in D if not x["g"] or x["g"] >= cut], models)
    return D


PFX = "https://buycycle.com/en-lu/product/"
COLS = [
    "i",
    "n",
    "b",
    "m",
    "y",
    "s",
    "c",
    "p",
    "op",
    "ms",
    "u",
    "r",
    "nc",
    "av",
    "cf",
    "sp",
    "d",
    "dl",
    "ld",
    "fs",
    "g",
    "pd",
    "pdp",
    "pr",
    "flex",
    "co",
    "km",
    "sr",
    "msn",
    "ph",
    "fv",
    "k",
    "mt",
    "w",
    "ct",
    "cp",
    "rk",
    "mdts",
    "str",
]


def put(path, obj):
    import gzip

    raw = json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode()
    for p, b in ((path, raw), (path + ".gz", gzip.compress(raw, 9))):
        open(p + ".tmp", "wb").write(b)
        os.replace(p + ".tmp", p)


def write_split(kind, meta, items, models):
    """data.json = slim columnar list (all items), top.json = first-paint subset, details.json = comps+history (lazy), models.json (lazy)"""

    def row(x):
        x = dict(x)
        x["u"] = x["u"].replace(PFX, "")
        return [x.get(k) if x.get(k) not in ("", []) else None for k in COLS]

    o = OUT[kind]
    dflt = (0.025, 0, 125, 75 + 50, 0.0695) if kind == "bikes" else (0.06, 1, 25, 30, 0)

    def pf(x):
        if x["r"] is None:
            return -1e9
        return x["r"] * 0.95 * (1 - dflt[4]) - (x["p"] * (1 + dflt[0]) + dflt[1] + dflt[2] + dflt[3])

    hard = {"too-good-to-be-true", "implausibly low price", "zero-review seller"}
    top = sorted([x for x in items if not x["g"] and not (hard & set(x["rk"]))], key=lambda x: -pf(x))[:300]
    put(os.path.join(o, "data.json"), {"meta": meta, "cols": COLS, "rows": [row(x) for x in items]})
    put(os.path.join(o, "top.json"), {"meta": meta, "cols": COLS, "rows": [row(x) for x in top]})
    put(os.path.join(o, "details.json"), {x["i"]: [x["cu"], x["h"]] for x in items if x["cu"] or x["h"]})
    put(os.path.join(o, "models.json"), models)


def alerts(kind, D, today, had_prior):
    # default cost model mirrors the UI defaults
    if kind == "bikes":
        bp, bpf, ship_in, ship_out, sell, pack, buf, minp = 0.025, 0, 125, 0, 0.0695, 0, 75, 300
    else:
        bp, bpf, ship_in, ship_out, sell, pack, buf, minp = 0.06, 1, 25, 0, 0, 10, 20, 100
    out = []
    for x in D:
        if x["g"] or x["r"] is None or x["nc"] < 5:
            continue
        is_new = (x["fs"] == today and had_prior) or (x["ld"] and x["dl"] <= 1.5)
        dropped = len(x["h"]) > 1 and x["h"][-1][0] == today and x["h"][-1][1] < x["h"][-2][1]
        if not (is_new or dropped):
            continue
        sale = x["r"] * 0.95
        cost = x["p"] * (1 + bp) + bpf + ship_in + pack + buf
        profit = sale * (1 - sell) - ship_out - cost
        roi = profit / cost * 100
        hard = {"too-good-to-be-true", "implausibly low price", "zero-review seller"} & set(x["rk"])
        if profit >= minp and roi >= 15 and not hard:
            out.append(
                {
                    "name": x["n"],
                    "url": x["u"],
                    "price_eur": x["p"],
                    "reference_eur": x["r"],
                    "comps": x["nc"],
                    "confidence": x["cf"],
                    "est_profit_eur": round(profit),
                    "roi_pct": round(roi, 1),
                    "why": "new listing" if is_new else "price dropped today",
                    "country": x["co"],
                    "risk_flags": x["rk"],
                    "model_str_30d_pct": x["str"],
                    "model_days_to_sell": x["mdts"],
                }
            )
    out.sort(key=lambda a: -a["est_profit_eur"])
    doc = {
        "generated": dt.datetime.now().astimezone().isoformat(timespec="minutes"),
        "kind": kind,
        "date": today,
        "criteria": f"new or price-dropped today, >=5 comparables, est. profit >= EUR {minp} and ROI >= 15% with default costs, no hard risk flags",
        "deals": out[:50],
    }
    for name in ("alerts.json", f"alerts-{today}.json"):
        json.dump(doc, open(os.path.join(OUT[kind], name), "w"), indent=1, ensure_ascii=False)
    log(kind, "alerts", len(out))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", default="all")
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--no-scrape", action="store_true")
    ap.add_argument("--seed-checks", nargs="*", default=[])
    a = ap.parse_args()
    c = db()
    today = dt.date.today().isoformat()
    for f in a.seed_checks:
        for slug, v in json.load(open(f)).items():
            row = c.execute("select id from listing where slug=?", (slug,)).fetchone()
            if row and not v.get("error"):
                c.execute(
                    "insert or replace into detail values(" + ",".join("?" * 15) + ")",
                    (
                        row[0],
                        "2026-10-16",
                        v.get("status"),
                        int(bool(v.get("can_buy"))),
                        v.get("country"),
                        v.get("city"),
                        v.get("seller_reviews"),
                        v.get("seller_rating"),
                        v.get("member_since"),
                        v.get("listings"),
                        v.get("n_images"),
                        v.get("md_shipping"),
                        v.get("md_bp"),
                        v.get("md_total"),
                        v.get("price_badge"),
                    ),
                )
        c.commit()
    blocked = False
    for kind in ["bikes", "wheels"] if a.kind == "all" else [a.kind]:
        if not a.no_scrape and not blocked:
            if (c.execute("select complete from runs where day=? and kind=?", (today, kind)).fetchone() or [None])[0] == 1:
                log(kind, "already scraped today")
            else:
                try:
                    scrape(c, kind, today)
                except Blocked:
                    blocked = True
        D = build(c, kind, today)
        if not a.no_fetch and not blocked:
            # product pages only for new/changed listings that look like candidate deals, capped, 2.2s apart
            cand = [x for x in D if not x["g"] and x["d"] is not None and x["d"] >= 15 and x["nc"] >= 3]
            todo = []
            for x in sorted(cand, key=lambda x: -x["d"]):
                r = c.execute("select l.slug, l.price, l.fetch_price from listing l where id=?", (x["i"],)).fetchone()
                if r["fetch_price"] != r["price"]:
                    todo.append((x["i"], r["slug"], r["price"]))
            n = 0
            for i, slug, price in todo[:PAGE_CAP]:
                try:
                    fetch_detail(c, i, slug)
                    n += 1
                except Blocked:
                    blocked = True
                    break
                except Exception as e:
                    log("detail err", slug, e)
                c.execute("update listing set fetch_price=?, last_fetch=? where id=?", (price, today, i))
                c.commit()
                time.sleep(PAGE_PAUSE)
            c.execute("update runs set fetched=? where day=? and kind=?", (n, today, kind))
            c.commit()
            log(kind, "product pages fetched", n, "of", len(todo))
            D = build(c, kind, today)
        had_prior = c.execute("select count(*) from runs where kind=? and day<? and complete=1", (kind, today)).fetchone()[0] > 0
        alerts(kind, D, today, had_prior)
    if blocked:
        log("stopped early after 403/429; will retry tomorrow")


if __name__ == "__main__":
    main()
