from pathlib import Path

parent = Path(__file__).resolve().parents[1]
print(parent)

import sys

sys.path.append(str(parent))
print(sys.path)

import pytest
import platform
import state_signals


def test_redis_mocking_create_exporter(mocker):
    mocker.patch("redis.Redis.ping", return_value=0)
    signal_exp = state_signals.SignalExporter(
        "work plz", redis_host="fakehost", redis_port=1111, log_level="DEBUG"
    )
    assert signal_exp.proc_name == "work plz"
    assert signal_exp.pub_id.startswith(signal_exp.proc_name)
    assert signal_exp.runner_host == platform.node()
    assert signal_exp.redis.connection_pool.connection_kwargs["host"] == "fakehost"
    assert signal_exp.redis.connection_pool.connection_kwargs["port"] == 1111
    assert signal_exp.logger.level == 10


def test_redis_mocking_create_responder(mocker):
    mocker.patch("redis.Redis.ping", return_value=0)
    mocker.patch("redis.client.PubSub.subscribe", return_value=None)
    signal_resp = state_signals.SignalResponder(
        responder_name="also work",
        redis_host="fakehost",
        redis_port=1111,
        log_level="DEBUG",
    )
    assert signal_resp.responder_id.startswith("also work")
    assert signal_resp.redis.connection_pool.connection_kwargs["host"] == "fakehost"
    assert signal_resp.redis.connection_pool.connection_kwargs["port"] == 1111
    assert signal_resp.logger.level == 10
