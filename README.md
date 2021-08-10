# state-signals
A temporary repo for testing packaging and getting a demo package available

NOTE: License will likely be changed when moved to official repo, just in place here for safety in meantime

# State/Event Signal Module

Adds two new, simple-to-use objects:
 - SignalExporter      (for publishing state signals and handling subscribers + responses)
 - SignalResponder     (for receiving state signals, locking onto publishers, and publishing responses)

Also provides two dataclass specifications:
 - Signal              (state signal protocol definition)
 - Response            (response protocol definition)

Combining redis pubsub features with state signal + response protocols, 
these additions make state signal publishing, subscribing, receiving, 
and responding incredibly easy to integrate into any code.
