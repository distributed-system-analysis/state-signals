from logging import shutdown
from pathlib import Path

parent = Path(__file__).resolve().parents[1]
print(parent)

import sys

sys.path.append(str(parent))
print(sys.path)

import pytest
import state_signals
import time
import redis
from multiprocessing import Process


def _listener():
    time.sleep(3)
    responder = state_signals.SignalResponder(
        responder_name="fakeresp", log_level="DEBUG"
    )
    responder.lock_id(sig_ex.pub_id)
    for signal in responder.listen():
        if signal.tag == "bad":
            ras = 0
            message = "I messed up!"
        else:
            ras = 1
            message = "I did it!"
        responder.srespond(signal, ras, message)


def _lock_tester():
    responder = state_signals.SignalResponder(
        responder_name="fakeresp", log_level="DEBUG"
    )
    for signal in responder.listen():
        if signal.event == "initialization":
            responder.lock_tag("locked")
            responder.lock_id(sig_ex.pub_id)
        if signal.tag == "locked":
            responder.unlock()
        responder.srespond(signal, 1, "Matched")


sig_ex = state_signals.SignalExporter("fakemark", log_level="DEBUG")
resp_proc = None


def _start_resp():
    global resp_proc
    resp_proc = Process(target=_listener, daemon=True)
    resp_proc.start()


def _init():
    return sig_ex.initialize_and_wait(
        1, legal_events=["benchmark-start", "benchmark-stop"], periodic=True, timeout=6
    )


def _shutdown():
    sig_ex.shutdown()


def _cleanup():
    resp_proc.terminate()


def test_existing_conns():
    redis_conn = redis.Redis(host="localhost", port="6379", db=0)
    try:
        sig_ex_test = state_signals.SignalExporter(
            "exist_conn", existing_redis_conn=redis_conn
        )
        sig_resp_test = state_signals.SignalResponder(existing_redis_conn=redis_conn)
    except redis.ConnectionError:
        assert 1 == 0
    assert sig_ex_test.pub_id
    assert sig_resp_test.responder_id


def test_basic_start_sub_stop():
    _start_resp()
    sub_check = _init()
    assert sig_ex.init_listener.is_alive()
    assert sub_check == 0
    assert sig_ex.subs
    _shutdown()
    assert not sig_ex.init_listener.is_alive()
    assert not sig_ex.subs
    _cleanup()


def test_response_flow():
    _start_resp()
    sub_check = _init()
    try:
        sig_ex.publish_signal("illegal")
        assert 0 == 1
    except ValueError as e:
        assert (
            e.args[0]
            == "Event illegal not one of legal events: ['benchmark-start', 'benchmark-stop']"
        )
    result, msgs = sig_ex.publish_signal(
        "benchmark-start", metadata={"something": "cool info"}
    )
    assert int(result) == 0
    assert "I did it!" in msgs.values()
    result, msgs = sig_ex.publish_signal(
        "benchmark-stop", metadata={"something": "cool info"}, timeout=-1
    )
    assert int(result) == 0
    assert "I did it!" in msgs.values()

    result, msgs = sig_ex.publish_signal(
        "benchmark-stop", metadata={"tool": "give bad resp"}, tag="bad"
    )
    assert int(result) == 1
    assert "I messed up!" in msgs.values()
    _shutdown()
    _cleanup()


def test_unknown_resp_and_timeout():
    _start_resp()
    sub_check = _init()
    sig_ex.subs = ["fake"]
    result, msgs = sig_ex.publish_signal(
        "benchmark-start", metadata={"something": "cool info"}, timeout=2
    )
    assert int(result) == 2
    assert "I did it!" in msgs.values()
    _shutdown()
    _cleanup()


def test_init_timeout():
    sub_check = _init()
    assert sub_check == 1
    _shutdown()


def test_expected_resps():
    sig_ex.initialize(legal_events=["bla"], expected_resps=["testo"])
    assert sig_ex.subs == {"testo"}
    _shutdown()


def test_resp_lock_tag():
    resp_proc = Process(target=_lock_tester, daemon=True)
    resp_proc.start()
    sub_check = _init()
    result, msgs = sig_ex.publish_signal("benchmark-start", timeout=2)
    assert int(result) == 2
    result, msgs = sig_ex.publish_signal("benchmark-start", tag="locked", timeout=2)
    assert int(result) == 0
    assert "Matched" in msgs.values()
    result, msgs = sig_ex.publish_signal("benchmark-start", timeout=2)
    assert int(result) == 0
    assert "Matched" in msgs.values()
    _shutdown()
    resp_proc.terminate()
