import urllib.error
from unittest.mock import MagicMock, patch

import pytest
from apscheduler.schedulers.blocking import BlockingScheduler

from src import config, db, heartbeat, scheduler

URL = "http://127.0.0.1:8091/ping/web-stalker"


@pytest.fixture
def urlopen():
    response = MagicMock(status=200)
    response.__enter__.return_value = response
    with patch("urllib.request.urlopen", return_value=response) as mock:
        yield mock


def test_send_disabled_without_url(urlopen):
    with patch.object(config, "HEARTBEAT_URL", ""):
        assert heartbeat.send() is False
    urlopen.assert_not_called()


def test_send_uses_short_timeout(urlopen):
    with patch.object(config, "HEARTBEAT_URL", URL + "/"):
        assert heartbeat.send() is True
        assert heartbeat.send("fail") is True
    assert [c.args[0] for c in urlopen.call_args_list] == [URL, URL + "/fail"]
    assert all(c.kwargs["timeout"] == 5 for c in urlopen.call_args_list)


@pytest.mark.parametrize("error", [urllib.error.URLError("refused"), TimeoutError("timed out"), ValueError("bad url")])
def test_send_swallows_errors(error):
    with patch.object(config, "HEARTBEAT_URL", URL), patch("urllib.request.urlopen", side_effect=error):
        assert heartbeat.send() is False


def test_heartbeat_job_added_only_with_url():
    sched = BlockingScheduler(timezone="UTC")
    with patch.object(scheduler, "HEARTBEAT_URL", ""):
        assert scheduler._add_heartbeat_job(sched) is False
    assert sched.get_job("heartbeat") is None

    with patch.object(scheduler, "HEARTBEAT_URL", URL):
        assert scheduler._add_heartbeat_job(sched) is True
    job = sched.get_job("heartbeat")
    assert job.func is heartbeat.send
    assert job.trigger.interval.total_seconds() == 5 * 60


def test_sync_jobs_keeps_the_heartbeat_job(mock_db, sample_job_data):
    sched = BlockingScheduler(timezone="UTC")
    with patch.object(scheduler, "HEARTBEAT_URL", URL):
        scheduler._add_heartbeat_job(sched)
    db.add_job(**sample_job_data)
    scheduler._sync_jobs(sched)
    scheduler._sync_jobs(sched)
    assert sched.get_job("heartbeat") is not None
    assert len(sched.get_jobs()) == 2
