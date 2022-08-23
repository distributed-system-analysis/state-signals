from multiprocessing import Process
from pathlib import Path
import pytest
import state_signals
import sys
import time


def _listener(_sig_ex):
    time.sleep(5)
    responder = state_signals.SignalResponder(
        responder_name="fakeresp", log_level="DEBUG"
    )
    responder.lock_id(_sig_ex.pub_id)
    for signal in responder.listen():
        if signal.tag == "bad":
            ras = 0
            message = "I messed up!"
        else:
            ras = 1
            message = "I did it!"
        responder.srespond(signal, ras, message)


class MockSubscriber:
    def __init__(self):
        self.channel = None

    def subscribe(self, channel):
        self.channel = channel


class MockRedis:
    def __init__(self, host, port, db=0):
        self.host = host
        self.port = port
        self.db = db
        self.channels = dict()
        self.subscribers = []

    def ping(self):
        pass

    def pubsub(ignore_subscribe_messages=True):
        sub = MockSubscriber()
        self.subscribers.append(sub)
        return sub

    def publish(channel, message):
        self.channels[channel].append(message)


class TestBasic:
    @pytest.fixture
    def listener_f(self):
        self.sig_ex = state_signals.SignalExporter("fakemark", log_level="DEBUG")
        self.resp_proc = Process(target=_listener, args=(self.sig_ex,), daemon=True)
        self.resp_proc.start()
        yield
        self.sig_ex.shutdown()
        assert not self.sig_ex.init_listener.is_alive()
        self.resp_proc.terminate()
        self.resp_proc = None
        self.sig_ex = None

    @pytest.fixture(autouse=True)
    def init_f(self, listener_f):
        sub_check = self.sig_ex.initialize_and_wait(
            1, legal_events=["benchmark-start", "benchmark-stop"], periodic=True
        )
        return sub_check

    def test_init(self, init_f):
        sub_check = init_f
        assert self.sig_ex.init_listener.is_alive()
        assert sub_check == 0
        assert sig_ex.subs

    def test_good_response(self):
        result, msgs = self.sig_ex.publish_signal(
            "benchmark-start", metadata={"something": "cool info"}
        )
        assert int(result) == 0
        assert "I did it!" in msgs.values()

    def test_bad_response(self):
        result, msgs = self.sig_ex.publish_signal(
            "benchmark-stop", metadata={"tool": "give bad resp"}, tag="bad"
        )
        assert int(result) == 1
        assert "I messed up!" in msgs.values()
