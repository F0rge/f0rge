import json
import sys
import os
import re

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tracker"))
import fees  # noqa: E402

T = open(sys.argv[1] if len(sys.argv) > 1 else "index.tpl.html").read()
OCT = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor", "octicons.json")))
svg = lambda n: f'<svg class="octicon" viewBox="0 0 16 16" width=16 height=16 aria-hidden=true fill=currentColor>{OCT[n]}</svg>'
T = re.sub(r"__OCT_([a-z-]+)__", lambda m: svg(m.group(1)), T).replace("__OCTICONS__", json.dumps(OCT, separators=(",", ":")))
fld = lambda i, l, t="text": (
    f'<div class="col-12 col-md-4 mb-2"><div class="FormControl FormControl--fullWidth"><label class=FormControl-label for={i}>{l}</label><input class="FormControl-input FormControl-medium" id={i} type={t}></div></div>'
)
T = T.replace(
    "__LOGFORM__",
    "".join(
        fld(*a)
        for a in [
            ("lname", "Item"),
            ("lurl", "URL"),
            ("lbuy", "Bought € (all-in)", "number"),
            ("lbd", "Bought on", "date"),
            ("lsell", "Sold € (net payout)", "number"),
            ("lsd", "Sold on", "date"),
        ]
    ),
)
KEYS = [
    ("/", "Search"),
    ("j / k or ↓ / ↑", "Move row"),
    ("Enter / o", "Open listing"),
    ("w", "Watch / unwatch row"),
    ("c", "Show comparables"),
    ("1–4", "Switch tab"),
    ("?", "This help"),
    ("Esc", "Close"),
]
T = T.replace(
    "__KEYS__",
    "".join(
        f'<li class=ActionListItem><span class=ActionListContent><span class=ActionListItem-label>{d}</span><span class="ActionListItem-visual ActionListItem-visual--trailing"><kbd>{k}</kbd></span></span></li>'
        for k, d in KEYS
    ),
)
OUTP = sys.argv[2] if len(sys.argv) > 2 else "."
os.makedirs(OUTP, exist_ok=True)
SRC = """<h2>What resale specialists track, and where it shows up here</h2>
<ul class=src>
<li><b>Net profit and ROI after <i>all</i> costs</b> — resellers rank by money left after fees, shipping, packaging, repairs and returns, and ROI = net profit ÷ total cost (<a href="https://scanflip.ai/blog/return-on-investment-metrics/" target=_blank>Scanflip: ROI metrics resellers use</a>; <a href="https://getpricebird.com/guides/reseller-profit-margin-calculator/" target=_blank>Pricebird: profit-margin calculator guide</a>). <i>Shown as:</i> € profit and ROI columns (default sort), editable Cost assumptions tab, Profit-vs-ROI scatter.</li>
<li><b>Sell-through rate</b> — units sold ÷ units listed over 30–90 days; 50%+ is a sweet spot, under 20% means slow demand unless margin is exceptional (<a href="https://www.mylisterhub.com/articles/ebay-sell-through-rate" target=_blank>MyListerHub on eBay STR</a>; eBay's own <a href="https://www.ebay.com.au/help/selling/selling-tools/terapeak?id=4853" target=_blank>Product Research/Terapeak</a> reports STR, sold-price range and trend). <i>Shown as:</i> model STR column, "Highest sell-through models" chart. Here "sold" = vanished from buycycle's live feed (likely sold or withdrawn).</li>
<li><b>Days to sell / time on market</b> — measure per item from listing to sale; a leading indicator alongside STR (<a href="https://instica.com/guides/reseller-metrics-and-kpis" target=_blank>Instica: reseller KPIs</a>; Scanflip above). <i>Shown as:</i> Days listed column (buycycle's own listing date, "activated_at"; * = first-seen fallback), model median days-to-sell, "Fastest-selling models" chart, days-listed histogram, Discount-vs-days scatter.</li>
<li><b>Sold-price comparables and trend, not just asks</b> — Terapeak-style research uses sold price ranges and trend direction. <i>Shown as:</i> Model trends tab: daily median ask, active count, and last ask of listings that disappeared (proxy for sold price; buycycle does not publish sold prices).</li>
<li><b>Price-drop history</b> — <i>Shown as:</i> "was €X (−Y%)" from buycycle's original price, count of drops seen by the daily snapshot, sort by price drop %, and the alerts include same-day drops.</li>
<li><b>Seller flexibility / negotiation signal</b> — <i>Shown as:</i> Flex column and filter: +2 if buycycle marks the listing "price reduced" (feed field is_price_reduced), +1 per price drop our daily snapshots saw (max 3), +1 if current price is below buycycle's original price, +1 if listed &gt;90 days (from buycycle's listing date). Higher = more room to offer below ask. Days listed always uses buycycle's listing date (activated_at).</li>
<li><b>Comparables confidence</b> — a deal is only as good as its reference. <i>Shown as:</i> comps count + confidence badge (high ≥10 comps and inter-quartile spread ≤40% of median; medium ≥5; low 3–4), expandable comp list, "wide comp spread" flag, min-confidence filter.</li>
<li><b>Risk</b> — scam and stolen-bike guides flag prices far below the usual, new accounts with no reviews/history, few or stock photos and vague descriptions (<a href="https://help.pinkbike.com/hc/en-us/articles/35442592059287-Buy-Sell-Safety-Tips" target=_blank>Pinkbike safety tips</a>; <a href="https://www.gumtree.com/guides/g/used-bicycle-scams.html" target=_blank>Gumtree used-bicycle scams</a>; <a href="https://www.propertyvault.com.au/bikevault/ForSale/BuyerInformation" target=_blank>BikeVAULT buyer guide</a>). <i>Shown as:</i> risk badges (red = hard: too-good-to-be-true ≥55% under comps, implausibly low price, zero-review seller; amber = few comparables, few photos, thin description, wide comp spread), risk filter, risk-flag chart. Seller reviews come from product pages, fetched only for candidate deals.</li>
</ul>
<h2>Data & method</h2><p class="f6 color-fg-muted">One gentle pass per day (Coolify scheduled task on the Pi, 06:15 Luxembourg time): buycycle's public listing feed at ≥1.6 s between pages; product pages only for new or price-changed candidate deals (≥15% under comps), capped at 150/day, ≥2.2 s apart; any 403/429 → one 2-minute back-off, then the run stops until tomorrow. No proxies. History is kept in an embedded local Turso DB on the Pi (Coolify volume, /data/buycycle.turso.db). Reference = median ask of ≥3 comparable live listings (same brand + model key__REFX__). Listings that vanish from a complete pass are marked "likely sold"; that includes withdrawn listings, so STR is an upper bound.</p>"""
K = {
    "bikes": dict(
        title="Buycycle road & gravel bikes — resale deal finder",
        refx=", model year ±1",
        defaults=fees.ASSUMPTIONS["bikes"],
        fee='Defaults from buycycle\'s fee page (<a href="https://buycycle.com/en-de/page/fees" target=_blank>buycycle.com/en-de/page/fees</a>, checked 17 Oct 2026, EU): buyer protection 2.5% of price for bikes; shipping €99–149 for bikes (default €125 midpoint-ish; local pickup is free); seller protection fee 6.95% of sale price for bikes; listing free; boost optional and dynamic; buycycle packaging is free for bike sellers (<a href="https://buycycle.zendesk.com/hc/en-us/articles/20389854670225-seller-fees" target=_blank>seller-fee help article</a>); no extra payment fee except FX when not paying in EUR; buyer pays the outbound shipping on resale, so outbound defaults to €0. €75 cancellation fee applies to whoever cancels.',
        extra="",
        ejs=[],
    ),
    "wheels": dict(
        title="Buycycle wheelsets — resale deal finder",
        refx=", brake type and rim material, tyre system where ≥3",
        defaults=fees.ASSUMPTIONS["wheels"],
        fee='Defaults from buycycle\'s fee page (<a href="https://buycycle.com/en-de/page/fees" target=_blank>buycycle.com/en-de/page/fees</a>, checked 17 Oct 2026, EU): buyer protection for parts 6% + €1; selling parts is free (0% seller fee); parts shipping "varies by size & location" (default €25 is an assumption — check the checkout total); packaging for parts is not supplied, default €10; no payment fee except FX.',
        extra='<label>Brake<select id=fk><option value="">All</option></select></label><label>Rim<select id=fm><option value="">All</option></select></label><label>Tyre system<select id=fw><option value="">All</option></select></label>',
        ejs=[dict(id="fk", k="k", label="Brake"), dict(id="fm", k="mt", label="Rim"), dict(id="fw", k="w", label="Tyre system")],
    ),
}
for kind, c in K.items():
    h = (
        T.replace("__SHORT__", {"bikes": "Bike deals", "wheels": "Wheelset deals"}[kind])
        .replace("__TITLE__", c["title"])
        .replace("__KIND__", kind)
        .replace("__DEFAULTS__", json.dumps(c["defaults"]))
        .replace("__EXTRA_JS__", json.dumps(c["ejs"]))
    )
    h = h.replace("__EXTRA_FILTERS__", c["extra"]).replace("__FEENOTE__", c["fee"]).replace("__METHOD__", SRC.replace("__REFX__", c["refx"]))
    open(f"{OUTP}/index-{kind}.html", "w").write(h)
