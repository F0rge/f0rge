#!/usr/bin/env python3
"""One-time copy of the legacy SQLite history (buycycle.db) into the embedded Turso DB, then verify row counts.
Usage: migrate_sqlite_to_turso.py [--src buycycle.db] [--dst buycycle.turso.db]   (refuses to run if dst already has rows)"""

import argparse
import sqlite3
import sys
import os
import storage

ap = argparse.ArgumentParser()
ap.add_argument("--src", default=os.path.join(storage.BASE, "buycycle.db"))
ap.add_argument("--dst", default=storage.DB)
a = ap.parse_args()
src = sqlite3.connect(f"file:{a.src}?mode=ro", uri=True)
dst = storage.connect(a.dst)
if any(dst.execute(f"select count(*) from {t}").fetchone()[0] for t in storage.TABLES):
    sys.exit(f"{a.dst} is not empty; refusing")
ok = True
for t in storage.TABLES:
    cols = [r[1] for r in src.execute(f"pragma table_info({t})")]
    rows = src.execute(f"select {','.join(cols)} from {t}").fetchall()
    sql = f"insert into {t}({','.join(cols)}) values({','.join('?' * len(cols))})"
    for i in range(0, len(rows), 2000):
        for r in rows[i : i + 2000]:
            dst.execute(sql, r)
        dst.commit()
    n_dst = dst.execute(f"select count(*) from {t}").fetchone()[0]
    same = n_dst == len(rows)
    ok &= same
    print(f"{t:14} sqlite={len(rows):7} turso={n_dst:7} {'OK' if same else 'MISMATCH'}")
sys.exit(0 if ok else 1)
