"""Local, durable request accounting; no listing data or database-schema changes."""

from __future__ import annotations

from contextlib import contextmanager
import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import stat
import tempfile
from zoneinfo import ZoneInfo


class SafetyStop(Exception):
    """A collection cannot safely continue; never include upstream URLs."""


class Blocked(SafetyStop):
    pass


class BudgetExhausted(SafetyStop):
    pass


def local_day():
    return dt.datetime.now(ZoneInfo("Europe/Luxembourg")).date().isoformat()


def canonical_db(path):
    return Path(path).expanduser().resolve()


@contextmanager
def collection_lock(path):
    """Nonblocking advisory lock shared by all supported collector invocations."""
    lock_path = str(canonical_db(path)) + "-tracker.lock"
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise SafetyStop("collector lock is not a regular file")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SafetyStop("another collector owns the database lock") from None
        yield
    finally:
        os.close(fd)


class RequestState:
    """One most-recent Luxembourg day; counters are persisted before requests."""

    def __init__(self, path, legacy_data, limit=150):
        self.path = Path(str(canonical_db(path)) + "-tracker-safety.json")
        self.limit = limit
        self.day = local_day()
        try:
            fd = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW)
        except FileNotFoundError:
            # Existing data cannot prove how much legacy collection happened today.
            self.state = self._new_day(hold=legacy_data)
            self._save()
            return
        try:
            with os.fdopen(fd) as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode) or os.fstat(stream.fileno()).st_size > 65536:
                    raise SafetyStop("invalid safety ledger file")
                self.state = json.load(stream)
            self._validate()
        except (ValueError, TypeError, KeyError):
            raise SafetyStop("invalid safety ledger; preserve it and repair under the recovery procedure") from None
        if self.state["day"] > self.day:
            raise SafetyStop("clock moved behind the safety ledger; collection held")
        if self.state["day"] < self.day:
            self.state = self._new_day()
            self._save()

    def _new_day(self, hold=False):
        return {"version": 1, "day": self.day, "detail_attempts": self.limit if hold else 0, "blocked": bool(hold), "pending": False, "feeds": []}

    def _validate(self):
        s = self.state
        if not isinstance(s, dict) or set(s) != {"version", "day", "detail_attempts", "blocked", "pending", "feeds"}:
            raise SafetyStop("invalid safety ledger shape")
        if type(s["version"]) is not int or s["version"] != 1 or not isinstance(s["day"], str):
            raise SafetyStop("unsupported safety ledger version/date")
        if dt.date.fromisoformat(s["day"]).isoformat() != s["day"]:
            raise SafetyStop("invalid safety ledger date")
        if (
            type(s["detail_attempts"]) is not int
            or not 0 <= s["detail_attempts"] <= self.limit
            or type(s["blocked"]) is not bool
            or type(s["pending"]) is not bool
        ):
            raise SafetyStop("invalid safety ledger counters")
        if not isinstance(s["feeds"], list) or any(k not in ("bikes", "wheels") for k in s["feeds"]) or len(set(s["feeds"])) != len(s["feeds"]):
            raise SafetyStop("invalid safety ledger feed claims")

    def _save(self):
        try:
            self._write()
        except OSError:
            raise SafetyStop("safety ledger could not be durably written; collection held") from None

    def _write(self):
        """Atomic replace plus file/directory fsync; any failure forbids the request."""
        fd, temporary = tempfile.mkstemp(prefix=self.path.name + ".", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w") as stream:
                json.dump(self.state, stream, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            directory = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def allowed(self):
        if local_day() != self.day:
            raise SafetyStop("collection crossed a Luxembourg date boundary; resume on the next scheduled run")
        if self.state["blocked"] or self.state["pending"]:
            raise Blocked("collection held for this Luxembourg day")

    def claim_feed(self, kind):
        self.allowed()
        if kind in self.state["feeds"]:
            return False
        self.state["feeds"].append(kind)
        self._save()
        return True

    def before_request(self, detail=False):
        self.allowed()
        if detail:
            if self.state["detail_attempts"] >= self.limit:
                raise BudgetExhausted("daily detail request budget exhausted")
            self.state["detail_attempts"] += 1
        # A crash or failed outcome write leaves uncertainty durably visible.
        self.state["pending"] = True
        self._save()

    def finish_request(self):
        self.state["pending"] = False
        self._save()

    def block(self):
        self.state["blocked"] = True
        self.state["pending"] = False
        self._save()
