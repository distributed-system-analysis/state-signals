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


def _listener(responder):
    for signal in responder.listen():
        if signal.tag == "bad":
            ras = 0
        else:
            ras = 1
        responder.srespond(signal, ras)

sig_ex = state_signals.SignalExporter("fakemark", log_level="DEBUG")
responder = state_signals.SignalResponder(responder_name="fakeresp", log_level="DEBUG")
responder.lock_id(sig_ex.pub_id)
resp_proc = Process(target=_listener, args=(responder,), daemon=True)

def _init():
    resp_proc.start()
    sig_ex.initialize(legal_events=["benchmark-start", "benchmark-stop"])

def _shutdown():
    sig_ex.shutdown()

def _cleanup():
    resp_proc.terminate()

@pytest.mark.dependency()
def test_init():
    _init()
    assert sig_ex.init_listener.is_alive()
    time.sleep(1)
    assert sig_ex.subs

@pytest.mark.dependency(depends=['test_init'])
def test_good_response():
    result = sig_ex.publish_signal("benchmark-start", metadata={"something": "cool info"})
    assert int(result) == 0

@pytest.mark.dependency(depends=['test_good_response'])
def test_bad_response():
    result = sig_ex.publish_signal("benchmark-stop", metadata={"tool": "give bad resp"}, tag="bad")
    assert int(result) == 1

@pytest.mark.dependency('test_bad_response')
def test_shutdown():
    _shutdown()
    assert not sig_ex.init_listener.is_alive()
    _cleanup()
