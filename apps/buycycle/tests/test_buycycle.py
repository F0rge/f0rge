import json
import os
import sqlite3
import subprocess
import sys

import pytest

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


def test_fee_config_matches_dashboard_formula():
    import fees

    bikes = fees.estimate_net_margin("bikes", 1000, 2400)
    sale = 2400 * (1 - 5 / 100)
    cost = 1000 * (1 + 2.5 / 100) + 0 + 125 + 0 + 50 + 75
    net = sale * (1 - 6.95 / 100) - cost
    assert bikes["margin_label"] == "estimate"
    assert bikes["net_margin_eur"] == pytest.approx(net)
    assert bikes["roi_pct"] == pytest.approx(net / cost * 100)
    assert fees.estimate_net_margin("bikes", 1000, None) is None
    wheels = fees.estimate_net_margin("wheels", 100, 200)
    wheel_cost = 100 * (1 + 6 / 100) + 1 + 25 + 10 + 20
    assert wheels["net_margin_eur"] == pytest.approx(200 * 0.95 - wheel_cost)


def test_reference_cohort_matches_dashboard_rules():
    import market

    rows = []
    for listing_id, year, price, gone in (
        ("1", 2020, 1000, None),
        ("2", 2020, 1200, None),
        ("3", 2021, 1400, None),
        ("4", 2020, 1600, "2026-10-01"),
        ("5", 2010, 500, None),
    ):
        row = {"id": listing_id, "name": "Canyon Endurace CF", "brand": "Canyon", "year": year, "price": price, "gone_at": gone, "spec": "{}"}
        assert market.annotate(row, "bikes")
        rows.append(row)
    comps = market.comparable_listings(rows, "bikes")
    assert sorted(item["id"] for item in comps["1"]) == ["2", "3"]
    assert comps["5"] == []


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
    import fees

    bikes_html = (tmp_path / "index-bikes.html").read_text()
    wheels_html = (tmp_path / "index-wheels.html").read_text()
    assert json.dumps(fees.ASSUMPTIONS["bikes"]) in bikes_html
    assert json.dumps(fees.ASSUMPTIONS["wheels"]) in wheels_html


def test_no_feed_key_in_source():
    import re

    pat = re.compile(r"key_[A-Za-z0-9]{16}")
    for root, _, files in os.walk(APP):
        for f in files:
            if f.endswith((".py", ".html", ".md", ".sh", ".toml")):
                assert not pat.search(open(os.path.join(root, f), errors="ignore").read())
