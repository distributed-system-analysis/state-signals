from pathlib import Path
from signal import signal

parent = Path(__file__).resolve().parents[1]
print(parent)

import sys

sys.path.append(str(parent))
print(sys.path)

import pytest
import platform
import redis
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


def test_redis_fail_create_exporter():
    try:
        signal_exp = state_signals.SignalExporter(
            "work plz",
            redis_host="fakehost",
            redis_port=1111,
            log_level="DEBUG",
            conn_timeout=1,
        )
        assert 1 == 0
    except redis.ConnectionError:
        assert 0 == 0


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


def test_redis_fail_create_responder():
    try:
        signal_resp = state_signals.SignalResponder(
            responder_name="also work",
            redis_host="fakehost",
            redis_port=1111,
            log_level="DEBUG",
            conn_timeout=1,
        )
        assert 1 == 0
    except redis.ConnectionError:
        assert 0 == 0


def test_create_logger_fail():
    try:
        state_signals._create_logger("bla", "bla", "bla")
        assert 1 == 0
    except ValueError as e:
        assert e.args[0] == "Legal log levels: [DEBUG, INFO, WARNING, ERROR, CRITICAL]"


def test_create_signal_fail():
    try:
        signal = state_signals.Signal(
            publisher_id="bla",
            process_name="bla",
            event="bla",
            runner_host="bla",
            sample_no="bla",
        )
        assert 1 == 0
    except TypeError as e:
        assert (
            e.args[0]
            == "The field sample_no should be type <class 'int'>, not <class 'str'>"
        )


def test_create_response_fail():
    try:
        resp = state_signals.Response(
            responder_id="bla", publisher_id="bla", event="bla", ras="bla"
        )
        assert 1 == 0
    except TypeError as e:
        assert (
            e.args[0]
            == "The field ras should be type (<class 'int'>, <class 'NoneType'>), not <class 'str'>"
        )


def test_signal_to_json():
    signal = state_signals.Signal(
        publisher_id="bla", process_name="bla", event="bla", runner_host="bla"
    )
    json_str = signal.to_json_str()
    assert (
        json_str
        == '{"publisher_id": "bla", "process_name": "bla", "event": "bla", "runner_host": "bla", "sample_no": -1, "tag": "No tag specified"}'
    )


def test_response_to_json():
    resp = state_signals.Response(
        responder_id="bla", publisher_id="bla", event="bla", ras=1
    )
    json_str = resp.to_json_str()
    assert (
        json_str
        == '{"responder_id": "bla", "publisher_id": "bla", "event": "bla", "ras": 1}'
    )


def test_response_data_checks(mocker):
    mocker.patch("redis.Redis.ping", return_value=0)
    signal_exp = state_signals.SignalExporter(
        "work plz", redis_host="fakehost", redis_port=1111, log_level="DEBUG"
    )

    data = signal_exp._get_data_dict({"bla": 1, "blamore": 2})
    assert data == None

    data = signal_exp._get_data_dict({"bla": 1, "data": "bla"})
    assert data == None

    data = signal_exp._get_data_dict(
        {
            "bla": 1,
            "data": '{"responder_id": "bla", "publisher_id": "bla", "shmevent": "bla"}',
        }
    )
    assert data == None

    data = signal_exp._get_data_dict(
        {
            "bla": 1,
            "data": '{"responder_id": "bla", "publisher_id": "bla", "event": "bla"}',
        }
    )
    assert data == {"event": "bla", "publisher_id": "bla", "responder_id": "bla"}
