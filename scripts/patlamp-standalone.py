#!/usr/bin/env python3
"""Standalone HTTP GPIO controller for Phone Call Light.

This variant is intentionally dependency-free for Raspberry Pi setups that do
not have Internet access after becoming a standalone Wi-Fi access point.

It uses only Python's standard library and Raspberry Pi OS's `pinctrl` command.
Default endpoints:

    GET /              health check
    GET /call/start    turn lamp on
    GET /call/end      turn lamp off
    GET /on            manual lamp on
    GET /off           manual lamp off
    GET /status        JSON status

Default GPIO is BCM17. Most inexpensive relay modules are active-low, so the
script defaults to ACTIVE_LOW=True.
"""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse
import datetime as _datetime
import json
import os
import subprocess
from typing import Any

GPIO = os.environ.get("PATLAMP_GPIO", "17")
ACTIVE_LOW = os.environ.get("PATLAMP_ACTIVE_LOW", "1").lower() not in {
    "0",
    "false",
    "no",
    "off",
}
HOST = os.environ.get("PATLAMP_HOST", "0.0.0.0")
PORT = int(os.environ.get("PATLAMP_PORT", "80"))

state: dict[str, Any] = {
    "lamp": "off",
    "last_event": None,
    "last_time": None,
    "gpio": GPIO,
    "active_low": ACTIVE_LOW,
}


def gpio_set(on: bool) -> None:
    """Set GPIO output using pinctrl.

    For active-low relay modules, ON means driving the GPIO low.
    """

    if ACTIVE_LOW:
        level = "dl" if on else "dh"
    else:
        level = "dh" if on else "dl"

    subprocess.run(["pinctrl", "set", GPIO, "op", level], check=True)


def set_lamp(on: bool, event: str) -> None:
    gpio_set(on)
    state["lamp"] = "on" if on else "off"
    state["last_event"] = event
    state["last_time"] = _datetime.datetime.now().isoformat(timespec="seconds")


class Handler(BaseHTTPRequestHandler):
    def send_text(self, text: str, code: int = 200) -> None:
        data = text.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, obj: Any, code: int = 200) -> None:
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        path = urlparse(self.path).path

        try:
            if path == "/":
                self.send_text("Patlamp controller OK\n")
            elif path == "/call/start":
                set_lamp(True, "call/start")
                self.send_text("CALL START: LAMP ON\n")
            elif path == "/call/end":
                set_lamp(False, "call/end")
                self.send_text("CALL END: LAMP OFF\n")
            elif path == "/on":
                set_lamp(True, "manual/on")
                self.send_text("ON\n")
            elif path == "/off":
                set_lamp(False, "manual/off")
                self.send_text("OFF\n")
            elif path == "/status":
                self.send_json(state)
            else:
                self.send_text("Not found\n", 404)
        except Exception as exc:  # Keep this visible for field debugging.
            self.send_text(f"ERROR: {exc}\n", 500)

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"{self.address_string()} - {fmt % args}")


if __name__ == "__main__":
    set_lamp(False, "startup/off")
    server = HTTPServer((HOST, PORT), Handler)
    print(f"Patlamp controller listening on {HOST}:{PORT}")
    server.serve_forever()
