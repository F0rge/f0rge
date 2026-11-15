from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import rehearse_restore  # noqa: E402


def test_non_rehearsal_target_is_rejected_before_docker_access(monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError("An unapproved target must not reach Docker")

    monkeypatch.setattr(rehearse_restore, "run", unexpected)
    with pytest.raises(ValueError, match="task-owned"):
        rehearse_restore.verify_container("production", 5549)
    with pytest.raises(ValueError, match="task-owned"):
        rehearse_restore.verify_container("buycycle-migration-pg", 5432)


@pytest.mark.parametrize("address", ["0.0.0.0", "::", "192.0.2.1"])
def test_rehearsal_refuses_a_public_or_nonloopback_database(monkeypatch, address):
    response = [
        {
            "Config": {"Env": ["POSTGRES_DB=buycycle_rehearsal"], "Image": "postgres:17"},
            "NetworkSettings": {"Ports": {"5432/tcp": [{"HostIp": address, "HostPort": "5549"}]}},
        }
    ]
    monkeypatch.setattr(rehearse_restore, "run", lambda *args: json.dumps(response).encode())
    with pytest.raises(ValueError, match="isolated"):
        rehearse_restore.verify_container("buycycle-migration-pg", 5549)


def test_later_acknowledged_write_blocks_old_candidate():
    before = {"user_state": {"rows": 1, "sha256": "older"}, "user_state_history": {"rows": 1, "sha256": "older-history"}}
    latest = {"user_state": {"rows": 1, "sha256": "edited"}, "user_state_history": {"rows": 2, "sha256": "new-history"}}
    with pytest.raises(ValueError, match="stale.*activation is blocked"):
        rehearse_restore.assert_candidate_current(latest, before)
    rehearse_restore.assert_candidate_current(latest, latest)
