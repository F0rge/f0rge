# Reading a live StatsHunters collection

Research for [Gridloot #774](https://github.com/F0rge/f0rge/issues/774). StatsHunters remains the system of record: Gridloot reads whatever StatsHunters already calculated; it does not re-derive the collection from Strava or another grid.

**Gridloot needs:** the athlete’s explorer tiles (VeloViewer zoom‑14 grid), landmark values (total explorer tiles, max square, largest cluster — StatsHunters names these **max square** and **max cluster**), and enough ordered history to replay how the collection grew.

Primary sources: [StatsHunters FAQ — explorer tiles](https://www.statshunters.com/faq-10-what-are-explorer-tiles), [FAQ — share](https://www.statshunters.com/faq-18-how-can-i-share-my-activity-and-statistics), [FAQ — route extension / API-code](https://www.statshunters.com/faq-16-how-to-easy-plan-routes-for-tiles-(chrome-/-firefox-extension)), [gatsby-source-statshunters `gatsby-node.js`](https://github.com/cedricdelpoux/gatsby-source-statshunters/blob/main/gatsby-node.js) (authoritative `GET /api/{code}/tiles` client), [liscopridge `statshunters.py`](https://github.com/liskin/liscopridge/blob/main/src/liscopridge/app/statshunters.py) and [route-tiles `statshunters.py`](https://github.com/BenoitBouillard/route-tiles/blob/master/statshunters.py) (share activities client), and live probes of a public share link’s JSON endpoints (March 2026).

---

## What StatsHunters means (collection semantics)

From the explorer-tiles FAQ ([primary](https://www.statshunters.com/faq-10-what-are-explorer-tiles)):

- **Explorer tile:** [VeloViewer](https://www.veloviewer.com/) explorer tile — a map square counted when an activity **crosses** it.
- **Cluster-tile:** a tile whose left, right, top, and bottom neighbours are all visited.
- **Max cluster:** derived from connected **cluster-tiles** (Gridloot: **largest cluster**).
- **Max square:** the largest solid square of connected visited tiles.

Tile indices in machine-readable APIs use **Web Mercator slippy tiles at zoom 14** (`x`, `y` integers). Third-party clients treat `z=14` as fixed ([liscopridge `get_tiles`](https://github.com/liskin/liscopridge/blob/main/src/liscopridge/app/statshunters.py), [gatsby plugin `Z = 14`](https://github.com/cedricdelpoux/gatsby-source-statshunters/blob/main/gatsby-node.js)).

StatsHunters does **not** expose Squadrats **squadratinhos** in these tile APIs; only explorer-tile scale appears in the payloads reviewed here.

---

## Ways to read the collection

### 1. Share-link JSON API (read-only, athlete-issued token)

**What:** A share URL `https://www.statshunters.com/share/{shareId}` created on the [Shares](https://www.statshunters.com/share) page ([FAQ](https://www.statshunters.com/faq-18-how-can-i-share-my-activity-and-statistics)). The SPA prefixes API calls with `/share/{shareId}` when `SHARE_HASH` is set ([`app.js`](https://www.statshunters.com/js/app.js) — `window.SHARE_HASH`).

**Endpoints (JSON, no login):**

| Endpoint | Role |
|----------|------|
| `GET …/api/activities?page={n}` | Paginated activities; **500 per page**; empty `activities` ends pagination ([route-tiles](https://github.com/BenoitBouillard/route-tiles/blob/master/statshunters.py), [liscopridge](https://github.com/liskin/liscopridge/blob/main/src/liscopridge/app/statshunters.py)). |
| `GET …/api/activities/lines?page={n}` | Same pagination; each item has `id` and polyline `data` (heatmap lines), not tile lists. |

**Explorer tiles:** each activity includes `tiles: [{x, y}, …]` (live probe of a public share, March 2026).

**Landmarks:** **not** returned as scalar fields. Derive by unioning all activity `tiles` (total count) and running the same graph logic StatsHunters uses client-side ([`/js/tiles.js`](https://www.statshunters.com/js/tiles.js) worker: `square`, `cluster`, etc.) or reuse published algorithms ([liscopridge `max_square`](https://github.com/liskin/liskin/liscopridge/blob/main/src/liscopridge/app/statshunters.py), [route-tiles `compute_max_square` / `compute_cluster`](https://github.com/BenoitBouillard/route-tiles/blob/master/statshunters.py)). StatsHunters’ **definitions** of max square / max cluster are in the FAQ above; the share API does not ship the finished landmark geometries.

**Replay / growth:** Pages are ordered **oldest activity first** (verified: page 1 starts 2011, page 2 continues mid‑2016 on the same public share). Replay = walk `page=1…N`, merging `tiles` (and optionally attaching `utcDate` / `date` per activity). `meta` on each response includes `limit`, `last_activity`, `last_change`, `last_cache_bust` (useful for polling, not documented as a contract).

**Allowed:** Opt-in sharing only ([FAQ privacy / share](https://www.statshunters.com/faq-18-how-can-i-share-my-activity-and-statistics)). Anyone with the URL can read what the share exposes. Third-party tools already depend on this shape ([liscopridge](https://github.com/liskin/liscopridge/blob/main/src/liscopridge/app/statshunters.py)).

**Stable:** Path pattern and `{activities, meta}` envelope have been stable for years in community clients; **no** published OpenAPI, versioning, rate-limit docs, or deprecation policy. Invalid share IDs behave like normal site HTML, not JSON errors.

**Does not include:** Squadratinhos; precomputed max square / max cluster JSON; activity GPS at full resolution (tiles only on the activities endpoint); filters from the logged-in UI unless you implement them client-side; guarantees on private activities beyond what the athlete enabled when sharing.

---

### 2. Personal API code — `GET /api/{code}/tiles`

**What:** The **API-code** on [Settings](https://www.statshunters.com/settings) is the user’s `hash` in the SPA ([`apicode` → `user.hash`](https://www.statshunters.com/js/app.js)). The Chrome/Firefox extension uses the same value ([FAQ‑16](https://www.statshunters.com/faq-16-how-to-easy-plan-routes-for-tiles-(chrome-/-firefox-extension))). Documented for integrators via [gatsby-source-statshunters](https://github.com/cedricdelpoux/gatsby-source-statshunters) (with author permission noted in the README).

**Request:** `GET https://www.statshunters.com/api/{code}/tiles` ([`gatsby-node.js`](https://github.com/cedricdelpoux/gatsby-source-statshunters/blob/main/gatsby-node.js)). Invalid code → `401` + `{"error":"Not allowed"}` (probed March 2026).

**Response (from plugin — only public schema description found):** JSON fields used by the plugin:

- `tiles` — array of tile coordinates (plugin maps to lat/lng polygons).
- `square` — axis-aligned square bounds `{x1, x2, y1, y2}` for **max square** tiles.
- `cluster` and `restCluster` — tile lists for the **max cluster** footprint (plugin concatenates before mapping).
- Plugin classifies tiles into **square**, **cluster**, and remaining **tiles** layers for display.

**Landmarks:** **Present** as tile sets / bounds, not necessarily as single numeric totals (total explorer tiles = &#124;union of all tile coords&#124;).

**Replay:** **Snapshot only** — current collection at request time. No activity timeline in this endpoint.

**Allowed:** Intended for personal integrations (extension, Gatsby plugin). Treat `{code}` as a **secret** (same sensitivity as a share link).

**Stable:** Single-endpoint contract stable since at least the Gatsby plugin (2019+); still **undocumented** by StatsHunters itself beyond settings copy + community README.

**Does not include:** Per-activity history; polylines; squadratinhos; documented SLA; webhook/push on new tiles.

---

### 3. Logged-in first-party `/api/*` (session cookie)

**What:** The StatsHunters web app loads data through `authAxios` with routes such as `/api/activities?page=`, `/api/activities/lines?page=`, `/api/gear`, `/api/badges`, etc. ([`app.js`](https://www.statshunters.com/js/app.js)). On a share page the base URL is `/share/{id}`; when logged in as the athlete it is the site root — **same route names**, different base.

**Explorer tiles & landmarks:** Tiles are **not** fetched from a dedicated public `GET /api/tiles` for the profile. The SPA builds tile layers in a **web worker** ([`/js/tiles.js`](https://www.statshunters.com/js/tiles.js)) from activities already loaded via `/api/activities`. Landmark overlays (max square, max cluster, etc.) are computed in the browser from that tile set.

**Replay:** Possible in principle by paging `/api/activities` the same way as the share API (same `tiles` per activity shape expected). The UI also offers **Record heatmap** (step through activities, export WebM) on share/heatmap chrome — a **manual** replay export, not an API ([share page UI](https://www.statshunters.com/share)).

**Allowed:** Only the authenticated athlete (Strava-linked account). Subject to Strava sync delays ([FAQ rate limits](https://www.statshunters.com/faq)).

**Stable:** Internal SPA contract; can change without notice. Not a supported third-party integration surface.

**Does not include:** A supported alternative to (1) or (2) for external apps unless you hold the athlete’s session (fragile, ToS-grey).

---

### 4. Heatmap download menu (browser export, snapshot)

**What:** Logged-in heatmap **Download** menu ([FAQ‑16](https://www.statshunters.com/faq-16-how-to-easy-plan-routes-for-tiles-(chrome-/-firefox-extension)) mentions EveryTile string; full menu from [`app.js` `downloadTypes`](https://www.statshunters.com/js/app.js)):

- KML (all tiles), KML (missing tiles), KML (activities / lines), KML (compare VeloViewer/Squadrats import)
- Everytile (string) — client-generated MapString-style grid
- Garmin IMG (missing tiles) — `POST /api/tiles/garmin` with tile payload + style ([`app.js`](https://www.statshunters.com/js/app.js))
- Square planner GPX, heatmap image sizes

**Explorer tiles:** Yes, in KML/string/IMG exports after the app has loaded tiles.

**Landmarks:** KML exports can represent max-square-related geometry when generated from current in-memory state; not a structured “three landmarks” API. Compare mode imports **external** VeloViewer/Squadrats KML — not StatsHunters export of squadratinhos.

**Replay:** **No** — exports are **present-state** files. EveryTile string is a **local map window** (124×124 around map centre in `generateEverytileString`), not the full collection.

**Allowed:** Athlete session only; files are meant for devices/tools (Garmin, EveryTile, etc.).

**Stable:** UI-driven; formats have been relatively constant but are not versioned.

**Does not include:** Machine polling; full-world tile dump in one string; activity-dated timeline.

---

### 5. Chrome / Firefox extension (route planning)

**What:** Extension overlays **missing** tiles on Strava/Komoot/etc. using the API-code ([FAQ‑16](https://www.statshunters.com/faq-16-how-to-easy-plan-routes-for-tiles-(chrome-/-firefox-extension))). It consumes the same personal code as `/api/{code}/tiles`, not a separate public API.

**Collection read:** Partial — oriented to **planning**, not delivering full history or landmark stats to a custom viewer.

---

## What is out of scope as “StatsHunters collection”

| Source | Why it is not the collection |
|--------|------------------------------|
| **Strava API** | Raw activities/GPS; no StatsHunters tile set, cluster rules, or landmark values. Sync into StatsHunters is asynchronous and rate-limited ([FAQ](https://www.statshunters.com/faq)). |
| **VeloViewer / Squadrats exports** | StatsHunters can **compare** imported KML to its own tiles ([`app.js`](https://www.statshunters.com/js/app.js)); that is diff tooling, not StatsHunters as SoR. |
| **Country/region tile APIs** | Separate `/api/countrytiles/…` feature in the SPA — not the explorer-tile collection Gridloot describes. |

---

## Summary matrix

| Way | Auth | Explorer tiles | Total count | Max square | Largest cluster (max cluster) | Replay growth | Live / poll |
|-----|------|------------------|------------|------------|-------------------------------|---------------|-------------|
| Share `…/api/activities` | Share URL | Per-activity `tiles` | Derive union | Derive (FAQ rules) | Derive (FAQ rules) | Yes — chronological pages | `meta.last_*` (undocumented) |
| Share `…/api/activities/lines` | Share URL | No (polylines only) | — | — | — | Partial (geometry over time; join IDs to activities) | Same `meta` |
| `GET /api/{code}/tiles` | API-code | `tiles` + `square` + `cluster`/`restCluster` | Derive union | `square` bounds + tiles | `cluster` + `restCluster` | No (snapshot) | Re-fetch |
| Logged-in `/api/activities` | Session | Same as share | Derive | SPA worker | SPA worker | Yes (same paging model) | Re-fetch / UI sync |
| Heatmap downloads | Session | KML / string / IMG | Export-time | Partial in KML | Partial | No | Manual export |
| Extension | API-code | Planning overlay | — | — | — | No | Re-fetch tiles endpoint |

---

## Stability and “live” behaviour

- **No** official StatsHunters developer documentation or stability guarantees were found; contracts are inferred from the SPA, FAQ prose, and long-lived community clients.
- **New activities** land after Strava → StatsHunters sync ([FAQ](https://www.statshunters.com/faq)); readers see updates after sync + cache bust (`last_cache_bust` in share `meta`).
- **Grid definition** is anchored to VeloViewer explorer tiles ([FAQ‑10](https://www.statshunters.com/faq-10-what-are-explorer-tiles)); precision can differ if activity GPS precision differs ([FAQ‑14](https://www.statshunters.com/faq-14-how-to-update-activity-precision-for-tiles/heatmap)).

---

## Practical read paths for Gridloot (facts only, not architecture)

1. **Present + landmarks in one call:** athlete-owned **API-code** → `GET /api/{code}/tiles` (secrets handling required).
2. **Present + replay + shareable read model:** athlete-created **share link** → paginate `…/api/activities` (and optionally `…/api/activities/lines` for paths); compute landmarks from StatsHunters rules or ship landmark math that matches [`tiles.js`](https://www.statshunters.com/js/tiles.js).
3. **Human snapshot only:** heatmap downloads — poor fit for an automated live view.

Open product choices (see parent [#773](https://github.com/F0rge/f0rge/issues/773) “Access setup”): whether Gridloot uses API-code vs share token, how Leonardo rotates/revokes access, and whether landmark numbers must be **bit-identical** to the StatsHunters UI (favours using `/api/{code}/tiles` for present state) vs recomputed from activities (required for replay either way).
