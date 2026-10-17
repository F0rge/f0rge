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
        calc = html.split("function calc(x)", 1)[1].split("function", 1)[0]
        assert "if(x.r==null)return" in calc and "x.av" not in calc
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


def test_no_feed_key_in_source():
    import re

    pat = re.compile(r"key_[A-Za-z0-9]{16}")
    for root, _, files in os.walk(APP):
        for f in files:
            if f.endswith((".py", ".html", ".md", ".sh", ".toml")):
                assert not pat.search(open(os.path.join(root, f), errors="ignore").read())
