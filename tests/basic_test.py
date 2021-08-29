from .. import state_signals
import subprocess
import time
from multiprocessing import Process

class TestClass:
    def _listener(self, responder):
        for signal in responder.listen():
            print(signal)
            if signal.tag == "bad":
                ras = 0
            else:
                ras = 1
            responder.srespond(signal, ras)

    def _create(self):
        self.redis = subprocess.Popen(["redis-server"])
        responder = state_signals.SignalResponder(responder_name="fakeresp", log_level="DEBUG")
        self.resp_proc = Process(target=self._listener, args=(responder,))
        self.resp_proc.start()
        self.sig_ex = state_signals.SignalExporter("fakemark", log_level="DEBUG")

    def test_init_shutdown(self):
        self._create()
        self.sig_ex.initialize(legal_events=["benchmark-start", "benchmark-stop"])
        assert self.sig_ex.init_listener.is_alive()
        time.sleep(1)
        assert self.sig_ex.subs
        time.sleep(1)

        self.sig_ex.shutdown()
        time.sleep(1)
        assert not self.sig_ex.init_listener.is_alive()
        self.resp_proc.terminate()
        self.redis.terminate()
