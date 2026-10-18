import json
import sys
import os
import re

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
<li><b>Seller flexibility / negotiation signal</b> — <i>Shown as:</i> a "price reduced" label when buycycle marks the listing (feed field is_price_reduced), the drop count from daily snapshots or a price below buycycle's original, and a filter for price reduced, dropped, or either. Days listed always uses buycycle's listing date (activated_at).</li>
<li><b>Price vs comparables (z-score)</b> — (ask − mean of the same live comps) / their standard deviation. The listing itself is left out. <i>Shown as:</i> Z column, with the comp count, and a "low" mark under 5 comps. A dash under 2 comps or when the comp asks do not vary.</li>
<li><b>Price-cut speed</b> — euros dropped per day listed. Start price is the higher of buycycle's original price and the highest daily snapshot, so a drop this tracker recorded still counts when buycycle's original price does not show it. <i>Shown as:</i> €/day column and the same figure on the mobile card. 0 when the ask did not fall. A dash when this tracker has no price history for the listing. The mobile card header also shows how many daily snapshots that listing has.</li>
<li><b>Mature sell-through of the same comps</b> — of comparable listings first seen at least 30 days ago, the share that disappeared within 30 days of first being seen. Disappeared means <i>gone_at</i> was set because a complete daily pass no longer listed them (sold or withdrawn; buycycle does not publish a sold status). The number beside the percent is that denominator. <i>Shown as:</i> Sold % column. A dash when fewer than 5 comps are old enough. Snapshots only exist from when this tracker started, so on a short history the column is mostly dashes. That is the honest result.</li>
<li><b>Days listed vs typical time to disappear</b> — days listed ÷ the median days-to-disappear of the same comps that have already disappeared. <i>Shown as:</i> vs sell column. A dash when fewer than 5 comparables have disappeared, which is common until the tracker has watched a model long enough.</li>
<li><b>Next cheaper</b> — among the same live comps, the highest ask that is still strictly below this listing, plus how many days this tracker has seen that comp (from first_seen). An equal ask does not count. Ties at that price show the longest-listed one and +N for the others. A ≥ prefix means that comp's first day is the earliest snapshot in the published file, so its age is understated. <i>Shown as:</i> Next column beside Comps, and the same line on the mobile card, linking to that comp. "cheapest" when comps exist and none is cheaper; a dash when there are no live comps. Sorted by those days, with cheapest and dashes last. Computed in the browser from the published listings, so a redeploy shows it before the next tracker run.</li>
<li><b>Comparables confidence</b> — a deal is only as good as its reference. <i>Shown as:</i> comps count + confidence badge (high ≥10 comps and inter-quartile spread ≤40% of median; medium ≥5; low 3–4), expandable comp list, "wide comp spread" flag, min-confidence filter.</li>
<li><b>Risk</b> — scam and stolen-bike guides flag prices far below the usual, new accounts with no reviews/history, few or stock photos and vague descriptions (<a href="https://help.pinkbike.com/hc/en-us/articles/35442592059287-Buy-Sell-Safety-Tips" target=_blank>Pinkbike safety tips</a>; <a href="https://www.gumtree.com/guides/g/used-bicycle-scams.html" target=_blank>Gumtree used-bicycle scams</a>; <a href="https://www.propertyvault.com.au/bikevault/ForSale/BuyerInformation" target=_blank>BikeVAULT buyer guide</a>). <i>Shown as:</i> risk badges (red = hard: too-good-to-be-true ≥55% under comps, implausibly low price, zero-review seller; amber = few comparables, few photos, thin description, wide comp spread), risk filter, risk-flag chart. Seller reviews come from product pages, fetched only for candidate deals.</li>
</ul>
<h2>Data & method</h2><p class="f6 color-fg-muted">One gentle pass per day (Coolify scheduled task on the Pi, 06:15 Luxembourg time): buycycle's public listing feed at ≥1.6 s between pages; product pages only for new or price-changed candidate deals (≥15% under comps), capped at 150/day, ≥2.2 s apart; any 403/429 → one 2-minute back-off, then the run stops until tomorrow. No proxies. History is kept in an embedded local Turso DB on the Pi (Coolify volume, /data/buycycle.turso.db). Reference = median ask of ≥3 comparable live listings (same brand + model key__REFX__). Avg ask is the mean of those same currently listed comparables (every other live match; sold and removed listings stay out) for any count of one or more, and a dash when there are none. Comps is that count. Profit, fees and alerts still use the median reference. Listings that vanish from a complete pass are marked "likely sold"; that includes withdrawn listings, so STR is an upper bound.</p>"""
K = {
    "bikes": dict(
        title="Buycycle road & gravel bikes — resale deal finder",
        refx=", model year ±1",
        defaults=dict(bp=2.5, bpf=0, pay=0, shipin=125, pack=0, repair=50, buffer=75, haircut=5, sellfee=6.95, shipout=0, relist=0),
        fee='Defaults from buycycle\'s fee page (<a href="https://buycycle.com/en-de/page/fees" target=_blank>buycycle.com/en-de/page/fees</a>, checked 17 Oct 2026, EU): buyer protection 2.5% of price for bikes; shipping €99–149 for bikes (default €125 midpoint-ish; local pickup is free); seller protection fee 6.95% of sale price for bikes; listing free; boost optional and dynamic; buycycle packaging is free for bike sellers (<a href="https://buycycle.zendesk.com/hc/en-us/articles/20389854670225-seller-fees" target=_blank>seller-fee help article</a>); no extra payment fee except FX when not paying in EUR; buyer pays the outbound shipping on resale, so outbound defaults to €0. €75 cancellation fee applies to whoever cancels.',
        extra="",
        ejs=[],
    ),
    "wheels": dict(
        title="Buycycle wheelsets — resale deal finder",
        refx=", brake type and rim material, tyre system where ≥3",
        defaults=dict(bp=6, bpf=1, pay=0, shipin=25, pack=10, repair=0, buffer=20, haircut=5, sellfee=0, shipout=0, relist=0),
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
