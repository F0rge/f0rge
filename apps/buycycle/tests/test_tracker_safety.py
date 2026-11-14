from __future__ import annotations

import io
import json
import urllib.error
from urllib.parse import parse_qs, urlsplit

import pytest
import storage
import tracker


def test_first_block_stops_without_retry(monkeypatch):
    calls, sleeps = [], []

    def upstream(request, **kwargs):
        calls.append(request.full_url)
        raise urllib.error.HTTPError(request.full_url, 429, "blocked", {}, None)

    monkeypatch.setattr(tracker, "open_url", upstream)
    monkeypatch.setattr(tracker.time, "sleep", sleeps.append)
    with pytest.raises(tracker.Blocked):
        tracker.get("https://example.invalid/feed?key=secret")
    assert len(calls) == 1
    assert sleeps == [120]


def test_repeated_page_is_incomplete_and_preserves_old_listing(tmp_path, monkeypatch):
    c = storage.connect(str(tmp_path / "fixture.turso.db"))
    c.execute("insert into listing(id,kind,name,brand,price,first_seen,last_seen) values('old','wheels','Old','Brand',100,'2026-01-01','2026-01-01')")
    c.commit()

    def upstream(request, **kwargs):
        page = int(parse_qs(urlsplit(request.full_url).query)["page"][0])
        items = [{"value": "Wheel", "data": {"id": str(((page - 1) % 3) * 200 + n), "price": 100}} for n in range(200)]
        return io.BytesIO(json.dumps({"response": {"results": items}}).encode())

    monkeypatch.setattr(tracker, "open_url", upstream)
    monkeypatch.setattr(tracker.time, "sleep", lambda _: None)
    assert tracker.scrape(c, "wheels", "2026-11-14") is False
    assert c.execute("select gone_at from listing where id='old'").fetchone()[0] is None


def test_unrecognized_detail_does_not_write_success(tmp_path, monkeypatch):
    c = storage.connect(str(tmp_path / "fixture.turso.db"))
    monkeypatch.setattr(tracker, "open_url", lambda *args, **kwargs: io.BytesIO(b"<html>Unexpected upstream page</html>"))
    with pytest.raises(ValueError):
        tracker.fetch_detail(c, "item", "item")
    assert c.execute("select count(*) from detail").fetchone()[0] == 0


def clock(monkeypatch, day="2026-11-14"):
    import safety

    monkeypatch.setattr(safety, "local_day", lambda: day)
    monkeypatch.setattr(tracker, "local_day", lambda: day)
    return day


def runtime(tmp_path, monkeypatch, initialize=True):
    import safety

    day = clock(monkeypatch)
    path = str(tmp_path / "fixture.turso.db")
    monkeypatch.setattr(tracker, "DB", path)
    monkeypatch.setattr(tracker, "OUT", {"bikes": str(tmp_path / "bikes"), "wheels": str(tmp_path / "wheels")})
    if initialize:
        with safety.collection_lock(path):
            safety.RequestState(path, legacy_data=False)
    monkeypatch.setattr(tracker.time, "sleep", lambda _: None)
    return path, day


def invoke(monkeypatch, *arguments):
    import sys

    monkeypatch.setattr(sys, "argv", ["tracker.py", *arguments])
    return tracker.main()


def insert_listing(c, lid="old", kind="wheels", price=100, name="Series test"):
    c.execute(
        "insert into listing(id,kind,slug,name,brand,price,original_price,n_media,desc_len,spec,first_seen,last_seen) values(?,?,?,?,?,?,?,?,?,?,?,?)",
        (lid, kind, lid, name, "Brand", price, price, 6, 100, "{}", "2026-10-01", "2026-11-13"),
    )


def detail_response(lid):
    obj = {"id": lid, "slug": lid, "price": 100, "status": "active"}
    payload = json.dumps(obj, separators=(",", ":"))
    return io.BytesIO(("<script>self.__next_f.push([1," + json.dumps(payload) + "])</script>").encode())


def test_global_detail_budget_counts_attempts_across_kinds_and_restarts(tmp_path, monkeypatch):
    import safety

    path, _ = runtime(tmp_path, monkeypatch)
    c = storage.connect(path)
    for kind in ("bikes", "wheels"):
        for group in range(100):
            for n, price in enumerate((100, 1000, 1000, 1000)):
                insert_listing(c, f"{kind}-{group}-{n}", kind, price, f"Series q{group}")
    c.commit()
    c.close()
    calls = []

    def upstream(request, **kwargs):
        lid = request.full_url.rsplit("/", 1)[-1]
        calls.append(lid)
        # A failed request still spends budget and remains retryable.
        if len(calls) <= 2:
            raise OSError("transport failed")
        return detail_response(lid)

    monkeypatch.setattr(tracker, "open_url", upstream)
    assert invoke(monkeypatch, "--no-scrape") == 1
    assert len(calls) == 150
    assert any(x.startswith("bikes-") for x in calls) and any(x.startswith("wheels-") for x in calls)
    assert invoke(monkeypatch, "--no-scrape", "--kind", "wheels") == 0
    assert len(calls) == 150
    with safety.collection_lock(path):
        assert safety.RequestState(path, legacy_data=True).state["detail_attempts"] == 150
    c = storage.connect(path)
    assert c.execute("select count(*) from listing").fetchone()[0] == 800
    assert c.execute("select fetch_price from listing where id=?", (calls[0],)).fetchone()[0] is None
    assert c.execute("select count(*) from detail").fetchone()[0] == 148
    c.close()


@pytest.mark.parametrize("code", [403, 429])
def test_feed_block_is_durable_global_and_preserves_existing_history(tmp_path, monkeypatch, code, capsys):
    path, day = runtime(tmp_path, monkeypatch)
    c = storage.connect(path)
    insert_listing(c)
    c.execute("insert into price_history values('old','2026-11-13',100)")
    c.commit()
    c.close()
    calls, sleeps = [], []

    def upstream(request, **kwargs):
        calls.append(request.full_url)
        raise urllib.error.HTTPError(request.full_url, code, "secret upstream", {}, None)

    monkeypatch.setattr(tracker, "K", "do-not-log-key")
    monkeypatch.setattr(tracker, "open_url", upstream)
    monkeypatch.setattr(tracker.time, "sleep", sleeps.append)
    assert invoke(monkeypatch) == 1
    assert invoke(monkeypatch, "--kind", "wheels", "--no-scrape") == 1
    assert len(calls) == 1 and sleeps == [120]
    assert "do-not-log-key" not in capsys.readouterr().out
    c = storage.connect(path)
    assert c.execute("select gone_at from listing where id='old'").fetchone()[0] is None
    assert c.execute("select count(*) from price_history").fetchone()[0] == 1
    assert c.execute("select complete from runs where day=? and kind=?", (day, "bikes")).fetchone()[0] == 0
    c.close()


def test_missing_state_on_legacy_database_holds_only_activation_day(tmp_path, monkeypatch):
    import safety

    path, _ = runtime(tmp_path, monkeypatch, initialize=False)
    c = storage.connect(path)
    insert_listing(c)
    c.commit()
    c.close()
    calls = []
    monkeypatch.setattr(tracker, "open_url", lambda request, **kw: calls.append(request.full_url) or io.BytesIO(b'{"response":{"results":[]}}'))
    assert invoke(monkeypatch, "--no-fetch") == 1
    assert calls == []
    clock(monkeypatch, "2026-11-15")
    assert invoke(monkeypatch, "--no-fetch") == 0
    assert len(calls) == 3
    with safety.collection_lock(path):
        assert safety.RequestState(path, legacy_data=True).state["day"] == "2026-11-15"


def test_corrupt_state_is_preserved_and_all_network_held(tmp_path, monkeypatch):
    from pathlib import Path

    path, _ = runtime(tmp_path, monkeypatch)
    ledger = Path(path + "-tracker-safety.json")
    ledger.write_text("{broken")
    monkeypatch.setattr(tracker, "open_url", lambda *a, **k: pytest.fail("network forbidden"))
    assert invoke(monkeypatch) == 1
    assert ledger.read_text() == "{broken"
    # Offline publishing is available and does not repair/reset the ledger.
    assert invoke(monkeypatch, "--no-scrape", "--no-fetch") == 0
    assert ledger.read_text() == "{broken"


def test_feed_claim_survives_failed_attempt_and_process_reentry(tmp_path, monkeypatch):
    path, day = runtime(tmp_path, monkeypatch)
    calls = []

    def upstream(request, **kwargs):
        calls.append(request.full_url)
        raise OSError("feed unavailable")

    monkeypatch.setattr(tracker, "open_url", upstream)
    assert invoke(monkeypatch, "--kind", "wheels", "--no-fetch") == 1
    assert invoke(monkeypatch, "--kind", "wheels", "--no-fetch") == 1
    assert len(calls) == 1
    c = storage.connect(path)
    assert c.execute("select complete from runs where day=?", (day,)).fetchone()[0] == 0
    c.close()


def test_clock_rollback_and_midnight_never_open_a_new_budget(tmp_path, monkeypatch):
    import safety

    path, _ = runtime(tmp_path, monkeypatch)
    state = safety.RequestState(path, legacy_data=False)
    state.before_request(detail=True)
    clock(monkeypatch, "2026-11-15")
    with pytest.raises(safety.SafetyStop):
        state.before_request(detail=True)
    clock(monkeypatch, "2026-11-13")
    with pytest.raises(safety.SafetyStop):
        safety.RequestState(path, legacy_data=False)


@pytest.mark.parametrize("results", [None, {}, [{"value": "x", "data": {"price": 100}}]])
def test_malformed_feed_does_not_mark_missing_listing_gone(tmp_path, monkeypatch, results):
    c = storage.connect(str(tmp_path / "fixture.turso.db"))
    insert_listing(c)
    c.commit()
    monkeypatch.setattr(tracker, "open_url", lambda *a, **kw: io.BytesIO(json.dumps({"response": {"results": results}}).encode()))
    assert tracker.scrape(c, "wheels", "2026-11-14") is False
    assert c.execute("select gone_at from listing where id='old'").fetchone()[0] is None
    c.close()


def test_short_page_with_more_reported_results_is_incomplete(tmp_path, monkeypatch):
    c = storage.connect(str(tmp_path / "fixture.turso.db"))
    monkeypatch.setattr(tracker, "open_url", lambda *a, **kw: io.BytesIO(b'{"response":{"results":[],"total_num_results":600}}'))
    assert tracker.scrape(c, "wheels", "2026-11-14") is False
    c.close()


@pytest.mark.parametrize("price", [None, 0, -1, True])
def test_present_but_unpriced_listing_never_enables_disappearance(tmp_path, monkeypatch, price):
    c = storage.connect(str(tmp_path / "fixture.turso.db"))
    insert_listing(c)
    c.commit()
    items = [{"value": "Wheel", "data": {"id": str(n), "price": 100}} for n in range(600)]
    items.append({"value": "Old", "data": {"id": "old", "price": price}})

    def upstream(request, **kwargs):
        page = int(parse_qs(urlsplit(request.full_url).query)["page"][0])
        return io.BytesIO(json.dumps({"response": {"results": items[(page - 1) * 200 : page * 200]}}).encode())

    monkeypatch.setattr(tracker, "open_url", upstream)
    monkeypatch.setattr(tracker.time, "sleep", lambda _: None)
    assert tracker.scrape(c, "wheels", "2026-11-14") is False
    assert c.execute("select gone_at from listing where id='old'").fetchone()[0] is None
    assert c.execute("select price from listing where id='old'").fetchone()[0] == 100
    c.close()


def test_feed_transport_errors_are_paced_and_exit_unsuccessfully(tmp_path, monkeypatch):
    runtime(tmp_path, monkeypatch)
    events = []

    def upstream(request, **kwargs):
        events.append("request")
        raise OSError("failure with private URL and key")

    monkeypatch.setattr(tracker, "open_url", upstream)
    monkeypatch.setattr(tracker.time, "sleep", events.append)
    assert invoke(monkeypatch, "--no-fetch") == 1
    assert events == ["request", 1.6, "request", 1.6]


def subprocess_environment(path, tmp_path):
    import os
    from pathlib import Path

    env = os.environ.copy()
    env.update(
        BUYCYCLE_DB=path,
        BUYCYCLE_OUT_BIKES=str(tmp_path / "bikes"),
        BUYCYCLE_OUT_WHEELS=str(tmp_path / "wheels"),
        PYTHONPATH=str(Path(tracker.__file__).parent),
        BUYCYCLE_FORCE="1",
    )
    env.pop("BUYCYCLE_API_KEY", None)
    return env


def test_process_lock_precedes_database_open_and_releases_after_exit(tmp_path):
    import subprocess
    import sys
    from pathlib import Path
    import safety

    path = str(tmp_path / "fixture.turso.db")
    alias = tmp_path / "alias"
    alias.symlink_to(tmp_path, target_is_directory=True)
    env = subprocess_environment(str(alias / "fixture.turso.db"), tmp_path)
    command = [sys.executable, tracker.__file__, "--no-scrape", "--no-fetch"]
    with safety.collection_lock(path):
        result = subprocess.run(command, capture_output=True, text=True, env=env)
        assert result.returncode == 1
        assert not Path(path).exists()
    result = subprocess.run(command, capture_output=True, text=True, env=env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert Path(path).exists()
    assert not Path(path + "-tracker-safety.json").exists()


def test_reserved_budget_survives_process_crash_and_lock_is_released(tmp_path):
    import subprocess
    import sys
    import safety

    path = str(tmp_path / "fixture.turso.db")
    env = subprocess_environment(path, tmp_path)
    script = """
import os
from safety import collection_lock, RequestState
with collection_lock(os.environ['BUYCYCLE_DB']):
    state = RequestState(os.environ['BUYCYCLE_DB'], legacy_data=False)
    state.before_request(detail=True)
    os._exit(7)
"""
    result = subprocess.run([sys.executable, "-c", script], env=env, capture_output=True, text=True)
    assert result.returncode == 7
    with safety.collection_lock(path):
        state = safety.RequestState(path, legacy_data=False)
        assert state.state["detail_attempts"] == 1


def test_full_cli_budget_survives_separate_processes(tmp_path, monkeypatch):
    import subprocess
    import sys
    import safety

    # Use the actual current day in subprocesses; only synthetic transport and sleep are replaced.
    path = str(tmp_path / "fixture.turso.db")
    c = storage.connect(path)
    for n, price in enumerate((100, 1000, 1000, 1000)):
        insert_listing(c, str(n), price=price)
    c.commit()
    c.close()
    del c
    import gc

    gc.collect()
    with safety.collection_lock(path):
        state = safety.RequestState(path, legacy_data=False)
        for _ in range(149):
            state.before_request(detail=True)
            state.finish_request()
    script = """
import io, json, sys
import tracker
tracker.time.sleep = lambda _: None
def transport(request, **kwargs):
    print('SYNTHETIC_DETAIL_REQUEST')
    lid = request.full_url.rsplit('/', 1)[-1]
    payload = json.dumps({'id':lid,'slug':lid,'price':100}, separators=(',',':'))
    return io.BytesIO(('<script>self.__next_f.push([1,'+json.dumps(payload)+'])</script>').encode())
tracker.open_url = transport
sys.argv = ['tracker.py','--no-scrape','--kind','wheels']
raise SystemExit(tracker.main())
"""
    env = subprocess_environment(path, tmp_path)
    first = subprocess.run([sys.executable, "-c", script], env=env, capture_output=True, text=True)
    second = subprocess.run([sys.executable, "-c", script], env=env, capture_output=True, text=True)
    assert first.returncode == second.returncode == 0, first.stderr + second.stderr
    assert first.stdout.count("SYNTHETIC_DETAIL_REQUEST") == 1
    assert "SYNTHETIC_DETAIL_REQUEST" not in second.stdout
    with safety.collection_lock(path):
        assert safety.RequestState(path, legacy_data=True).state["detail_attempts"] == 150


def test_redirect_does_not_hide_additional_http_requests(tmp_path, monkeypatch):
    import http.server
    import threading

    seen = []

    class Redirect(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append(self.path)
            self.send_response(302)
            self.send_header("Location", "/hidden-extra-request")
            self.end_headers()

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Redirect)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(tracker.time, "sleep", lambda _: None)
    try:
        with pytest.raises(urllib.error.HTTPError) as caught:
            tracker.get(f"http://127.0.0.1:{server.server_port}/first", js=False)
        assert caught.value.code == 302
        assert seen == ["/first"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_ledger_write_failure_cannot_reach_transport(tmp_path, monkeypatch):
    import safety

    path, _ = runtime(tmp_path, monkeypatch)
    state = safety.RequestState(path, legacy_data=False)
    monkeypatch.setattr(tracker, "_REQUEST_STATE", state)
    monkeypatch.setattr(safety.os, "replace", lambda *args: (_ for _ in ()).throw(OSError("disk full")))
    monkeypatch.setattr(tracker, "open_url", lambda *a, **k: pytest.fail("no request before durable reservation"))
    with pytest.raises(safety.SafetyStop):
        tracker.get("https://example.invalid/detail", js=False)


def test_failed_block_write_leaves_durable_uncertainty_across_restart(tmp_path, monkeypatch):
    import safety

    path, _ = runtime(tmp_path, monkeypatch)
    calls = []

    def upstream(request, **kwargs):
        calls.append(request.full_url)
        raise urllib.error.HTTPError(request.full_url, 429, "blocked", {}, None)

    monkeypatch.setattr(tracker, "open_url", upstream)
    original = safety.RequestState._write

    def unavailable_on_block(state):
        if state.state["blocked"]:
            raise OSError("disk failure")
        original(state)

    with monkeypatch.context() as patch:
        patch.setattr(safety.RequestState, "_write", unavailable_on_block)
        assert invoke(monkeypatch, "--no-fetch") == 1
    assert invoke(monkeypatch, "--no-fetch") == 1
    assert len(calls) == 1
    with safety.collection_lock(path):
        state = safety.RequestState(path, legacy_data=True)
        assert state.state["pending"] is True
        with pytest.raises(safety.Blocked):
            state.allowed()


@pytest.mark.parametrize("interruption", [KeyboardInterrupt, SystemExit])
def test_interrupted_request_preserves_pending_hold(tmp_path, monkeypatch, interruption):
    import safety

    path, _ = runtime(tmp_path, monkeypatch)
    state = safety.RequestState(path, legacy_data=False)
    monkeypatch.setattr(tracker, "_REQUEST_STATE", state)
    monkeypatch.setattr(tracker, "open_url", lambda *args, **kw: (_ for _ in ()).throw(interruption()))
    with pytest.raises(interruption):
        tracker.get("https://example.invalid/detail", js=False)
    recovered = safety.RequestState(path, legacy_data=True)
    assert recovered.state["pending"] is True
    assert recovered.state["detail_attempts"] == 1
    with pytest.raises(safety.Blocked):
        recovered.allowed()


@pytest.mark.parametrize("totals", [(600, 500), (1, 1)])
def test_contradictory_feed_totals_never_enable_disappearance(tmp_path, monkeypatch, totals):
    c = storage.connect(str(tmp_path / "fixture.turso.db"))
    insert_listing(c)
    c.commit()

    def upstream(request, **kwargs):
        page = int(parse_qs(urlsplit(request.full_url).query)["page"][0])
        results = [{"value": "Wheel", "data": {"id": str((page - 1) * 200 + n), "price": 100}} for n in range(200)] if page < 4 else []
        total = totals[min(page - 1, 1)]
        return io.BytesIO(json.dumps({"response": {"results": results, "total_num_results": total}}).encode())

    monkeypatch.setattr(tracker, "open_url", upstream)
    monkeypatch.setattr(tracker.time, "sleep", lambda _: None)
    assert tracker.scrape(c, "wheels", "2026-11-14") is False
    assert c.execute("select gone_at from listing where id='old'").fetchone()[0] is None
    c.close()


def test_unique_full_pages_without_terminal_page_are_incomplete(tmp_path, monkeypatch):
    c = storage.connect(str(tmp_path / "fixture.turso.db"))
    insert_listing(c)
    c.commit()
    calls = []

    def upstream(request, **kwargs):
        page = int(parse_qs(urlsplit(request.full_url).query)["page"][0])
        calls.append(page)
        items = [{"value": "Wheel", "data": {"id": str((page - 1) * 200 + n), "price": 100}} for n in range(200)]
        return io.BytesIO(json.dumps({"response": {"results": items}}).encode())

    monkeypatch.setattr(tracker, "open_url", upstream)
    monkeypatch.setattr(tracker.time, "sleep", lambda _: None)
    assert tracker.scrape(c, "wheels", "2026-11-14") is False
    assert calls == list(range(1, 120))
    assert c.execute("select gone_at from listing where id='old'").fetchone()[0] is None
    c.close()
