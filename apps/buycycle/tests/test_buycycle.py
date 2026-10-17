import os
import sqlite3
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


def test_no_feed_key_in_source():
    import re

    pat = re.compile(r"key_[A-Za-z0-9]{16}")
    for root, _, files in os.walk(APP):
        for f in files:
            if f.endswith((".py", ".html", ".md", ".sh", ".toml")):
                assert not pat.search(open(os.path.join(root, f), errors="ignore").read())
