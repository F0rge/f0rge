import os
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

import fees
import storage
from buycycle_mcp.db import connect_readonly, db_path
from buycycle_mcp.queries import get_listing, search_listings, stats, todays_deals
from buycycle_mcp.server import build_runtime, create_server, http_app

NOW = 1_760_720_000
TODAY = datetime(2026, 10, 17, 12, 0, tzinfo=ZoneInfo("Europe/Luxembourg"))
COLS = [
    "id",
    "kind",
    "slug",
    "name",
    "brand",
    "year",
    "size",
    "cond",
    "msrp",
    "price",
    "original_price",
    "activated_at",
    "updated_at",
    "country_id",
    "seller_id",
    "favs",
    "offers",
    "high_demand",
    "n_media",
    "desc_len",
    "spec",
    "first_seen",
    "last_seen",
    "gone_at",
    "last_fetch",
    "fetch_price",
    "pr",
]


def _insert(conn, **fields):
    row = {column: None for column in COLS}
    row.update(spec="{}", first_seen="2026-10-01", last_seen="2026-10-17", activated_at=NOW)
    row.update(fields)
    conn.execute(
        "insert into listing (" + ",".join(COLS) + ") values (" + ",".join("?" * len(COLS)) + ")",
        [row[column] for column in COLS],
    )


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = tmp_path / "buycycle.turso.db"
    conn = sqlite3.connect(path)
    for statement in storage.SCHEMA:
        conn.execute(statement)
    conn.executemany("insert into country_map values(?, ?)", [(150, "Germany"), (151, "France")])
    day = 86400
    _insert(
        conn,
        id="b-deal",
        kind="bikes",
        slug="deal",
        name="Canyon Endurace CF",
        brand="Canyon",
        year=2020,
        size="56",
        price=1000,
        original_price=1500,
        country_id=150,
        activated_at=NOW - 10 * day,
        first_seen="2026-10-17",
    )
    _insert(
        conn,
        id="b-mid",
        kind="bikes",
        slug="mid",
        name="Canyon Endurace CF",
        brand="Canyon",
        year=2020,
        size="54",
        price=2200,
        original_price=2200,
        country_id=151,
        activated_at=NOW - 30 * day,
        first_seen="2026-09-01",
    )
    _insert(
        conn,
        id="b-high",
        kind="bikes",
        slug="high",
        name="Canyon Endurace CF",
        brand="Canyon",
        year=2020,
        size="56",
        price=2400,
        original_price=2400,
        country_id=150,
        activated_at=NOW - 5 * day,
        first_seen="2026-10-01",
    )
    _insert(
        conn,
        id="b-comp",
        kind="bikes",
        slug="comp",
        name="Canyon Endurace CF",
        brand="Canyon",
        year=2020,
        size="M",
        price=2600,
        original_price=3000,
        country_id=150,
        activated_at=NOW - 40 * day,
        first_seen="2026-08-01",
    )
    _insert(
        conn,
        id="b-old",
        kind="bikes",
        slug="old",
        name="Canyon Endurace CF",
        brand="Canyon",
        year=2010,
        size="56",
        price=1800,
        original_price=2000,
        country_id=150,
        activated_at=NOW - 20 * day,
        first_seen="2026-10-01",
    )
    _insert(
        conn,
        id="b-gone",
        kind="bikes",
        slug="gone",
        name="Canyon Endurace CF",
        brand="Canyon",
        year=2020,
        size="56",
        price=900,
        original_price=900,
        country_id=150,
        first_seen="2026-10-17",
        gone_at="2026-10-17",
    )
    _insert(
        conn,
        id="w-new",
        kind="wheels",
        slug="zipp",
        name="Zipp 303 Firecrest",
        brand="Zipp",
        year=2024,
        size="700",
        price=400,
        original_price=400,
        country_id=150,
        first_seen="2026-10-17",
    )
    _insert(
        conn,
        id="w-skip",
        kind="wheels",
        slug="skip",
        name="Zipp 303 Firecrest",
        brand="Zipp",
        year=2024,
        size="700",
        price=50,
        original_price=50,
        country_id=150,
        spec='{"spec": {"wheel-type": "9999"}}',
        first_seen="2026-10-17",
    )
    for index in range(51):
        _insert(
            conn,
            id=f"f{index}",
            kind="bikes",
            slug=f"f{index}",
            name=f"Filler model {index}",
            brand="Filler",
            year=2022,
            size="S",
            price=5000 + index,
            original_price=5000 + index,
            country_id=150,
            first_seen="2026-09-01",
        )
    conn.executemany(
        "insert into price_history values(?, ?, ?)",
        [
            ("b-deal", "2026-10-16", 1200),
            ("b-deal", "2026-10-17", 1000),
            ("b-old", "2026-10-01", 2000),
            ("b-old", "2026-10-16", 1800),
        ],
    )
    conn.execute(
        "insert into detail(id, fetched, country, city) "
        "values('b-deal', '2026-10-17', 'Germany', 'Berlin')"
    )
    conn.execute("insert into runs values('2026-10-17', 'bikes', 1, 10, 2, 0, 0, '')")
    conn.commit()
    conn.close()
    monkeypatch.setenv("BUYCYCLE_DB", str(path))
    return path


def test_search_filters_sort_and_caps_limit(db):
    found = search_listings(kind="bike", brand="Canyon", sort="price", descending=False, now=NOW)
    ids = [row["id"] for row in found["listings"]]
    assert ids[0] == "b-deal"
    assert "b-gone" not in ids and "w-new" not in ids and "w-skip" not in ids
    deal = found["listings"][0]
    assert deal["price_drop_percent"] == 33.3
    assert deal["days_on_market"] == 10.0
    assert deal["country"] == "Germany"
    assert deal["reference_eur"] == 2400
    assert deal["margin_label"] == "estimate"
    expected = fees.estimate_net_margin("bikes", 1000, 2400)
    assert deal["net_margin_eur_estimate"] == round(expected["net_margin_eur"], 2)
    assert deal["roi_pct_estimate"] == round(expected["roi_pct"], 1)
    assert "price_history" not in deal

    priced = search_listings(kind="bikes", price_min=2000, price_max=2300, now=NOW)
    assert [row["id"] for row in priced["listings"]] == ["b-mid"]
    sized = search_listings(kind="bikes", size="56", country="germany", brand="Canyon", now=NOW)
    assert {row["id"] for row in sized["listings"]} == {"b-deal", "b-high", "b-old"}
    aged = search_listings(kind="bike", days_on_market_min=9, days_on_market_max=11, now=NOW)
    assert [row["id"] for row in aged["listings"]] == ["b-deal"]
    dropped = search_listings(kind="bikes", min_price_drop_percent=20, now=NOW)
    assert [row["id"] for row in dropped["listings"]] == ["b-deal"]
    margin = search_listings(kind="bikes", min_net_margin=0, now=NOW)
    assert [row["id"] for row in margin["listings"]] == ["b-deal"]
    wheels = search_listings(kind="wheels", now=NOW)
    assert [row["id"] for row in wheels["listings"]] == ["w-new"]
    assert wheels["listings"][0]["net_margin_eur_estimate"] is None
    assert wheels["listings"][0]["margin_label"] == "estimate"

    capped = search_listings(limit=100, now=NOW)
    assert capped["limit"] == 50
    assert capped["returned"] == 50
    assert capped["matched"] > 50
    assert search_listings(limit=0, now=NOW)["returned"] == 1


def test_get_listing_includes_full_history(db):
    row = get_listing("b-deal", now=NOW)
    assert row["city"] == "Berlin"
    assert row["url"] == "https://buycycle.com/en-lu/product/deal"
    assert row["price_history"] == [
        {"day": "2026-10-16", "price_eur": 1200},
        {"day": "2026-10-17", "price_eur": 1000},
    ]
    assert row["margin_label"] == "estimate"
    with pytest.raises(ValueError):
        get_listing("missing", now=NOW)


def test_todays_deals_uses_luxembourg_day(db):
    result = todays_deals(now=TODAY, clock=NOW)
    assert result["day"] == "2026-10-17"
    assert result["timezone"] == "Europe/Luxembourg"
    assert result["margin_label"] == "estimate"
    assert [row["id"] for row in result["deals"]] == ["b-deal", "w-new"]
    assert result["deals"][0]["why"] == ["new listing", "price drop"]
    assert result["deals"][1]["why"] == ["new listing"]
    yesterday = datetime(2026, 10, 16, 23, 30, tzinfo=ZoneInfo("Europe/Luxembourg"))
    assert todays_deals(now=yesterday, clock=NOW)["day"] == "2026-10-16"
    assert [row["id"] for row in todays_deals(now=yesterday, clock=NOW)["deals"]] == ["b-old"]


def test_stats_reports_run_and_freshness(db):
    report = stats(now=TODAY)
    assert report["last_run_day"] == "2026-10-17"
    assert report["runs"][0]["kind"] == "bikes"
    assert report["counts"]["active_bikes"] >= 5
    assert report["counts"]["price_history"] == 4
    assert report["freshness"]["latest_snapshot_day"] == "2026-10-17"
    assert report["freshness"]["age_days"] == 0
    assert report["fee_assumptions"]["bikes"]["sellfee"] == fees.ASSUMPTIONS["bikes"]["sellfee"]
    assert report["margin_label"] == "estimate"
    assert report["last_run_time"].startswith("2026-") or "T" in report["last_run_time"]


def test_readonly_rejects_writes_and_missing_file(db, tmp_path):
    conn = connect_readonly(str(db))
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("insert into country_map values(9, 'Nope')")
    conn.close()
    missing = tmp_path / "absent.db"
    with pytest.raises(FileNotFoundError):
        connect_readonly(str(missing))
    assert not missing.exists()


def test_readonly_opens_pyturso_file(tmp_path):
    path = tmp_path / "from-turso.db"
    conn = storage.connect(str(path))
    conn.execute("insert into country_map values(1, 'Germany')")
    conn.commit()
    conn.close()
    opened = connect_readonly(str(path))
    assert (
        opened.execute("select country from country_map where cid = 1").fetchone()[0] == "Germany"
    )
    with pytest.raises(sqlite3.OperationalError):
        opened.execute("insert into country_map values(2, 'France')")
    opened.close()


def test_readonly_mount_creates_no_sidecar(tmp_path):
    if os.geteuid() == 0:
        pytest.skip("root ignores directory mode bits")
    path = tmp_path / "buycycle.turso.db"
    conn = sqlite3.connect(path)
    conn.execute("create table t(id int)")
    conn.execute("insert into t values(1)")
    conn.commit()
    conn.close()
    os.chmod(tmp_path, 0o555)
    os.chmod(path, 0o444)
    try:
        opened = connect_readonly(str(path))
        assert opened.execute("select id from t").fetchone()[0] == 1
        assert list(tmp_path.iterdir()) == [path]
        opened.close()
    finally:
        os.chmod(tmp_path, 0o755)
        os.chmod(path, 0o644)


def test_default_db_path_matches_storage(monkeypatch):
    monkeypatch.delenv("BUYCYCLE_DB", raising=False)
    import importlib

    importlib.reload(storage)
    assert os.path.abspath(db_path()) == os.path.abspath(storage.DB)


def test_server_source_has_no_write_sql():
    root = Path(__file__).resolve().parents[1] / "buycycle_mcp"
    text = "\n".join(path.read_text() for path in root.glob("*.py")).lower()
    for word in ("insert ", "update ", "delete ", "drop table", "replace into"):
        assert word not in text


def test_refuses_to_start_without_token():
    env = os.environ.copy()
    env.pop("BUYCYCLE_MCP_TOKEN", None)
    root = Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        [sys.executable, "-m", "buycycle_mcp"], cwd=root, env=env, capture_output=True, text=True
    )
    assert proc.returncode != 0
    assert "BUYCYCLE_MCP_TOKEN" in proc.stderr


def test_blank_token_refuses_to_start(monkeypatch):
    monkeypatch.setenv("BUYCYCLE_MCP_TOKEN", "   ")
    with pytest.raises(SystemExit):
        create_server()


def test_default_port_is_8097(monkeypatch):
    monkeypatch.setenv("BUYCYCLE_MCP_TOKEN", "s3cret-token")
    monkeypatch.delenv("BUYCYCLE_MCP_PORT", raising=False)
    _server, host, port = build_runtime()
    assert host == "0.0.0.0"
    assert port == 8097


def test_tools_and_bearer_auth(monkeypatch):
    monkeypatch.setenv("BUYCYCLE_MCP_TOKEN", "s3cret-token")
    server = create_server()
    names = {tool.name for tool in server._tool_manager.list_tools()}
    assert names == {"search_listings", "get_listing", "todays_deals", "stats"}
    assert "id" in server._tool_manager.get_tool("get_listing").parameters["properties"]

    from starlette.testclient import TestClient

    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "0"},
        },
    }
    headers = {"Accept": "application/json, text/event-stream"}
    app = http_app()
    with TestClient(app) as client:
        missing = client.post("/mcp", json=body, headers=headers)
        assert missing.status_code == 401
        assert "resource_metadata" not in missing.headers.get("www-authenticate", "")
        wrong = client.post("/mcp", json=body, headers={**headers, "Authorization": "Bearer nope"})
        assert wrong.status_code == 401
        authed = client.post(
            "/mcp", json=body, headers={**headers, "Authorization": "Bearer s3cret-token"}
        )
        assert authed.status_code != 401
        assert client.get("/.well-known/oauth-protected-resource").status_code == 404
        assert client.get("/.well-known/oauth-authorization-server").status_code == 404


def test_bad_kind_and_sort(db):
    with pytest.raises(ValueError):
        search_listings(kind="frame", now=NOW)
    with pytest.raises(ValueError):
        search_listings(sort="unknown", now=NOW)
    assert search_listings(brand="'; drop table listing; --", now=NOW)["returned"] == 0
    still = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    assert still.execute("select count(*) from listing").fetchone()[0] > 0
    still.close()
