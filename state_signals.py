"""
State/Event Signal Module

Adds two new, simple-to-use objects:

   - SignalExporter      (for publishing state signals and handling subscribers + responses)  
   - SignalResponder     (for receiving state signals, locking onto publishers, and publishing responses)

Also provides two dataclass specifications:

   - Signal              (state signal protocol payload definition)  
   - Response            (response protocol payload definition)

Combining redis pubsub features with state signal + response protocols, 
these additions make state signal publishing, subscribing, receiving, 
and responding incredibly easy to integrate into any code.
"""


from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Dict, Iterator, List, Optional, Tuple
import redis
import platform
import json
import time
import uuid
import logging


def _create_logger(
    class_name: str, process_name: str, log_level: str
) -> logging.Logger:
    """
    Creates and returns logging.Logger object for detailed logging.
    Used by SignalExporter and SignalResponder.
    """
    logger = (
        logging.getLogger("state-signals").getChild(class_name).getChild(process_name)
    )
    try:
        logger.setLevel(log_level)
        ch = logging.StreamHandler()
        ch.setLevel(log_level)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        ch.setFormatter(formatter)
        logger.addHandler(ch)
    except ValueError:
        raise ValueError("Legal log levels: [DEBUG, INFO, WARNING, ERROR, CRITICAL]")
    return logger


class ResultCodes(IntEnum):
    """
    All potential result codes when publishing a signal. See the publish_signal
    method under SignalExporter for more details.
    """

    ALL_SUBS_SUCCESS = 0
    SUB_FAILED = 1
    MISSING_RESPONSE = 2


@dataclass
class Signal:
    """
    Standard event signal protocol payload. All required fields, defaults, 
    and type restrictions are defined in this dataclass. Also includes a 
    method for converting object data to json string.

    Fields:

        - publisher_id: A unique id generated by the SignalExporter for identification  
        - process_name: The name of the process that the state signals are describing  
        - event: The current state of the process  
        - runner_host: The host that the process is currently being run on  
        - sample_no: The current sample number (if applicable, default -1)  
        - tag: Any user-supplied string tag for the signal (default 'No tag specified')  
        - metadata: Dictionary containing any additional necessary data (optional)
    """

    publisher_id: str
    process_name: str
    event: str
    runner_host: str
    sample_no: int = -1
    tag: str = "No tag specified"
    metadata: Optional[Dict] = None

    def __post_init__(self) -> None:
        """
        Checks all field types.
        """
        for (name, field_type) in self.__annotations__.items():
            if name == "metadata":
                field_type = field_type.__args__
            if not isinstance(self.__dict__[name], field_type):
                raise TypeError(
                    f"The field {name} should be type {field_type}, not {type(self.__dict__[name])}"
                )

    def to_json_str(self) -> Dict[str, Any]:
        """
        Converts object data into json string.
        """
        result: Dict[str, Any] = {
            k: v
            for k, v in self.__dict__.items()
            if not (k.startswith("__") and k.endswith("__"))
            and not (k == "metadata" and v == None)
        }
        return json.dumps(result)


@dataclass
class Response:
    """
    Standard signal response protocol payload. All required fields, defaults, 
    and type restrictions are defined in this dataclass. Also includes a 
    method for converting object data to json string.

    Fields:

        - responder_id: A unique id generated by the SignalResponder for identification  
        - publisher_id: The id of the publisher that is being responded to  
        - event: The published state of the signal-publishing process  
        - ras: Response Action Success code  
            - Whether or not the responding process successfully processed/acted upon the signal  
            - 1 = successful, 0 (or other) = unsuccessful  
            - Not needed when not subscribed or responding to initialization  
    """

    responder_id: str
    publisher_id: str
    event: str
    ras: Optional[int]

    def __post_init__(self) -> None:
        """
        Checks all field types.
        """
        for (name, field_type) in self.__annotations__.items():
            if name == "ras":
                field_type = field_type.__args__
            if not isinstance(self.__dict__[name], field_type):
                raise TypeError(
                    f"The field {name} should be type {field_type}, not {type(self.__dict__[name])}"
                )

    def to_json_str(self) -> Dict[str, Any]:
        """
        Converts object data into json string.
        """
        result: Dict[str, Any] = {
            k: v
            for k, v in self.__dict__.items()
            if not (k.startswith("__") and k.endswith("__"))
            and not (k == "ras" and v == None)
        }
        return json.dumps(result)


class SignalExporter:
    """
    A signal management object for tools that wish to publish event/state signals.
    Also handles subscriber recording and response reading/awaiting. Uses the standard
    signal protocol for all published messages. Easy-to-use interface for publishing
    legal signals and handling responders.
    """

    def __init__(
        self,
        process_name: str,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        runner_host: str = platform.node(),
        log_level: str = "INFO",
    ) -> None:
        """
        init: Sets exporter object fields and generates unique publisher_id.
        Allows for specification of redis host/port. Also allows runner
        hostname to be inputted manually (otherwise will default to 
        platform.node() value)
        """
        self.logger = _create_logger("SignalExporter", process_name, log_level)
        self.subs = []
        self.proc_name = process_name
        self.runner_host = runner_host
        self.pub_id = process_name + "-" + str(uuid.uuid4())
        self.redis = redis.Redis(host=redis_host, port=redis_port, db=0)
        self.init_listener = None
        self.legal_events = None

    def _sig_builder(
        self, event: str, sample: int = -1, tag: str = None, metadata: Dict = None
    ) -> Signal:
        """
        Build a signal data object based on exporter object fields,
        as well as user-inputted fields. Returns the signal object.
        """
        config = {
            "publisher_id": self.pub_id,
            "process_name": self.proc_name,
            "event": event,
            "runner_host": self.runner_host,
        }
        if sample:
            config["sample_no"] = sample
        if tag:
            config["tag"] = tag
        if metadata:
            config["metadata"] = metadata
        sig = Signal(**config)
        return sig

    def _get_data_dict(self, response: Dict) -> Dict:
        """
        Returns response signal payload if a properly-formed
        response is received. Otherwise return None.
        """
        if not "data" in response:
            self.logger.debug(f"No data in this response message: {response}")
            return None
        try:
            data = json.loads(response["data"])
        except ValueError:
            return None
        if (
            "responder_id" not in data
            or "publisher_id" not in data
            or "event" not in data
        ):
            self.logger.debug(f"Malformed response data found: {response}")
            return None
        return data

    def _fetch_responders(self) -> None:
        """
        Start initialization response listener. Add respoder_ids from proper
        responses to the subscriber list.
        """
        subscriber = self.redis.pubsub(ignore_subscribe_messages=True)

        def _init_handler(item) -> None:
            data = self._get_data_dict(item)
            if (
                data
                and data["event"] == "initialization"
                and data["publisher_id"] == self.pub_id
            ):
                self.subs.append(data["responder_id"])

        subscriber.subscribe(**{"event-signal-response": _init_handler})
        self.init_listener = subscriber.run_in_thread()

    def _check_subs(self, event: str) -> Tuple[Any, List[int]]:
        """
        Listen for responses from all registered subscribers. Return
        listener, as well as value based on responders' RAS codes.
        """
        if not self.subs:
            return None, [0]

        to_check = set(self.subs)
        subscriber = self.redis.pubsub(ignore_subscribe_messages=True)
        result_code_holder = [ResultCodes.ALL_SUBS_SUCCESS]

        def _sub_handler(item: Dict) -> None:
            data = self._get_data_dict(item)
            if data and data["publisher_id"] == self.pub_id and data["event"] == event:
                if "ras" in data:
                    if data["responder_id"] not in to_check:
                        self.logger.warning(
                            f"Got a response from tool '{data['responder_id']}' but it's not on the known subscribers list (or already responded for '{event}'). RAS: {data['ras']}"
                        )
                    else:
                        to_check.remove(data["responder_id"])
                        if data["ras"] != 1:
                            self.logger.warning(
                                f"Tool '{data['responder_id']}' returned bad response for event '{event}', ras: {data['ras']}"
                            )
                            result_code_holder[0] = ResultCodes.SUB_FAILED
            if not to_check:
                listener.stop()

        subscriber.subscribe(**{"event-signal-response": _sub_handler})
        listener = subscriber.run_in_thread()
        return listener, result_code_holder

    def _valid_str_list(self, names: List[str]) -> bool:
        """
        Return true if input is a non-empty list of strings. Otherwise
        return false.
        """
        return (
            bool(names)
            and isinstance(names, list)
            and all(isinstance(event, str) for event in names)
        )

    def publish_signal(
        self,
        event: str,
        sample: int = -1,
        tag: str = None,
        metadata: Dict = None,
        timeout: int = 20,
    ) -> int:
        """
        Publish a legal event signal. Includes additional options to specify sample_no,
        a tag, and any other additional metadata. Will then wait for responses from
        subscribed responders (if any). The method will give up once the timeout period
        is reached (default = 20s). Returns one of the below result codes based on
        signal publish/response success.

        Result Codes:

           - ALL_SUBS_SUCCESS = 0 = all subs responded well 
           - SUB_FAILED = 1 = one or more sub responded badly  
           - MISSING_RESPONE = 2 = not all subs responded
        """
        if not isinstance(timeout, int):
            raise TypeError("'timeout' arg must be an int value")

        skip_check = False
        if not self.init_listener or not self.init_listener.is_alive():
            self.logger.warning(
                "Exporter is not initialized, not accepting subscribers and no event checking"
            )
            skip_check = True

        if event == "initialization":
            raise ValueError(
                "Please use the 'initialize()' method for publishing 'initialization' signals"
            )

        if event == "shutdown":
            raise ValueError(
                "Please use the 'shutdown()' method for 'shutdown' signals"
            )

        if not skip_check and not event in self.legal_events:
            raise ValueError(
                f"Event {self.event} not one of legal events: {self.legal_events}"
            )

        sig = self._sig_builder(event=event, sample=sample, tag=tag, metadata=metadata)
        sub_check, result_code_holder = self._check_subs(event)

        self.redis.publish(channel="event-signal-pubsub", message=sig.to_json_str())
        self.logger.debug(f"Signal published for event {event}")

        counter = 0
        while sub_check and sub_check.is_alive():
            time.sleep(0.1)
            counter += 1
            if counter >= timeout * 10:
                self.logger.error(
                    f"Timeout after waiting {timeout} seconds for sub response"
                )
                sub_check.stop()
                return ResultCodes.MISSING_RESPONSE

        return result_code_holder[0]

    def initialize(
        self, legal_events: List[str], tag: str = None, expected_resps: List[str] = None
    ) -> None:
        """
        Publishes an initialization message. Starts a listener that reads responses
        to the initialization message and adds responders to the subscriber list.
        Sets list of legal event names for future signals, and also allows for optional
        input of expected responders (subscribers) as well as a tag.
        """
        if not self._valid_str_list(legal_events):
            raise TypeError("'legal_events' arg must be a list of string event names")

        if expected_resps:
            if not self._valid_str_list(expected_resps):
                raise TypeError(
                    "'expected_hosts' arg must be a list of string hostnames"
                )
            for resp in expected_resps:
                self.subs.append(resp)

        self.legal_events = legal_events
        sig = self._sig_builder(event="initialization", tag=tag)
        self._fetch_responders()
        self.redis.publish(channel="event-signal-pubsub", message=sig.to_json_str())
        self.logger.debug("Initialization successful!")

    def shutdown(self, tag: str = None) -> None:
        """
        Shuts down initialization response listener (stops accepting subscribers).
        Wipes the subscriber list and publishes a shutdown message.
        """
        sig = self._sig_builder(event="shutdown", tag=tag)
        self.init_listener.stop()
        self.subs = []
        self.redis.publish(channel="event-signal-pubsub", message=sig.to_json_str())
        self.logger.debug("Shutdown successful!")


class SignalResponder:
    """
    A signal management object for tools that wish to respond to event/state signals.
    Can be used both for listening for signals as well as responding to them. Also
    allows for locking onto specific tags/publisher_ids. Uses the standard signal
    response protocol for all published messages.
    """

    def __init__(
        self,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        responder_name: str = platform.node(),
        log_level="INFO",
    ) -> None:
        """
        init: Sets responder object fields and generates unique responder_id.
        Allows for specification of redis host/port.
        """
        self.logger = _create_logger("SignalResponder", responder_name, log_level)
        self.redis = redis.Redis(host=redis_host, port=redis_port, db=0)
        self.subscriber = self.redis.pubsub(ignore_subscribe_messages=True)
        self.subscriber.subscribe("event-signal-pubsub")
        self.responder_id = responder_name + "-" + str(uuid.uuid4()) + "-resp"
        self._locked_id = None
        self._locked_tag = None

    def _parse_signal(self, signal: Dict) -> Dict:
        """
        Validates received signal. Returns payload if valid.
        Also applies tag/publisher_id filters if added.
        """
        try:
            data = json.loads(signal["data"])
        except ValueError:
            self.logger.debug(f"Received non-signal redis message {signal}")
            return None
        # FIXME - Replace below line, maybe with dataclasses.fields()?
        check_set = set(
            [
                "publisher_id",
                "process_name",
                "event",
                "runner_host",
                "sample_no",
                "tag",
                "metadata",
            ]
        )
        if set(data.keys()) == check_set or check_set - set(data.keys()) == {
            "metadata"
        }:
            return data
        self.logger.warning(f"Received malformed signal payload {signal}")
        return None

    def _check_target(self, payload: Dict) -> bool:
        """
        Checks if given signal payload matches the locked publisher_id/tag
        (if any were provided). Returns True if the check passes or if no
        locks were provided, and False otherwise.
        """
        if (not self._locked_id or self._locked_id == payload["publisher_id"]) and (
            not self._locked_tag or self._locked_tag == payload["tag"]
        ):
            return True
        return False

    def listen(self) -> Iterator[Signal]:
        """
        Yield all legal published signals. If a specific tag/published_id
        was locked, only signals with those matching values will be yielded.
        """
        for item in self.subscriber.listen():
            data = self._parse_signal(item)
            if data and self._check_target(data):
                signal = Signal(**data)
                yield signal

    def respond(self, publisher_id: str, event: str, ras: int = None) -> None:
        """
        Publish a legal response to a certain publisher_id's event signal.
        Also allows for optional ras code to be added on (required for 
        publisher acknowledgement, but not for initialization response).
        """
        response = Response(self.responder_id, publisher_id, event, ras)
        self.redis.publish("event-signal-response", response.to_json_str())
        self.logger.debug(f"Published response for event {event} from {publisher_id}")

    def srespond(self, signal: Signal, ras: int = None) -> None:
        """
        Publish a legal response to a given signal. Serves as a wrapper
        for the respond method. Also allows for optional ras code to be
        added on (required for publisher acknowledgement, but not for 
        initialization response).
        """
        self.respond(signal.publisher_id, signal.event, ras)

    def lock_id(self, publisher_id: str) -> None:
        """
        Lock onto a specific publisher_id. Only receive signals from the
        chosen id.
        """
        if isinstance(publisher_id, str):
            self._locked_id == publisher_id
            self.logger.debug(f"Locked onto id: {publisher_id}")
        else:
            raise TypeError("Unsuccessful lock, 'publisher_id' must be type str")

    def lock_tag(self, tag: str) -> None:
        """
        Lock onto a specific tag. Only receive signals from the chosen tag.
        """
        if isinstance(tag, str):
            self._locked_tag == tag
            self.logger.debug(f"Locked onto tag: {tag}")
        else:
            raise TypeError("Unsuccessful lock, 'tag' must be type str")

    def unlock(self) -> None:
        """
        Releases both tag and publisher_id locks. Resume receiving signals
        from all publisher_ids and tags.
        """
        self.logger.debug(
            f"Released locks on tag '{self._locked_tag}' and published_id '{self._locked_id}'"
        )
        self._locked_id = None
        self._locked_tag = None
