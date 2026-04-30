#!/usr/bin/env python3
"""
Phone Call Light Server
Receives webhooks from Tasker (Android) and controls a patrol lamp via GPIO relay.

Endpoints:
  POST /call/start  — incoming call detected, turn lamp on
  POST /call/end    — call ended, turn lamp off
  GET  /status      — health check
"""

import atexit
import logging
from flask import Flask, request, jsonify

import config
import lamp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

app = Flask(__name__)


def _check_auth():
    token = request.headers.get("X-Auth-Token") or request.args.get("token")
    return token == config.AUTH_TOKEN


def _get_caller_from_request() -> str:
    if not request.is_json:
        return "unknown"
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return "unknown"
    caller = payload.get("caller", "unknown")
    return str(caller) if caller is not None else "unknown"


@app.before_request
def require_auth():
    if request.path == "/status":
        return  # health check is public
    if not _check_auth():
        log.warning("Unauthorized request from %s", request.remote_addr)
        return jsonify({"error": "unauthorized"}), 401


@app.post("/call/start")
def call_start():
    caller = _get_caller_from_request()
    log.info("Incoming call from %s — lamp ON", caller)
    lamp.turn_on()
    return jsonify({"status": "lamp_on"})


@app.post("/call/end")
def call_end():
    log.info("Call ended — lamp OFF (delay: %ss)", config.LAMP_OFF_DELAY)
    lamp.turn_off(delay=config.LAMP_OFF_DELAY)
    return jsonify({"status": "lamp_off"})


@app.get("/status")
def status():
    return jsonify({"status": "ok", "simulation": lamp.is_simulation_mode()})


if __name__ == "__main__":
    if config.AUTH_TOKEN == "change-me-please":
        log.warning("Using default AUTH_TOKEN; set LAMP_AUTH_TOKEN for production use")
    lamp.setup()
    atexit.register(lamp.cleanup)
    log.info("Starting server on %s:%s", config.HOST, config.PORT)
    app.run(host=config.HOST, port=config.PORT)
