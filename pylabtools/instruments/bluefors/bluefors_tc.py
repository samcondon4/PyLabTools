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

import json
import logging
import math
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from pymeasure.adapters import Adapter
from pymeasure.instruments import Channel, Instrument
from pymeasure.instruments.validators import strict_range

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

#: Value path of sensor ``{channel}`` in the heater mapping of older control software versions.
#: Newer BlueFTC versions use "mapper.temperature_control.sensors.t{channel}".
DEFAULT_SENSOR_PATH = "mapper.heater_mappings_bftc.device.c{channel}"

#: Device path of heater output ``{heater}`` (an int), at the temperature controller's driver level
#: as in current BlueFTC. This addresses the physical heater output by number, rather than a named
#: entry of the control software's heater mapping.
DEFAULT_HEATER_PATH = "driver.bftc.data.heaters.heater_{heater}"

#: ``latest_valid_value`` statuses accepted as a valid reading (as in BlueFTC).
VALID_STATUSES = ("SYNCHRONIZED", "CHANGED", "INDEPENDENT")
#: Statuses meaning a written value failed; anything else (e.g. "QUEUED") is waited on.
FAILED_STATUSES = ("INVALID", "DISCONNECTED", "ERROR")


class BlueforsAPIError(RuntimeError):
    """ Raised when a value cannot be read or written, or the controller reports it as not valid. """


class BlueforsHTTPAdapter(Adapter):
    """ PyMeasure adapter for the Bluefors REST interface.

    PyMeasure queries are ``write(command)`` followed by ``read()``. Here a query *command* is a value
    path such as ``"mapper.heater_mappings_bftc.device.c6.temperature"``; ``read()`` performs the
    HTTP GET for the last path written by the same thread and returns the value as a string.

    A *set* command has the form ``"<value path>=<value>"``. Writing it sets the value, applies it
    to the device, and waits until the controller reports the new value as valid.

    :param host: IP address or host name of the computer running the Bluefors control software.
    :param key: API key (read permission; write permission to change settings).
    :param port: HTTPS port of the REST interface.
    :param scheme: ``"https"`` (default) or ``"http"``.
    :param verify: Verify the server's TLS certificate. The Bluefors server uses a self-signed
        certificate, so this is False by default; the connection is still encrypted.
    :param timeout: Seconds to wait for each HTTP reply before raising.
    :param apply_timeout: Seconds to wait for the controller to confirm a written value.
    :param poll_interval: Seconds between confirmation checks.
    """

    def __init__(self, host, key, port=49098, scheme="https", verify=False, timeout=10,
                 apply_timeout=10, poll_interval=0.25, log=None, **kwargs):
        super().__init__(log=log, **kwargs)
        if not key:
            raise ValueError("An API key from the Bluefors control software is required.")
        self.base_url = f"{scheme}://{host}:{port}"
        self.timeout = timeout
        self.apply_timeout = apply_timeout
        self.poll_interval = poll_interval
        self._key = key
        self._context = None
        if scheme == "https" and not verify:
            self._context = ssl.create_default_context()
            self._context.check_hostname = False
            self._context.verify_mode = ssl.CERT_NONE
        # - one pending command per thread, so concurrent write/read pairs cannot be mixed up - #
        self._pending = threading.local()

    # - pymeasure adapter interface ------------------------------------------------------------ #
    def _write(self, command, **kwargs):
        command = command.strip()
        if "=" in command:
            path, _, raw = command.partition("=")
            self.set_value(path.strip(), _parse_value(raw.strip()))
        else:
            self._pending.command = command

    def _read(self, **kwargs):
        command = getattr(self._pending, "command", None)
        if command is None:
            raise BlueforsAPIError("read() called without a preceding write() of a value path.")
        self._pending.command = None
        return str(self.get_value(command))

    # - REST operations ------------------------------------------------------------------------ #
    def get_value(self, path):
        """ Return the latest valid value at ``path`` (e.g. ``"mapper.....c6.temperature"``).

        :raises BlueforsAPIError: On connection errors, HTTP errors, an unexpected reply, or a
            value whose status is not one of :data:`VALID_STATUSES`.
        """
        value, status = self._latest(path)
        if status not in VALID_STATUSES:
            raise BlueforsAPIError(f"{path!r} is not valid: status {status!r}.")
        return value

    def set_value(self, path, value):
        """ Set ``path`` to ``value``, apply it to the device, and wait for confirmation.

        The device is everything before the last ``.`` of ``path``.

        :raises BlueforsAPIError: If a request fails, the controller reports the value as failed,
            or the new value is not confirmed within ``apply_timeout`` seconds.
        """
        device = path.rsplit(".", 1)[0]
        self._post({"data": {path: {"content": {"value": value}}}}, f"setting {path!r}")
        self._post({"data": {f"{device}.write": {"content": {"call": 1}}}}, f"applying {device!r}")

        deadline = time.monotonic() + self.apply_timeout
        while True:
            current, status = self._latest(path)
            if status in VALID_STATUSES and _same(current, value):
                return current
            if status in FAILED_STATUSES:
                raise BlueforsAPIError(f"Controller rejected {path!r} = {value!r}: status {status!r}.")
            if time.monotonic() >= deadline:
                raise BlueforsAPIError(
                    f"{path!r} = {value!r} not confirmed within {self.apply_timeout} s "
                    f"(controller reports {current!r} with status {status!r}).")
            time.sleep(self.poll_interval)

    def _latest(self, path):
        reply = self._request(f"/values/{path.replace('.', '/')}/", None, f"reading {path!r}")
        try:
            latest = reply["data"][path]["content"]["latest_valid_value"]
            return latest["value"], latest["status"]
        except (KeyError, TypeError) as exc:
            raise BlueforsAPIError(f"Unexpected reply for {path!r}: missing {exc}. Check the value path "
                                   f"(sensor_path / heater_path) for your control software version.") from None

    def _post(self, body, action):
        reply = self._request("/values/", body, action)
        if isinstance(reply, dict) and "error" in reply:
            error = reply["error"]
            detail = error.get("description") or error.get("name") if isinstance(error, dict) else error
            raise BlueforsAPIError(f"Controller returned an error {action}: {detail}.")
        return reply

    def _request(self, endpoint, body, action):
        url = f"{self.base_url}{endpoint}?" + urllib.parse.urlencode({"prettyprint": 1, "key": self._key})
        data, headers = None, {}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=data, headers=headers,
                                         method="GET" if body is None else "POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout, context=self._context) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            exc.close()  # - an HTTPError holds the open response; close it so the socket is not leaked - #
            # - never put the URL in messages: it contains the API key - #
            raise BlueforsAPIError(f"HTTP {exc.code} {exc.reason} {action}.") from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            reason = getattr(exc, "reason", exc)
            raise BlueforsAPIError(f"Cannot reach {self.base_url} {action}: {reason}.") from None
        except json.JSONDecodeError as exc:
            raise BlueforsAPIError(f"Reply {action} is not JSON: {exc}.") from None

    def __repr__(self):
        return f"<BlueforsHTTPAdapter({self.base_url})>"


def _parse_value(raw):
    """ Turn the value part of a set command back into a number when possible. """
    try:
        return int(raw) if raw.lstrip("+-").isdigit() else float(raw)
    except ValueError:
        return raw


def _same(current, requested):
    """ True if the value reported by the controller matches the requested value. """
    try:
        return math.isclose(float(current), float(requested), rel_tol=1e-6, abs_tol=1e-12)
    except (TypeError, ValueError):
        return str(current) == str(requested)


class BlueforsSensor(Channel):
    """ One temperature sensor channel of the Bluefors temperature controller. """

    temperature = Channel.measurement(
        "{sensor}.temperature",
        """Measure the sensor temperature in kelvin (float).""",
        get_process=float,
    )

    def insert_id(self, command):
        sensor = self.parent.sensor_path.format(channel=self.id)
        return command.format(sensor=sensor)


class BlueforsHeater(Channel):
    """ One heater of the Bluefors temperature controller. """

    setpoint = Channel.control(
        "{heater}.setpoint", "{heater}.setpoint=%r",
        """Control the PID setpoint in kelvin (float).

        Setting it writes the value, applies it to the temperature controller and waits until the
        controller confirms it. Values outside ``setpoint_values`` (by default 0 K to the
        instrument's ``max_setpoint``) raise ValueError before anything is sent.""",
        validator=strict_range,
        values=(0, 0.5),
        dynamic=True,
        get_process=float,
        set_process=float,
    )

    def insert_id(self, command):
        heater = self.parent.heater_path.format(heater=self.id)
        return command.format(heater=heater)


class BlueforsTC(Instrument):
    """ Represents a Bluefors temperature controller, accessed through the REST interface of the
    Bluefors control software (the interface used by the BlueFTC package).

    Reads use ``GET https://<host>:<port>/values/<value path>/?key=<API key>``; writes ``POST`` the
    new value and then call the device's ``write`` method to apply it, and wait until the controller
    confirms the value (see :class:`BlueforsHTTPAdapter`).

    .. code-block:: python

        tc = BlueforsTC("192.168.0.10", key="<API key>", heaters=(1,))
        tc.ch_6.temperature             # sensor temperature in kelvin
        tc.temperature(6)               # same, channel chosen at run time
        tc.heater_1.setpoint            # PID setpoint of heater output 1, in kelvin
        tc.heater_1.setpoint = 0.050    # write, apply, and wait for confirmation

    The API key is created in the Bluefors control software; it needs write permission to change
    setpoints. Changing a setpoint does not switch the heater on or enable PID mode.

    :param adapter: Host name or IP address of the computer running the control software, or an
        adapter instance (e.g. a :class:`BlueforsHTTPAdapter`, or a protocol adapter in tests).
    :param name: Instrument name.
    :param key: API key, required when ``adapter`` is a host name.
    :param port: Port of the REST interface (49098 in BlueFTC).
    :param sensor_path: Value path of a sensor, with ``{channel}`` for the channel number.
    :param heater_path: Device path of a heater output, with ``{heater}`` for its number.
    :param heaters: Heater output numbers to create as ``heater_<n>`` attributes, e.g. ``(1, 2)``.
        Other outputs can be reached with :meth:`heater`.
    :param max_setpoint: Upper limit in kelvin for heater setpoints, as a guard against unit
        mistakes. Change per heater with ``tc.heater_1.setpoint_values = (0, 1.0)``.
    :param scheme: ``"https"`` (default) or ``"http"``.
    :param verify: Verify the TLS certificate (False: the server's certificate is self-signed).
    :param timeout: Seconds to wait for each reply.
    :param apply_timeout: Seconds to wait for the controller to confirm a new setpoint.
    :param kwargs: Further :class:`BlueforsHTTPAdapter` arguments when ``adapter`` is a host name.

    Sensors are available as ``ch_1`` ... ``ch_12`` and in the ``channels`` dict; heaters as
    ``heater_<id>`` and in the ``heaters`` dict::

        tc.ch_6.temperature
        tc.heater_1.setpoint = 0.1
    """

    channels = Instrument.MultiChannelCreator(BlueforsSensor, list(range(1, 13)))

    def __init__(self, adapter, name="Bluefors temperature controller", key=None, port=49098,
                 sensor_path=DEFAULT_SENSOR_PATH, heater_path=DEFAULT_HEATER_PATH, heaters=(),
                 max_setpoint=0.5, scheme="https", verify=False, timeout=10, apply_timeout=10,
                 **kwargs):
        self.sensor_path = sensor_path
        self.heater_path = heater_path
        self.max_setpoint = max_setpoint
        if isinstance(adapter, str):
            adapter = BlueforsHTTPAdapter(adapter, key, port=port, scheme=scheme, verify=verify,
                                          timeout=timeout, apply_timeout=apply_timeout, **kwargs)
        super().__init__(adapter, name, includeSCPI=False)
        self.heaters = {}
        for heater_id in heaters:
            self.heater(heater_id)

    def temperature(self, channel):
        """ Return the temperature in kelvin of sensor ``channel`` (an int). """
        try:
            return self.channels[channel].temperature
        except KeyError:
            raise ValueError(f"No sensor channel {channel}; channels are {sorted(self.channels)}.") from None

    def heater(self, heater_id):
        """ Return the :class:`BlueforsHeater` for heater output ``heater_id`` (an int), creating it
        on first use. """
        if isinstance(heater_id, bool) or not isinstance(heater_id, int) or heater_id < 1:
            raise TypeError(f"Heater ids are output numbers (1, 2, ...), got {heater_id!r}.")
        if heater_id not in self.heaters:
            heater = self.add_child(BlueforsHeater, heater_id, collection="heaters", prefix="heater_")
            heater.setpoint_values = (0, self.max_setpoint)
        return self.heaters[heater_id]
