#
# This file is part of the PyMeasure package.
#
# Copyright (c) 2013-2026 PyMeasure Developers
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#

""" Tests of BlueforsHTTPAdapter against a local mock of the Bluefors control software REST API. """
import json
import logging
import shutil
import ssl
import subprocess
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from pylabtools.instruments.bluefors.bluefors_tc import (DEFAULT_HEATER_PATH, DEFAULT_SENSOR_PATH,
                                                         BlueforsAPIError, BlueforsHTTPAdapter,
                                                         BlueforsTC)

KEY = "secret-key-123"
TEMPS = {1: 50.12, 2: 3.98, 5: 0.0123, 6: 0.00987}
STATUS = {6: "CHANGED", 2: "INVALID"}


class MockBluefors(BaseHTTPRequestHandler):
    """ Minimal stand-in for the control software: sensors c1..c6 and heaters 1..4. """

    sensor_path = DEFAULT_SENSOR_PATH
    heater_path = DEFAULT_HEATER_PATH
    requests = []
    posts = []
    heaters = {}
    apply_delay = 0.3

    @classmethod
    def reset(cls):
        cls.requests.clear()
        cls.posts.clear()
        cls.sensor_path, cls.heater_path = DEFAULT_SENSOR_PATH, DEFAULT_HEATER_PATH
        base = {"pending": None, "status": "SYNCHRONIZED", "ready_at": 0}
        cls.heaters = {
            1: {**base, "applied": 0.010},
            2: {**base, "applied": 0.700},
            3: {**base, "applied": 0.0, "rejects": True},
            4: {**base, "applied": 0.0, "never": True},
        }

    def log_message(self, *args):
        pass

    def _send_json(self, body):
        payload = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _authorized(self):
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        if query.get("key") != [KEY]:
            self.send_error(403, "Forbidden")
            return False
        return True

    def _heater_for(self, device):
        for hid in self.heaters:
            if device == self.heater_path.format(heater=hid):
                return hid
        return None

    def do_GET(self):
        MockBluefors.requests.append(self.path)
        if not self._authorized():
            return
        parts = urllib.parse.urlparse(self.path).path.strip("/").split("/")
        path = ".".join(parts[1:])
        if path.startswith("slow"):
            time.sleep(2)
        device, _, target = path.rpartition(".")
        hid = self._heater_for(device)
        if hid is not None and target == "setpoint":
            heater = self.heaters[hid]
            if heater["status"] == "QUEUED" and heater["pending"] is None and time.monotonic() >= heater["ready_at"]:
                heater["status"] = "SYNCHRONIZED"
            value, status = heater["applied"], heater["status"]
        else:
            matches = [ch for ch in TEMPS if path == self.sensor_path.format(channel=ch) + ".temperature"]
            if not matches:
                self._send_json({"error": {"name": "not found"}})
                return
            value, status = TEMPS[matches[0]], STATUS.get(matches[0], "SYNCHRONIZED")
        self._send_json({"data": {path: {"content": {"latest_valid_value": {"value": value, "status": status}}}}})

    def do_POST(self):
        if not self._authorized():
            return
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        MockBluefors.posts.append(body)
        (path, entry), = body["data"].items()
        device, target = path.rsplit(".", 1)
        hid = self._heater_for(device)
        if hid is None:
            self._send_json({"error": {"name": "UNKNOWN", "description": f"no device {device}"}})
            return
        heater = self.heaters[hid]
        if target == "setpoint":
            heater["pending"], heater["status"] = entry["content"]["value"], "QUEUED"
        elif target == "write" and entry["content"] == {"call": 1}:
            if heater.get("rejects"):
                heater["status"] = "INVALID"
            elif not heater.get("never") and heater["pending"] is not None:
                heater["applied"], heater["pending"] = heater["pending"], None
                heater["ready_at"] = time.monotonic() + self.apply_delay
        self._send_json({"data": {}})


def _serve(ssl_context=None):
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), MockBluefors)
    httpd.daemon_threads = True
    if ssl_context is not None:
        httpd.socket = ssl_context.wrap_socket(httpd.socket, server_side=True)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


@pytest.fixture(scope="module")
def server():
    httpd = _serve()
    yield httpd.server_address[1]
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture
def tc(server):
    MockBluefors.reset()
    return BlueforsTC("127.0.0.1", key=KEY, port=server, scheme="http", timeout=1, apply_timeout=3,
                      heaters=(1,))


# - reading -------------------------------------------------------------------------------------- #
def test_temperatures(tc):
    assert tc.ch_1.temperature == 50.12
    assert tc.temperature(5) == 0.0123
    assert tc.ch_6.temperature == 0.00987  # - status CHANGED is accepted - #


def test_url_format(tc):
    tc.ch_5.temperature
    path, query = MockBluefors.requests[-1].split("?")
    assert path == "/values/mapper/heater_mappings_bftc/device/c5/temperature/"
    assert urllib.parse.parse_qs(query) == {"prettyprint": ["1"], "key": [KEY]}


def test_invalid_status_raises(tc):
    with pytest.raises(BlueforsAPIError, match="status 'INVALID'"):
        tc.ch_2.temperature


def test_unknown_path_raises_with_hint(tc):
    with pytest.raises(BlueforsAPIError, match="Check the value path"):
        tc.ch_9.temperature


def test_wrong_key_raises_without_leaking_it(server):
    bad = BlueforsTC("127.0.0.1", key="wrong-key", port=server, scheme="http", heaters=(1,))
    for action in (lambda: bad.ch_1.temperature, lambda: setattr(bad.heater_1, "setpoint", 0.1)):
        with pytest.raises(BlueforsAPIError, match="HTTP 403") as info:
            action()
        assert "wrong-key" not in str(info.value)


def test_unreachable_host_raises():
    dead = BlueforsTC("127.0.0.1", key=KEY, port=1, scheme="http", timeout=1)
    with pytest.raises(BlueforsAPIError, match="Cannot reach"):
        dead.ch_1.temperature


def test_timeout(server):
    slow = BlueforsTC("127.0.0.1", key=KEY, port=server, scheme="http", timeout=0.3,
                      sensor_path="slow.c{channel}")
    t = time.monotonic()
    with pytest.raises(BlueforsAPIError, match="Cannot reach"):
        slow.ch_1.temperature
    assert time.monotonic() - t < 1.5


def test_key_is_required_for_a_host():
    with pytest.raises(ValueError, match="API key"):
        BlueforsTC("127.0.0.1")


def test_key_not_logged(tc, caplog):
    with caplog.at_level(logging.DEBUG):
        tc.ch_1.temperature
        tc.heater_1.setpoint = 0.02
    assert KEY not in caplog.text


def test_concurrent_reads_are_not_mixed_up(tc):
    errors = []

    def read(ch):
        try:
            for _ in range(20):
                assert tc.temperature(ch) == TEMPS[ch]
        except Exception as exc:  # pragma: no cover - only on failure
            errors.append(exc)

    threads = [threading.Thread(target=read, args=(ch,)) for ch in (1, 5, 6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors


# - writing ------------------------------------------------------------------------------------ #
def test_set_posts_value_then_apply_and_waits_for_confirmation(tc):
    t = time.monotonic()
    tc.heater_1.setpoint = 0.050
    assert time.monotonic() - t >= MockBluefors.apply_delay
    assert MockBluefors.posts == [
        {"data": {"driver.bftc.data.heaters.heater_1.setpoint": {"content": {"value": 0.05}}}},
        {"data": {"driver.bftc.data.heaters.heater_1.write": {"content": {"call": 1}}}},
    ]
    assert tc.heater_1.setpoint == 0.05
    assert MockBluefors.heaters[2]["applied"] == 0.700  # - other outputs untouched - #


def test_rejected_value_raises(tc):
    with pytest.raises(BlueforsAPIError, match="rejected .* status 'INVALID'"):
        tc.heater(3).setpoint = 0.1


def test_unconfirmed_value_times_out(server):
    MockBluefors.reset()
    tc = BlueforsTC("127.0.0.1", key=KEY, port=server, scheme="http", heaters=(4,), apply_timeout=0.6)
    t = time.monotonic()
    with pytest.raises(BlueforsAPIError, match="not confirmed within 0.6 s .*status 'QUEUED'"):
        tc.heater_4.setpoint = 0.1
    assert time.monotonic() - t < 2


def test_error_reply_to_post_raises(tc):
    with pytest.raises(BlueforsAPIError, match="Controller returned an error setting .*no device"):
        tc.heater(9).setpoint = 0.1


def test_adapter_read_without_write():
    adapter = BlueforsHTTPAdapter("127.0.0.1", key=KEY)
    with pytest.raises(BlueforsAPIError, match="without a preceding write"):
        adapter.read()


# - HTTPS with a self-signed certificate, as served by the control software --------------------- #
@pytest.fixture(scope="module")
def https_server(tmp_path_factory):
    openssl = shutil.which("openssl")
    if openssl is None:
        pytest.skip("openssl is needed to create a self-signed test certificate")
    d = tmp_path_factory.mktemp("cert")
    subprocess.run([openssl, "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                    "-subj", "/CN=bluefors-mock", "-keyout", str(d / "key.pem"), "-out", str(d / "cert.pem")],
                   check=True, capture_output=True)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(d / "cert.pem", d / "key.pem")
    httpd = _serve(context)
    yield httpd.server_address[1]
    httpd.shutdown()
    httpd.server_close()


def test_https_with_self_signed_certificate(https_server):
    MockBluefors.reset()
    tc = BlueforsTC("127.0.0.1", key=KEY, port=https_server, timeout=2, heaters=(1,))
    assert tc.ch_5.temperature == 0.0123
    tc.heater_1.setpoint = 0.04
    assert tc.heater_1.setpoint == 0.04


def test_https_certificate_verification_can_be_enabled(https_server):
    tc = BlueforsTC("127.0.0.1", key=KEY, port=https_server, timeout=2, verify=True)
    with pytest.raises(BlueforsAPIError, match="Cannot reach"):
        tc.ch_5.temperature
