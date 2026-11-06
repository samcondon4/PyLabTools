import os
import threading
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pylabtools import Consumer  # noqa: E402  (QT_QPA_PLATFORM must be set first)


class ListConsumer(Consumer):
    """ Test consumer that stores every record and hook call. """

    def __init__(self, delay=0.0, fail_on=None, critical=True, **kwargs):
        super().__init__(**kwargs)
        self.records = []
        self.group_ends = []
        self.events = []
        self.threads = set()
        self.delay = delay
        self.fail_on = fail_on
        self.critical = critical

    def on_start(self):
        self.events.append("start")
        self.threads.add(threading.get_ident())

    def handle(self, record):
        self.threads.add(threading.get_ident())
        if self.fail_on is not None and len(self.records) == self.fail_on:
            raise RuntimeError("consumer failure")
        if self.delay:
            time.sleep(self.delay)
        self.records.append(record)

    def on_group_end(self, group):
        self.group_ends.append((group, len(self.records)))

    def on_stop(self):
        self.events.append("stop")
        self.threads.add(threading.get_ident())


@pytest.fixture
def consumer():
    c = ListConsumer()
    with c:
        yield c


# - device tests (as in PyMeasure): pytest --device-address=<address> runs *_with_device.py tests - #
def pytest_addoption(parser):
    parser.addoption("--device-address", action="store", default=None,
                     help="Address of the device for tests that require a connected device")


@pytest.fixture(scope="session")
def connected_device_address(pytestconfig):
    address = pytestconfig.getoption("device_address")
    if address is None:
        pytest.skip("Only works with connected device.")
    return address
