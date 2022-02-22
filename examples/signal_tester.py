import state_signals
import time
from multiprocessing import Process


def _listener():
    time.sleep(5)
    responder = state_signals.SignalResponder(
        responder_name="fakeresp", log_level="DEBUG"
    )
    for signal in responder.listen():
        print(signal)
        if signal.tag == "bad":
            ras = 0
        else:
            ras = 1
        # responder.respond(signal.publisher_id, signal.event, ras)
        responder.srespond(signal, ras)


init = Process(target=_listener)
init.start()

sig_ex = state_signals.SignalExporter("fakemark", log_level="DEBUG")
print("\nBENCHMARK INIT TEST\n")
sig_ex.initialize_and_wait(
    1, legal_events=["benchmark-start", "benchmark-stop"], periodic=True
)
print("Proof of response (subs): " + str(sig_ex.subs))
time.sleep(1)

print("\nBENCHMARK START TEST\n")
result, _ = sig_ex.publish_signal(
    "benchmark-start", metadata={"something": "cool info"}
)
print(f"SUBS CLEARED! Result code: {result}")
time.sleep(1)

print("\nBENCHMARK STOP TEST\n")
result, _ = sig_ex.publish_signal(
    "benchmark-stop", metadata={"tool": "give bad resp"}, tag="bad"
)
print(f"SUBS CLEARED! Result code: {result}")
time.sleep(1)

print("\nBENCHMARK SHUTDOWN TEST\n")
print("Listening: " + str(sig_ex.init_listener.is_alive()))
sig_ex.shutdown()
print("Listening: " + str(sig_ex.init_listener.is_alive()))
print("NO LONGER LISTENING, DONE")

init.terminate()
