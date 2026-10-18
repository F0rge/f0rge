import json
import os
import re
import sqlite3
import statistics
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(HERE)


def test_migration_copies_all_rows(tmp_path):
    src = tmp_path / "legacy.db"
    s = sqlite3.connect(src)
    s.execute("create table listing(id text primary key, kind text, slug text, name text, price int)")
    s.execute("create table price_history(id text, day text, price int, primary key(id, day))")
    s.execute("create table detail(id text primary key, fetched text)")
    s.execute("create table runs(day text, kind text, complete int, n int, new int, gone int, fetched int, note text, primary key(day, kind))")
    s.execute("create table country_map(cid int primary key, country text)")
    s.executemany("insert into listing values(?,?,?,?,?)", [(str(i), "bikes", f"s{i}", f"n{i}", 1000 + i) for i in range(50)])
    s.executemany("insert into price_history values(?,?,?)", [(str(i), "2026-10-17", 1000 + i) for i in range(50)])
    s.execute("insert into runs values('2026-10-17','bikes',1,50,50,0,0,'')")
    s.commit()
    s.close()
    dst = tmp_path / "new.turso.db"
    r = subprocess.run(
        [sys.executable, os.path.join(APP, "tracker", "migrate_sqlite_to_turso.py"), "--src", str(src), "--dst", str(dst)], capture_output=True, text=True
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "MISMATCH" not in r.stdout
    import storage

    c = storage.connect(str(dst))
    assert c.execute("select count(*) from listing").fetchone()[0] == 50
    assert c.execute("select count(*) from price_history").fetchone()[0] == 50
    # second run refuses (target not empty)
    r2 = subprocess.run(
        [sys.executable, os.path.join(APP, "tracker", "migrate_sqlite_to_turso.py"), "--src", str(src), "--dst", str(dst)], capture_output=True, text=True
    )
    assert r2.returncode != 0


def test_render_is_responsive_and_has_no_toggle(tmp_path):
    r = subprocess.run(
        [sys.executable, os.path.join(APP, "dashboard", "render.py"), os.path.join(APP, "dashboard", "index.tpl.html"), str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr
    for kind in ("bikes", "wheels"):
        html = (tmp_path / f"index-{kind}.html").read_text()
        assert "__" + "KIND__" not in html and "__OCT_" not in html
        assert "data-viewbtn" not in html and "toggle mobile/desktop" not in html
        assert "<style" not in html
        # Desktop table scrolls at its column floors; risk badges wrap in the cell. Cards stay as they were.
        assert "minmax(160px,.45fr)" in html and "dt.style.minWidth" in html
        assert '<div class="d-flex flex-wrap">${rkHtml(x)}</div>' in html
        assert "function card(x)" in html and "wb-break-word" in html.split("function card(x)", 1)[0].split("function row", 1)[1]


def _insert(c, **k):
    c.execute(
        "insert into listing(id,kind,slug,name,brand,year,size,cond,price,original_price,n_media,desc_len,spec,first_seen,last_seen,gone_at,pr)"
        " values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            k["id"],
            k["kind"],
            k["id"],
            k["name"],
            k["brand"],
            k.get("year"),
            k.get("size", "M"),
            "3",
            k["price"],
            k["price"],
            6,
            120,
            k.get("spec", "{}"),
            "2026-10-01",
            "2026-10-17",
            k.get("gone_at"),
            0,
        ),
    )


def _cell(doc, lid, col):
    idx = {name: i for i, name in enumerate(doc["cols"])}
    for row in doc["rows"]:
        if row[idx["i"]] == lid:
            return row[idx[col]]
    raise AssertionError(lid)


def test_listed_comparable_average_and_count(tmp_path, monkeypatch):
    """Avg ask is the mean of the same live comps the reference uses. Sold, removed, other specs, and the listing itself stay out."""
    import storage
    import tracker

    monkeypatch.setitem(tracker.OUT, "wheels", str(tmp_path / "wheels"))
    monkeypatch.setitem(tracker.OUT, "bikes", str(tmp_path / "bikes"))
    c = storage.connect(str(tmp_path / "fixture.turso.db"))
    disc = json.dumps({"spec": {"complete-wheels-brakes-type": "1430", "rim-material": "1433"}})
    rim = json.dumps({"spec": {"complete-wheels-brakes-type": "1431", "rim-material": "1433"}})
    alu = json.dumps({"spec": {"complete-wheels-brakes-type": "1430", "rim-material": "1432"}})
    for row in (
        dict(id="w1", kind="wheels", name="DT Swiss ERC 1400", brand="DT Swiss", price=1000, spec=disc),
        dict(id="w2", kind="wheels", name="DT Swiss ERC 1400", brand="DT Swiss", price=2000, spec=disc),
        dict(id="w3", kind="wheels", name="DT Swiss ERC 1400", brand="DT Swiss", price=3000, spec=disc),
        dict(id="w4", kind="wheels", name="DT Swiss ERC 1400", brand="DT Swiss", price=9000, spec=disc),
        dict(id="wgone", kind="wheels", name="DT Swiss ERC 1400", brand="DT Swiss", price=500, spec=disc, gone_at="2026-10-10"),
        dict(id="wrim", kind="wheels", name="DT Swiss ERC 1400", brand="DT Swiss", price=100, spec=rim),
        dict(id="walu", kind="wheels", name="DT Swiss ERC 1400", brand="DT Swiss", price=100, spec=alu),
        dict(id="wsolo", kind="wheels", name="Roval Alpinist CLX", brand="Roval", price=700, spec=disc),
    ):
        _insert(c, **row)
    for row in (
        dict(id="t23", kind="bikes", name="Specialized Tarmac SL7", brand="Specialized", year=2023, price=1000),
        dict(id="t24", kind="bikes", name="Specialized Tarmac SL7", brand="Specialized", year=2024, price=2000),
        dict(id="t24b", kind="bikes", name="Specialized Tarmac SL7", brand="Specialized", year=2024, price=3000),
        dict(id="t25", kind="bikes", name="Specialized Tarmac SL7", brand="Specialized", year=2025, price=9000),
        dict(id="tgone", kind="bikes", name="Specialized Tarmac SL7", brand="Specialized", year=2024, price=500, gone_at="2026-10-10"),
        dict(id="tother", kind="bikes", name="Canyon Endurace CF", brand="Canyon", year=2024, price=800),
        dict(id="n0", kind="bikes", name="Cannondale SuperSix Evo", brand="Cannondale", price=1500),
        dict(id="n2020", kind="bikes", name="Cannondale SuperSix Evo", brand="Cannondale", year=2020, price=2500),
        dict(id="n2022", kind="bikes", name="Cannondale SuperSix Evo", brand="Cannondale", year=2022, price=4500),
    ):
        _insert(c, **row)
    c.commit()

    wheels = {x["i"]: x for x in tracker.build(c, "wheels", "2026-10-17")}
    bikes = {x["i"]: x for x in tracker.build(c, "bikes", "2026-10-17")}
    mean = lambda xs: round(statistics.fmean(xs), 2)

    # four live disc/carbon asks; the subject, the sold ask, the rim-brake ask and the aluminium ask are excluded
    assert wheels["w1"]["nc"] == 3
    assert wheels["w1"]["av"] == mean([2000, 3000, 9000])
    assert wheels["w1"]["r"] == 3000  # reference stays the median, which is not the mean
    assert wheels["w1"]["d"] == round((3000 - 1000) / 3000 * 100, 1)
    assert wheels["w1"]["av"] != wheels["w1"]["r"]
    for lone in ("wrim", "walu", "wsolo"):
        assert wheels[lone]["nc"] == 0
        assert wheels[lone]["av"] is None
        assert wheels[lone]["r"] is None

    # bikes: same brand + model, model year ±1. 2023 does not meet 2025.
    assert bikes["t24"]["nc"] == 3
    assert bikes["t24"]["av"] == mean([1000, 3000, 9000])
    assert bikes["t24"]["r"] == 3000
    assert bikes["t24"]["d"] == round((3000 - 2000) / 3000 * 100, 1)
    assert bikes["t23"]["nc"] == 2 and bikes["t23"]["av"] == 2500 and bikes["t23"]["r"] is None
    assert bikes["t25"]["nc"] == 2 and bikes["t25"]["av"] == 2500 and bikes["t25"]["r"] is None
    assert bikes["tother"]["nc"] == 0 and bikes["tother"]["av"] is None
    # a missing year matches every year of that model; a known year does not jump a 2-year gap
    assert bikes["n0"]["nc"] == 2 and bikes["n0"]["av"] == 3500 and bikes["n0"]["r"] is None
    assert bikes["n2020"]["nc"] == 1 and bikes["n2020"]["av"] == 1500
    assert bikes["n2022"]["nc"] == 1 and bikes["n2022"]["av"] == 1500

    doc = json.loads((tmp_path / "wheels" / "data.json").read_text())
    assert doc["cols"].index("av") == doc["cols"].index("nc") + 1
    assert _cell(doc, "w1", "av") == wheels["w1"]["av"]
    assert _cell(doc, "w1", "nc") == 3
    assert _cell(doc, "wsolo", "av") is None
    assert _cell(doc, "wsolo", "nc") == 0
    alerts = open(os.path.join(APP, "tracker", "tracker.py")).read().split("def alerts(", 1)[1].split("\ndef ", 1)[0]
    assert 'x["av"]' not in alerts and 'x["r"]' in alerts


def test_dashboard_columns_sort_zero_comps_last(tmp_path):
    r = subprocess.run(
        [sys.executable, os.path.join(APP, "dashboard", "render.py"), os.path.join(APP, "dashboard", "index.tpl.html"), str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr
    for kind in ("bikes", "wheels"):
        html = (tmp_path / f"index-{kind}.html").read_text()
        assert "['av','Avg ask'" in html and "['nc','Comps'" in html
        assert "Min avg ask" in html and "Max avg ask" in html and "Min comps" in html
        assert "avg ask" in html and "comps" in html
        assert "['z','Z-score'" in html and "['cs','€/day cut'" in html and "['st','Sold within 30d'" in html and "['vs','Days vs typical'" in html
        assert "Min z-score" in html and "Min €/day cut" in html and "Min sold %" in html and "Max days vs typical" in html
        assert "standard deviation" in html and "fewer than 5" in html
        assert "no price history" in html and "highest daily snapshot" in html
        assert "of history" in html and "active · ${m.runs.length} snapshot(s) · updated" in html
        assert "z-score" in html and "€/day" in html and "sold %" in html and "vs typical" in html
        assert "Flex score" not in html and "['flex','Flex'" not in html and "days listed · flex" not in html
        assert "price reduced" in html and "Dropped (history or vs original)" in html
        assert "['nxd','Next up'" in html and "Min next-up days" in html
        assert html.index("['nc','Comps'") < html.index("['nxd','Next up'") < html.index("['z','Z'")
        cols = html.split("const COLS=", 1)[1].split("];", 1)[0]
        assert cols.index("['nc'") < cols.index("['nxd'") < cols.index("['z'")
        assert "next up" in html and "strictly above" in html and "priciest" in html
        assert "next cheaper" not in html and "nxk=='cheapest'" not in html and html.count("fillNext(ITEMS") == 1
        assert "x.nxd!=null&&x.nxd>=" in html
        calc = html.split("function calc(x)", 1)[1].split("function", 1)[0]
        assert "if(x.r==null)return" in calc and "x.av" not in calc and "x.z" not in calc and "x.cs" not in calc and "x.nx" not in calc
        m = re.search(r"view\.sort\(\(a,b\)=>\{.*?\}\);", html)
        assert m and "key=='nc'&&!A" in m.group(0)
    script = r"""
const rows = [{nc:0,av:null,name:'zero'},{nc:2,av:300,name:'two'},{nc:null,av:null,name:'none'},{nc:5,av:100,name:'five'},{nc:1,av:300,name:'one'}];
let key='nc', asc=true, view=rows.slice();
%s
const ascNames = view.map(r => r.name);
if (ascNames.slice(0, 3).join() !== 'one,two,five') throw new Error('asc ' + ascNames);
if (ascNames.slice(3).sort().join() !== 'none,zero') throw new Error('asc tail ' + ascNames);
view = rows.slice(); asc = false;
%s
const descNames = view.map(r => r.name);
if (descNames.slice(0, 3).join() !== 'five,two,one') throw new Error('desc ' + descNames);
if (descNames.slice(3).sort().join() !== 'none,zero') throw new Error('desc tail ' + descNames);
view = rows.slice(); key = 'av'; asc = true;
%s
const avNames = view.map(r => r.name);
if (avNames.slice(0, 3).join() !== 'five,two,one') throw new Error('av ' + avNames);
if (avNames.slice(3).sort().join() !== 'none,zero') throw new Error('av tail ' + avNames);
""" % (m.group(0), m.group(0), m.group(0))
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr


def _prod_listing(c, **k):
    """One row in the shape the Pi stores: listing.price is the integer ask; every other money/spec field may be NULL."""
    c.execute(
        "insert into listing(id,kind,slug,name,brand,year,size,cond,msrp,price,original_price,activated_at,updated_at,country_id,seller_id,favs,offers,high_demand,n_media,desc_len,spec,first_seen,last_seen,gone_at,last_fetch,fetch_price,pr)"
        " values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            k["id"],
            k["kind"],
            k["id"],
            k["name"],
            k["brand"],
            k.get("year"),
            None,
            None,
            None,
            k["price"],
            k.get("original"),
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            k.get("spec"),
            k.get("first_seen", "2026-10-01"),
            "2026-10-17",
            k.get("gone_at"),
            None,
            None,
            None,
        ),
    )


def _comp_js():
    lines = open(os.path.join(APP, "dashboard", "index.tpl.html")).read().splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("function compKey"))
    end = next(i for i, line in enumerate(lines) if line.startswith("function calc"))
    return "\n".join(lines[start:end])


def _unpack(doc):
    items = []
    for row in doc["rows"]:
        x = {c: v for c, v in zip(doc["cols"], row) if v is not None}
        items.append(x)
    return items


def _strip_av(doc):
    """The file currently on the Pi: comp count and asking price, no av column."""
    i = doc["cols"].index("av")
    doc["cols"].pop(i)
    for row in doc["rows"]:
        row.pop(i)
    return doc


def test_average_from_prod_listing_price_when_json_has_no_av_column(tmp_path, monkeypatch):
    import storage
    import tracker

    monkeypatch.setitem(tracker.OUT, "wheels", str(tmp_path / "wheels"))
    monkeypatch.setitem(tracker.OUT, "bikes", str(tmp_path / "bikes"))
    c = storage.connect(str(tmp_path / "fixture.turso.db"))
    disc = json.dumps({"spec": {"wheel-type": "1372", "complete-wheels-brakes-type": "1430", "rim-material": "1433"}})
    rim = json.dumps({"spec": {"wheel-type": "1372", "complete-wheels-brakes-type": "1431", "rim-material": "1433"}})
    for row in (
        dict(id="w1", kind="wheels", name="DT Swiss ERC 1400", brand="DT Swiss", price=1000, spec=disc),
        dict(id="w2", kind="wheels", name="DT Swiss ERC 1400", brand="DT Swiss", price=2000, spec=disc),
        dict(id="w3", kind="wheels", name="DT Swiss ERC 1400", brand="DT Swiss", price=3000, spec=disc),
        dict(id="w4", kind="wheels", name="DT Swiss ERC 1400", brand="DT Swiss", price=9000, spec=disc),
        dict(id="wgone", kind="wheels", name="DT Swiss ERC 1400", brand="DT Swiss", price=50, spec=disc, gone_at="2026-10-10"),
        dict(id="wrim", kind="wheels", name="DT Swiss ERC 1400", brand="DT Swiss", price=80, spec=rim),
    ):
        _prod_listing(c, **row)
    for row in (
        dict(id="t24", kind="bikes", name="Specialized Tarmac SL7", brand="Specialized", year=2024, price=2000),
        dict(id="t23", kind="bikes", name="Specialized Tarmac SL7", brand="Specialized", year=2023, price=1000),
        dict(id="t25", kind="bikes", name="Specialized Tarmac SL7", brand="Specialized", year=2025, price=9000),
        dict(id="tgone", kind="bikes", name="Specialized Tarmac SL7", brand="Specialized", year=2024, price=40, gone_at="2026-10-10"),
    ):
        _prod_listing(c, **row)
    # A different number in history must not become the average. The ask is listing.price.
    c.execute("insert into price_history values(?,?,?)", ("w1", "2026-09-01", 1))
    c.commit()
    stored = c.execute("select price, typeof(price), original_price, year from listing where id='w1'").fetchone()
    assert stored[0] == 1000 and stored[1] == "integer" and stored[2] is None and stored[3] is None

    wheels = {x["i"]: x for x in tracker.build(c, "wheels", "2026-10-17")}
    bikes = {x["i"]: x for x in tracker.build(c, "bikes", "2026-10-17")}
    assert wheels["w1"]["nc"] == 3
    assert wheels["w1"]["av"] == round(statistics.fmean([2000, 3000, 9000]), 2)
    assert wheels["w1"]["p"] == 1000
    assert "flex" not in wheels["w1"]
    assert bikes["t24"]["av"] == round(statistics.fmean([1000, 9000]), 2)
    assert bikes["t24"]["nc"] == 2

    def recover(kind, doc_path):
        doc = _strip_av(json.loads(doc_path.read_text()))
        assert "av" not in doc["cols"] and "p" in doc["cols"] and "nc" in doc["cols"]
        script = "const KIND=%s;\n%s\nconst items=%s;\nfillAvg(items);\nconsole.log(JSON.stringify(items.map(x=>({i:x.i,av:x.av??null,nc:x.nc}))));" % (
            json.dumps(kind),
            _comp_js(),
            json.dumps(_unpack(doc)),
        )
        out = subprocess.run(["node", "-e", script], capture_output=True, text=True)
        assert out.returncode == 0, out.stderr
        return {x["i"]: x for x in json.loads(out.stdout)}

    got = recover("wheels", tmp_path / "wheels" / "data.json")
    assert got["w1"]["nc"] == 3 and got["w1"]["av"] == wheels["w1"]["av"]
    assert got["wgone"]["av"] == wheels["wgone"]["av"]
    assert got["wrim"]["av"] is None and got["wrim"]["nc"] == 0
    gotb = recover("bikes", tmp_path / "bikes" / "data.json")
    assert gotb["t24"]["av"] == bikes["t24"]["av"] and gotb["t24"]["nc"] == 2
    assert gotb["t23"]["nc"] == 1 and gotb["t23"]["av"] == 2000


def test_market_metrics_on_prod_shaped_rows(tmp_path, monkeypatch):
    import storage
    import tracker

    monkeypatch.setitem(tracker.OUT, "wheels", str(tmp_path / "wheels"))
    monkeypatch.setitem(tracker.OUT, "bikes", str(tmp_path / "bikes"))
    c = storage.connect(str(tmp_path / "fixture.turso.db"))
    disc = json.dumps({"spec": {"wheel-type": "1372", "complete-wheels-brakes-type": "1430", "rim-material": "1433"}})
    rim = json.dumps({"spec": {"wheel-type": "1372", "complete-wheels-brakes-type": "1431", "rim-material": "1433"}})
    today = "2026-10-17"
    for i, price in enumerate((1000, 2000, 3000, 4000, 5000, 6000), start=1):
        _prod_listing(c, id=f"a{i}", kind="wheels", name="DT Swiss ARC 1100", brand="DT Swiss", price=price, spec=disc)
    for i in range(3):
        _prod_listing(c, id=f"flat{i}", kind="wheels", name="Enve SES", brand="Enve", price=800, spec=disc)
    _prod_listing(c, id="pair1", kind="wheels", name="Roval Alpinist", brand="Roval", price=1400, spec=disc)
    _prod_listing(c, id="pair2", kind="wheels", name="Roval Alpinist", brand="Roval", price=1800, spec=disc)
    for i, price in enumerate((1100, 1600, 2100)):
        _prod_listing(c, id=f"low{i}", kind="wheels", name="Scope R4", brand="Scope", price=price, spec=disc)
    _prod_listing(c, id="nohist", kind="wheels", name="Zipp 404", brand="Zipp", price=900, spec=disc, original=5000)
    _prod_listing(c, id="nodrop", kind="wheels", name="Zipp 303", brand="Zipp", price=700, spec=disc)
    # Mature comps for sell-through and time-to-disappear. A recent listing and a different brake stay out.
    _prod_listing(c, id="m0", kind="wheels", name="Mavic Cosmic", brand="Mavic", price=2000, spec=disc, first_seen="2026-08-01")
    for i in range(1, 4):
        _prod_listing(c, id=f"m{i}", kind="wheels", name="Mavic Cosmic", brand="Mavic", price=1500, spec=disc, first_seen="2026-08-01", gone_at="2026-08-20")
    for i in (4, 5):
        _prod_listing(c, id=f"m{i}", kind="wheels", name="Mavic Cosmic", brand="Mavic", price=2200, spec=disc, first_seen="2026-08-01")
    for i, gone in ((6, "2026-09-20"), (7, "2026-09-20")):
        _prod_listing(c, id=f"m{i}", kind="wheels", name="Mavic Cosmic", brand="Mavic", price=1800, spec=disc, first_seen="2026-08-01", gone_at=gone)
    _prod_listing(c, id="mnew", kind="wheels", name="Mavic Cosmic", brand="Mavic", price=50, spec=disc, first_seen="2026-10-01")
    _prod_listing(c, id="mrim", kind="wheels", name="Mavic Cosmic", brand="Mavic", price=10, spec=rim, first_seen="2026-08-01", gone_at="2026-08-05")
    for i in range(4):
        _prod_listing(c, id=f"thin{i}", kind="wheels", name="Lightweight Meilenstein", brand="Lightweight", price=3000, spec=disc, first_seen="2026-08-01")
    _prod_listing(c, id="t24", kind="bikes", name="Specialized Tarmac SL7", brand="Specialized", year=2024, price=2000)
    _prod_listing(c, id="t23", kind="bikes", name="Specialized Tarmac SL7", brand="Specialized", year=2023, price=1000)
    _prod_listing(c, id="t25", kind="bikes", name="Specialized Tarmac SL7", brand="Specialized", year=2025, price=9000)
    _prod_listing(c, id="t22", kind="bikes", name="Specialized Tarmac SL7", brand="Specialized", year=2022, price=100)
    c.executemany(
        "insert into price_history values(?,?,?)",
        [("a1", "2026-08-01", 3000), ("nodrop", "2026-10-01", 700), ("a1", "2026-10-17", 1000)],
    )
    c.commit()
    wheels = {x["i"]: x for x in tracker.build(c, "wheels", today)}
    bikes = {x["i"]: x for x in tracker.build(c, "bikes", today)}

    prices = [2000, 3000, 4000, 5000, 6000]
    assert wheels["a1"]["nc"] == 5
    assert wheels["a1"]["z"] == round((1000 - statistics.fmean(prices)) / statistics.pstdev(prices), 2)
    assert wheels["a1"]["av"] == round(statistics.fmean(prices), 2)
    assert wheels["flat0"]["nc"] == 2 and wheels["flat0"]["z"] is None
    assert wheels["pair1"]["nc"] == 1 and wheels["pair1"]["z"] is None
    assert wheels["low0"]["nc"] == 2 and wheels["low0"]["z"] is not None
    assert wheels["a1"]["cs"] == round(2000 / wheels["a1"]["dl"], 2)
    assert wheels["nodrop"]["cs"] == 0
    assert wheels["nohist"]["cs"] is None and wheels["nohist"]["op"] == 5000
    assert wheels["m0"]["st"] == 42.9 and wheels["m0"]["sn"] == 7
    assert wheels["mrim"]["st"] is None and wheels["mnew"]["i"]
    gone_days = [19, 19, 19, 50, 50]
    assert wheels["m0"]["vs"] == round(wheels["m0"]["dl"] / statistics.median(gone_days), 2)
    assert wheels["thin0"]["st"] is None and wheels["thin0"]["vs"] is None
    assert bikes["t24"]["nc"] == 2
    assert bikes["t24"]["z"] == round((2000 - statistics.fmean([1000, 9000])) / statistics.pstdev([1000, 9000]), 2)
    assert bikes["t22"]["nc"] == 1 and bikes["t22"]["z"] is None
    alerts = open(os.path.join(APP, "tracker", "tracker.py")).read().split("def alerts(", 1)[1].split("\ndef ", 1)[0]
    assert 'x["z"]' not in alerts and 'x["cs"]' not in alerts and 'x["st"]' not in alerts and 'x["r"]' in alerts

    doc = _strip_av(json.loads((tmp_path / "wheels" / "data.json").read_text()))
    zi = doc["cols"].index("z")
    doc["cols"].pop(zi)
    for row in doc["rows"]:
        row.pop(zi)
    script = "const KIND=%s;\n%s\nconst items=%s;\nfillZ(items);\nconsole.log(JSON.stringify(items.map(x=>({i:x.i,z:x.z??null}))));" % (
        json.dumps("wheels"),
        _comp_js(),
        json.dumps(_unpack(doc)),
    )
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    got = {x["i"]: x["z"] for x in json.loads(out.stdout)}
    assert got["a1"] == wheels["a1"]["z"]
    assert got["flat0"] is None and got["pair1"] is None


def test_cut_speed_counts_a_snapshot_drop_the_original_price_hides(tmp_path, monkeypatch):
    """Syncros Capital SL: ask €2,200, original €2,200, one snapshot drop, 205 days listed. The old start price ignored that drop and showed 0."""
    import storage
    import tracker

    now = 1_800_000_000
    monkeypatch.setattr(tracker.time, "time", lambda: now)
    monkeypatch.setitem(tracker.OUT, "wheels", str(tmp_path / "wheels"))
    monkeypatch.setitem(tracker.OUT, "bikes", str(tmp_path / "bikes"))
    c = storage.connect(str(tmp_path / "cut.turso.db"))
    disc = json.dumps({"spec": {"wheel-type": "1372", "complete-wheels-brakes-type": "1430", "rim-material": "1433"}})
    today = "2026-10-17"
    _prod_listing(
        c,
        id="syncros",
        kind="wheels",
        name="Syncros Capital SL 40 mm",
        brand="Syncros",
        price=2200,
        original=2200,
        spec=disc,
        first_seen="2026-03-26",
    )
    _prod_listing(
        c,
        id="mid",
        kind="wheels",
        name="Zipp 353 NSW",
        brand="Zipp",
        price=2200,
        original=2200,
        spec=disc,
        first_seen="2026-08-01",
    )
    _prod_listing(
        c,
        id="bsync",
        kind="bikes",
        name="Canyon Aeroad CF",
        brand="Canyon",
        year=2024,
        price=1500,
        original=1500,
        first_seen="2026-08-01",
    )
    c.execute("update listing set pr=1, activated_at=? where id='syncros'", (now - 205 * 86400,))
    c.executemany(
        "insert into price_history values(?,?,?)",
        [
            ("syncros", "2026-03-26", 2800),
            ("syncros", "2026-10-17", 2200),
            ("mid", "2026-08-01", 2200),
            ("mid", "2026-09-01", 2600),
            ("mid", "2026-10-17", 2200),
            ("bsync", "2026-08-01", 2000),
            ("bsync", "2026-10-17", 1500),
        ],
    )
    c.commit()
    wheels = {x["i"]: x for x in tracker.build(c, "wheels", today)}
    bikes = {x["i"]: x for x in tracker.build(c, "bikes", today)}
    sync = wheels["syncros"]
    assert sync["p"] == 2200 and sync["op"] == 2200 and sync["pr"] == 1
    assert sync["pd"] == 1 and sync["dl"] == 205 and sync["hs"] == 2
    assert sync["cs"] == round(600 / 205, 2)
    mid = wheels["mid"]
    assert mid["pd"] == 1 and mid["hs"] == 3 and mid["cs"] == round(400 / mid["dl"], 2) and mid["cs"] > 0
    bike = bikes["bsync"]
    assert bike["hs"] == 2 and bike["cs"] == round(500 / bike["dl"], 2) and bike["cs"] > 0
    doc = json.loads((tmp_path / "wheels" / "data.json").read_text())
    assert doc["cols"].index("hs") == doc["cols"].index("g") + 1


def _nx_cell_js():
    lines = open(os.path.join(APP, "dashboard", "index.tpl.html")).read().splitlines()
    return next(line for line in lines if line.startswith("function nxCell"))


def test_next_up_from_published_rows(tmp_path):
    """Closest strictly pricier live comp. Lightweight at €1,500 is the cheapest of 10 comps, so next up is €1,700."""
    today = "2026-10-17"
    wheels = [
        dict(
            i="lw",
            n="Lightweight Meilenstein Evo Disc Tubeless",
            b="Lightweight",
            m="Meilenstein",
            k="disc",
            mt="carbon",
            p=1500,
            fs="2026-10-10",
            u="https://buycycle.com/en-lu/product/lw",
        ),
        dict(i="up", b="Lightweight", m="Meilenstein", k="disc", mt="carbon", p=1700, fs="2026-10-01", u="https://buycycle.com/en-lu/product/up"),
        dict(
            i="gone",
            b="Lightweight",
            m="Meilenstein",
            k="disc",
            mt="carbon",
            p=1600,
            fs="2026-08-01",
            g="2026-10-10",
            u="https://buycycle.com/en-lu/product/gone",
        ),
        dict(i="rim", b="Lightweight", m="Meilenstein", k="rim", mt="carbon", p=1600, fs="2026-08-01", u="https://buycycle.com/en-lu/product/rim"),
        dict(i="eq", b="Scope", m="R4", k="disc", mt="carbon", p=800, fs="2026-10-01", u="https://buycycle.com/en-lu/product/eq"),
        dict(i="eq2", b="Scope", m="R4", k="disc", mt="carbon", p=800, fs="2026-09-01", u="https://buycycle.com/en-lu/product/eq2"),
        dict(i="higher", b="Scope", m="R4", k="disc", mt="carbon", p=1200, fs="2026-10-01", u="https://buycycle.com/en-lu/product/higher"),
        dict(i="solo", b="Hunt", m="Limitless", k="disc", mt="carbon", p=1500, fs="2026-10-01", u="https://buycycle.com/en-lu/product/solo"),
        dict(i="tie", b="Enve", m="SES", k="disc", mt="carbon", p=1000, fs="2026-10-10", u="https://buycycle.com/en-lu/product/tie"),
        dict(i="tiea", b="Enve", m="SES", k="disc", mt="carbon", p=1500, fs="2026-09-24", u="https://buycycle.com/en-lu/product/tiea"),
        dict(i="tieb", b="Enve", m="SES", k="disc", mt="carbon", p=1500, fs="2026-10-01", u="https://buycycle.com/en-lu/product/tieb"),
        dict(i="floor", b="Roval", m="Alpinist", k="disc", mt="carbon", p=1000, fs="2026-10-05", u="https://buycycle.com/en-lu/product/floor"),
        dict(i="floorc", b="Roval", m="Alpinist", k="disc", mt="carbon", p=1200, fs="2026-08-01", u="https://buycycle.com/en-lu/product/floorc"),
    ]
    for i, price in enumerate((1800, 2000, 2200, 2400, 2600, 2800, 3000, 3200, 3400), start=1):
        wheels.append(
            dict(
                i=f"h{i}",
                b="Lightweight",
                m="Meilenstein",
                k="disc",
                mt="carbon",
                p=price,
                fs="2026-08-01" if price == 3400 else "2026-10-05",
                u=f"https://buycycle.com/en-lu/product/h{i}",
            )
        )
    bikes = [
        dict(i="t24", b="Specialized", m="Tarmac", y=2024, p=2000, fs="2026-10-10", u="https://buycycle.com/en-lu/product/t24"),
        dict(i="t23", b="Specialized", m="Tarmac", y=2023, p=2500, fs="2026-10-01", u="https://buycycle.com/en-lu/product/t23"),
        dict(i="t25", b="Specialized", m="Tarmac", y=2025, p=4000, fs="2026-09-20", u="https://buycycle.com/en-lu/product/t25"),
        dict(i="t22", b="Specialized", m="Tarmac", y=2022, p=2100, fs="2026-08-01", u="https://buycycle.com/en-lu/product/t22"),
        dict(i="e1", b="Canyon", m="Aeroad", y=2020, p=1000, fs="2026-10-01", u="https://buycycle.com/en-lu/product/e1"),
        dict(i="e2", b="Canyon", m="Aeroad", y=2020, p=1000, fs="2026-09-01", u="https://buycycle.com/en-lu/product/e2"),
    ]

    def run(kind, items):
        script = (
            "const KIND=%s;\n%s\nconst items=%s;\nfillNext(items,%s);\nconsole.log(JSON.stringify(items.map(x=>({i:x.i,nxp:x.nxp,nxu:x.nxu,nxd:x.nxd,nxn:x.nxn,nxf:x.nxf,nxk:x.nxk}))));"
            % (
                json.dumps(kind),
                _comp_js(),
                json.dumps(items),
                json.dumps(today),
            )
        )
        out = subprocess.run(["node", "-e", script], capture_output=True, text=True)
        assert out.returncode == 0, out.stderr
        return {x["i"]: x for x in json.loads(out.stdout)}

    others = [x for x in wheels if x["m"] == "Meilenstein" and x["i"] != "lw" and not x.get("g") and x.get("k") == "disc"]
    assert len(others) == 10 and min(x["p"] for x in others) == 1700
    got = run("wheels", wheels)
    assert got["lw"]["nxp"] == 1700 and got["lw"]["nxu"].endswith("/up")
    assert got["lw"]["nxd"] == 16 and got["lw"]["nxn"] == 0 and got["lw"]["nxf"] is False
    assert got["h9"]["nxk"] == "priciest" and got["h9"]["nxp"] is None
    assert got["eq"]["nxp"] == 1200 and got["eq"]["nxk"] is None
    assert got["solo"]["nxk"] is None and got["solo"]["nxp"] is None and got["solo"]["nxd"] is None
    assert got["tie"]["nxp"] == 1500 and got["tie"]["nxu"].endswith("/tiea") and got["tie"]["nxd"] == 23 and got["tie"]["nxn"] == 1
    assert got["floor"]["nxp"] == 1200 and got["floor"]["nxd"] == 77 and got["floor"]["nxf"] is True and got["floor"]["nxn"] == 0
    assert got["rim"]["nxk"] is None and got["rim"]["nxp"] is None
    gotb = run("bikes", bikes)
    assert gotb["t24"]["nxp"] == 2500 and gotb["t24"]["nxu"].endswith("/t23") and gotb["t24"]["nxd"] == 16
    assert gotb["e1"]["nxk"] == "priciest"

    cell = "const esc=s=>String(s??'');const eur=v=>v==null?'–':'€'+Math.round(v).toLocaleString('en');const TIP={nxd:'tip'};\n%s\n" % _nx_cell_js()
    show = cell + "const rows=%s;\nconsole.log(rows.map(nxCell).join('\\n'));" % json.dumps(
        [
            dict(p=1500, nxp=1700, nxu="https://buycycle.com/en-lu/product/up", nxd=16, nxn=0, nxf=False),
            dict(p=1000, nxp=1200, nxu="https://buycycle.com/en-lu/product/floorc", nxd=77, nxn=0, nxf=True),
            dict(p=1000, nxp=1500, nxu="https://buycycle.com/en-lu/product/tiea", nxd=23, nxn=1, nxf=False),
            dict(nxk="priciest"),
            {},
            dict(p=1500, nxp=1700, nxu="https://buycycle.com/en-lu/product/up", nxd=None, nxn=0, nxf=False),
        ]
    )
    shown = subprocess.run(["node", "-e", show], capture_output=True, text=True)
    assert shown.returncode == 0, shown.stderr
    lines = shown.stdout.splitlines()
    assert (
        lines[0]
        == '<a class=Link--primary title="tip" href="https://buycycle.com/en-lu/product/up" target=_blank rel=noopener>↑ €1,700 (+€200 / +13%) · 16d</a>'
    )
    assert (
        lines[1]
        == '<a class=Link--primary title="tip" href="https://buycycle.com/en-lu/product/floorc" target=_blank rel=noopener>↑ €1,200 (+€200 / +20%) · ≥77d</a>'
    )
    assert (
        lines[2]
        == '<a class=Link--primary title="tip" href="https://buycycle.com/en-lu/product/tiea" target=_blank rel=noopener>↑ €1,500 (+€500 / +50%) · 23d (+1)</a>'
    )
    assert lines[3] == '<span title="tip">priciest</span>'
    assert lines[4] == "–"
    assert "€1,700" in lines[5] and "·" not in lines[5]

    r = subprocess.run(
        [sys.executable, os.path.join(APP, "dashboard", "render.py"), os.path.join(APP, "dashboard", "index.tpl.html"), str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr
    html = (tmp_path / "index-wheels.html").read_text()
    m = re.search(r"view\.sort\(\(a,b\)=>\{.*?\}\);", html)
    assert m
    sort = """
const rows=[{nxd:null,name:'dash'},{nxd:0,name:'zero'},{nxd:23,name:'mid'},{nxd:null,name:'cheap'},{nxd:5,name:'five'}];
let key='nxd', asc=true, view=rows.slice();
%s
if (view.map(r=>r.name).join() !== 'zero,five,mid,dash,cheap') throw new Error('asc '+view.map(r=>r.name));
view=rows.slice(); asc=false;
%s
if (view.map(r=>r.name).slice(0,3).join() !== 'mid,five,zero') throw new Error('desc '+view.map(r=>r.name));
if (view.map(r=>r.name).slice(3).sort().join() !== 'cheap,dash') throw new Error('desc tail '+view.map(r=>r.name));
""" % (m.group(0), m.group(0))
    out = subprocess.run(["node", "-e", sort], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    alerts = open(os.path.join(APP, "tracker", "tracker.py")).read().split("def alerts(", 1)[1].split("\ndef ", 1)[0]
    assert "nxp" not in alerts and "nxd" not in alerts


def test_insights_charts_and_model_table(tmp_path):
    """Scatter dots open the listing, model bars open that model's table, and comps stay split by brake/rim or year."""
    r = subprocess.run(
        [sys.executable, os.path.join(APP, "dashboard", "render.py"), os.path.join(APP, "dashboard", "index.tpl.html"), str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr
    for kind, rule in (("wheels", "brake and rim"), ("bikes", "year within")):
        html = (tmp_path / f"index-{kind}.html").read_text()
        assert "function openPoint" in html and "function openBar" in html and "function tipAsk" in html
        assert "cheapest first — compare prices" in html and rule in html
        assert "Click a dot to open the listing" in html and "Click a bar to compare" in html
        assert "ITEMS.filter(x=>!x.g&&x.b+' '+x.m==k)" in html
        assert "· avg " not in html
    note = next(line for line in open(os.path.join(APP, "dashboard", "index.tpl.html")) if line.startswith("function matchNote"))
    script = (
        """
let KIND='wheels';
%s
if (matchNote({k:'disc',mt:'carbon'}) !== 'disc · carbon') throw new Error('disc');
if (matchNote({}) !== 'any brake · any rim') throw new Error('blank wheel');
KIND='bikes';
if (matchNote({y:2024}) !== '2024') throw new Error('year');
if (matchNote({}) !== 'any year') throw new Error('blank bike');
"""
        % note
    )
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr


def test_insight_charts_use_one_scale(tmp_path):
    """Chart series come from one filtered set, and the value axis ends one step above the peak."""
    r = subprocess.run(
        [sys.executable, os.path.join(APP, "dashboard", "render.py"), os.path.join(APP, "dashboard", "index.tpl.html"), str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr
    html = (tmp_path / "index-wheels.html").read_text()
    assert "mob?600" not in html and "mob?1000" not in html and "mob?8" not in html
    assert "max:100" not in html and "beginAtZero" not in html and "m.t.length>=5" in html and "chartGen" in html
    assert "if(TAB=='insights')renderCharts()" in html
    assert "const ins=chartInputs(view,M)" in html
    assert "Chart.defaults.animation=false" in html and "animation:false" in html and "max:niceMax(rois)" in html
    assert "minmax(96px,1.1fr)" in html and 'style="display:block"' in html
    body = html.split("function chartInputs", 1)[1].split("let chartGen", 1)[0]
    assert "NARROW" not in body and "matchMedia" not in body
    filt = html.split("function filt()", 1)[1].split("const strong=", 1)[0]
    assert "NARROW" not in filt and "matchMedia" not in filt
    lines = [
        line
        for line in html.splitlines()
        if line.startswith("function niceStep")
        or line.startswith("function niceMax")
        or line.startswith("function axisTo")
        or line.startswith("function chartInputs")
        or line.startswith(" const fast")
        or line.startswith(" const sold")
        or line.startswith(" const ed=")
        or line.startswith(" const rc=")
        or line.startswith(" const roi=")
        or line.startswith(" return {profit:")
    ]
    script = (
        "\n".join(lines)
        + """
const cases=[[[4],5],[[0.4,1.2,3.9],4],[[100],110],[[0],1],[[6,2],7],[[6.2],7],[[50],55],[[48],50],[[140],160],[[1200],1400],[[5700],6000],[[],1]];
for (const [v,want] of cases) if (niceMax(v)!==want) throw new Error(JSON.stringify(v)+' -> '+niceMax(v)+' != '+want);
const rows=[
 {b:'Fulcrum',m:'Racing 4',p:800,pf:10,roi:5,cf:'high',d:20,dl:40,rk:[],n:'a',u:'/a'},
 {b:'Fulcrum',m:'Racing 4',p:700,pf:-5,roi:-2,cf:'low',d:10,dl:3,rk:['thin description'],n:'b',u:'/b'},
 {b:'Zipp',m:'303',p:900,pf:1,roi:1,cf:'medium',d:null,dl:200,rk:[],n:'c',u:'/c'},
 {b:'Other',m:'Hidden',p:100,pf:1,roi:1,cf:'high',d:5,dl:40,rk:[],n:'d',u:'/d'}
];
const models={
 'Fulcrum Racing 4':{dts:13,g30:3,a:10,str:6.2},
 'Zipp 303':{dts:95,g30:2,a:4,str:4},
 'Slow One':{dts:140,g30:2,a:4,str:48},
 'Not In View':{dts:1,g30:9,a:9,str:99}
};
const wide=chartInputs(rows, models);
const narrow=chartInputs(rows.slice(), models);
if (JSON.stringify(wide)!==JSON.stringify(narrow)) throw new Error('width copies diverged');
if (wide.fast.map(m=>m[0]+':'+m[1]).join()!=='Fulcrum Racing 4:13,Zipp 303:95') throw new Error('fast '+JSON.stringify(wide.fast));
if (wide.sell.map(m=>m.join(':')).join()!=='Fulcrum Racing 4:6.2,Zipp 303:4') throw new Error('sell '+JSON.stringify(wide.sell));
if (wide.sell.some(m=>m[0]==='Not In View'||m[0]==='Slow One')) throw new Error('unfiltered model');
if (JSON.stringify(wide.days)!==JSON.stringify([1,0,0,2,0,0,1,0])) throw new Error('days '+wide.days);
if (axisTo(wide.sell.map(m=>m[1])).max!==7) throw new Error('sell axis '+JSON.stringify(axisTo(wide.sell.map(m=>m[1]))));
if (axisTo([6.2,4,1]).max!==7) throw new Error('tight sell');
if (wide.discount.length!==3||wide.profit[0].length!==2) throw new Error('scatter '+wide.discount.length+' '+wide.profit[0].length);
"""
    )
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr


def test_desktop_comparables_are_a_full_width_row(tmp_path):
    """The desktop comparables control adds a spanning row, not a stack inside the Reference cell."""
    r = subprocess.run(
        [sys.executable, os.path.join(APP, "dashboard", "render.py"), os.path.join(APP, "dashboard", "index.tpl.html"), str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr
    html = (tmp_path / "index-bikes.html").read_text()
    assert "compsOpen(x)" in html and "data-cx=" in html and "TableGroupHeaderCell" in html
    assert "function card" in html and "compsBtn(x)" in html
    table = html.split("function compTable", 1)[1].split("function toggleComps", 1)[0]
    assert "This listing" in table and "Condition" in table and "Days listed" in table and "Location" in table
    assert "Avg ask" not in table and "zCell" not in table and "next up" not in table
    row = html.split("function row", 1)[1].split("const stat=", 1)[0]
    assert "compsOpen(x)" in row and "compsBtn(x)" not in row and "<details" not in row
    card = html.split("function card", 1)[1].split("function renderList", 1)[0]
    assert "compsBtn(x)" in card
    lines = []
    keep = False
    want = ("function compKey", "function liveGroups", "function liveComps", "function matchNote", "function compList")
    for line in html.splitlines():
        if line.startswith(want):
            keep = True
        elif line.startswith("function "):
            keep = False
        if keep:
            lines.append(line)
    script = (
        "let KIND='wheels';\n"
        + "\n".join(lines)
        + """
const items=[
 {i:'self',b:'Fulcrum',m:'Racing 4',k:'disc',mt:'carbon',y:2020,p:800,c:'3',dl:40,co:'DE',u:'/self',g:null},
 {i:'low',b:'Fulcrum',m:'Racing 4',k:'disc',mt:'carbon',y:2024,p:500,c:'4',dl:12,co:'FR',u:'/low',g:null},
 {i:'high',b:'Fulcrum',m:'Racing 4',k:'disc',mt:'carbon',y:2019,p:1100,c:'2',dl:90,co:'LU',u:'/high',g:null},
 {i:'other',b:'Fulcrum',m:'Racing 4',k:'rim',mt:'carbon',y:2020,p:100,c:'3',dl:1,co:'BE',u:'/other',g:null},
 {i:'gone',b:'Fulcrum',m:'Racing 4',k:'disc',mt:'carbon',y:2020,p:50,c:'3',dl:1,co:'DE',u:'/gone',g:'2026-10-01'}
];
const got=compList(items, items[0]).map(x=>x.i+':'+x.p+':'+matchNote(x));
if (got.join()!=='low:500:disc · carbon,self:800:disc · carbon,high:1100:disc · carbon') throw new Error(got.join());
KIND='bikes';
const bikes=[
 {i:'b',b:'Canyon',m:'Ultimate',y:2024,p:2000,u:'/b',g:null},
 {i:'a',b:'Canyon',m:'Ultimate',y:2023,p:1500,u:'/a',g:null},
 {i:'far',b:'Canyon',m:'Ultimate',y:2018,p:900,u:'/far',g:null}
];
const bg=compList(bikes, bikes[0]).map(x=>x.i);
if (bg.join()!=='a,b') throw new Error(bg.join());
"""
    )
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr + script[:400]


def test_no_feed_key_in_source():
    import re

    pat = re.compile(r"key_[A-Za-z0-9]{16}")
    for root, _, files in os.walk(APP):
        for f in files:
            if f.endswith((".py", ".html", ".md", ".sh", ".toml")):
                assert not pat.search(open(os.path.join(root, f), errors="ignore").read())
