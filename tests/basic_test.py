from pathlib import Path

parent = Path(__file__).resolve().parents[1]
print(parent)

import sys

sys.path.append(str(parent))
print(sys.path)

import pytest
import state_signals
import time
from multiprocessing import Process


def _listener():
    time.sleep(5)
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


sig_ex = state_signals.SignalExporter("fakemark", log_level="DEBUG")
resp_proc = Process(target=_listener, daemon=True)


def _init():
    resp_proc.start()
    return sig_ex.initialize_and_wait(
        1, legal_events=["benchmark-start", "benchmark-stop"], periodic=True
    )


def _shutdown():
    sig_ex.shutdown()


def _cleanup():
    resp_proc.terminate()


@pytest.mark.dependency()
def test_init():
    sub_check = _init()
    assert sig_ex.init_listener.is_alive()
    assert sub_check == 0
    assert sig_ex.subs


@pytest.mark.dependency(depends=["test_init"])
def test_good_response():
    result, msgs = sig_ex.publish_signal(
        "benchmark-start", metadata={"something": "cool info"}
    )
    assert int(result) == 0
    assert "I did it!" in msgs.values()


@pytest.mark.dependency(depends=["test_good_response"])
def test_bad_response():
    result, msgs = sig_ex.publish_signal(
        "benchmark-stop", metadata={"tool": "give bad resp"}, tag="bad"
    )
    assert int(result) == 1
    assert "I messed up!" in msgs.values()


@pytest.mark.dependency("test_bad_response")
def test_shutdown():
    _shutdown()
    assert not sig_ex.init_listener.is_alive()
    _cleanup()
