# State/Event Signal Module
A python package for handling state/event signals

Adds two new, simple-to-use objects:
 - SignalExporter      (for publishing state signals and handling subscribers + responses)
 - SignalResponder     (for receiving state signals, locking onto publishers, and publishing responses)

Also provides two dataclass specifications:
 - Signal              (state signal protocol payload definition)
 - Response            (response protocol payload definition)

Combining redis pubsub features with state signal + response protocols, 
these additions make state signal publishing, subscribing, receiving, 
and responding incredibly easy to integrate into any python code.

See full documentation [here](https://distributed-system-analysis.github.io/state-signals/)

# Installation
The state-signals PyPI package is available [here](https://pypi.org/project/state-signals)

To install, run `pip install state-signals`

# REQUIREMENTS
The use of this module requires the existence of an accessible redis server.
 - Redis can easily be installed with a `yum install redis` (or replace yum with package manager of choice).

A redis server can be started with the `redis-server` command.
 - The default port is 6379 (also default for state-signals), but can be changed with `--port (port)`
 - A config file can also be used for greater control/detail `redis-server \path\to\config`
 - Example/default config available (here)[https://download.redis.io/redis-stable/redis.conf]

See https://redis.io/ for more details and usage

# PROTOCOL / BEHAVIORS

