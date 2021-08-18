# State/Event Signal Module
A python package for handling state/event signals

Adds two new, simple-to-use objects:
 - SignalExporter      (for publishing state signals and handling subscribers + responses)
 - SignalResponder     (for receiving state signals, locking onto publishers, and publishing responses)

Also provides two dataclass specifications:
 - Signal              (state signal protocol definition)
 - Response            (response protocol definition)

Combining redis pubsub features with state signal + response protocols, 
these additions make state signal publishing, subscribing, receiving, 
and responding incredibly easy to integrate into any python code.

See full documentation [here](https://distributed-system-analysis.github.io/state-signals/)

# Installation
The state-signals PyPi package is available [here](https://pypi.org/project/state-signals)

To install, run `pip install state-signals`
