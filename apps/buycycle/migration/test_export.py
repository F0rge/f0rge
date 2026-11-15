from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import pytest
import turso

sys.path.insert(0, str(Path(__file__).parent))
from export_legacy import export, digest  # noqa: E402


def source(tmp_path):
    path = tmp_path / "legacy.turso.db"
    connection = turso.connect(str(path))
    for statement in [
        "CREATE TABLE listing(id text primary key,kind text,price int,extra text,gone_at text)",
        "CREATE TABLE price_history(id text,day text,price int,primary key(id,day))",
        "CREATE TABLE detail(id text primary key,seller_rating text,shipping text)",
        "CREATE TABLE runs(day text,kind text,complete int,note text,primary key(day,kind))",
        "CREATE TABLE country_map(cid int primary key,country text)",
    ]:
        connection.execute(statement)
    connection.execute("INSERT INTO listing VALUES(?,?,?,?,?)", ("synthetic-1", "bikes", 1234, "café", None))
    connection.execute("INSERT INTO price_history VALUES(?,?,?)", ("synthetic-1", "2026-01-01", 1500))
    connection.execute("INSERT INTO detail VALUES(?,?,?)", ("synthetic-1", "4.9", None))
    connection.execute("INSERT INTO runs VALUES(?,?,?,?)", ("2026-01-01", "bikes", 0, "incomplete"))
    connection.execute("INSERT INTO country_map VALUES(?,?)", (150, "Germany"))
    connection.commit()
    connection.close()
    return path


def test_actual_turso_export_retains_every_table_column_null_and_source(tmp_path):
    path = source(tmp_path)
    ledger = {"version": 1, "day": "2026-01-01", "detail_attempts": 41, "blocked": False, "pending": False, "feeds": ["bikes"]}
    Path(str(path) + "-tracker-safety.json").write_text(json.dumps(ledger))
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    target = tmp_path / "private-export.json"
    result = export(path, target, "synthetic-code-sha")
    bundle = json.loads(target.read_text())
    assert result["tables"] == {name: 1 for name in ("listing", "price_history", "detail", "runs", "country_map")}
    assert bundle["tables"]["listing"][0]["extra"] == "café"
    assert bundle["tables"]["listing"][0]["gone_at"] is None
    assert bundle["tables"]["detail"][0]["seller_rating"] == "4.9"
    assert bundle["safety_ledger"] == ledger
    for table, rows in bundle["tables"].items():
        assert bundle["table_sha256"][table] == digest(rows)
        assert bundle["source_schema"][table]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    assert target.stat().st_mode & 0o777 == 0o600
    with pytest.raises(ValueError, match="overwrite"):
        export(path, target, "synthetic-code-sha")


def test_export_rejects_unexpected_tables_without_modifying_original(tmp_path):
    path = source(tmp_path)
    connection = turso.connect(str(path))
    connection.execute("CREATE TABLE future_data(value text)")
    connection.commit()
    connection.close()
    before = path.read_bytes()
    with pytest.raises(ValueError, match="Unexpected legacy tables"):
        export(path, tmp_path / "output.json", "unknown-legacy")
    assert path.read_bytes() == before
    assert not (tmp_path / "output.json").exists()


def test_export_rejects_symlink_source_and_destination(tmp_path):
    path = source(tmp_path)
    link = tmp_path / "linked.db"
    link.symlink_to(path)
    with pytest.raises(ValueError):
        export(link, tmp_path / "output.json", "unknown-legacy")
    output = tmp_path / "output.json"
    output.symlink_to(tmp_path / "outside.json")
    with pytest.raises(ValueError):
        export(path, output, "unknown-legacy")
    assert not (tmp_path / "outside.json").exists()
