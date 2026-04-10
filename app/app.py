from flask import Flask, jsonify, render_template, request
import os
import time
import random
import logging
from datetime import datetime

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Version is injected via environment variable at deploy time ──
APP_VERSION = os.environ.get("APP_VERSION", "v1")
APP_COLOR   = os.environ.get("APP_COLOR",   "#3B82F6")   # blue=v1, green=v2
POD_NAME    = os.environ.get("HOSTNAME",    "local")

# Simulate slight instability in v2 to demo auto-rollback (set ERROR_RATE=0 for healthy)
ERROR_RATE  = float(os.environ.get("ERROR_RATE", "0.0"))


@app.route("/")
def index():
    return render_template("index.html",
                           version=APP_VERSION,
                           color=APP_COLOR,
                           pod=POD_NAME)


@app.route("/api/info")
def info():
    """Returns version metadata – used by health-check controller."""
    # Simulate random errors to trigger rollback in demo
    if ERROR_RATE > 0 and random.random() < ERROR_RATE:
        return jsonify({"error": "Simulated failure"}), 500

    return jsonify({
        "version":    APP_VERSION,
        "pod":        POD_NAME,
        "timestamp":  datetime.utcnow().isoformat(),
        "status":     "healthy"
    })


@app.route("/health")
def health():
    """Kubernetes liveness/readiness probe."""
    return jsonify({"status": "ok", "version": APP_VERSION}), 200


@app.route("/metrics")
def metrics():
    """Minimal Prometheus-compatible text metrics endpoint."""
    pod = POD_NAME
    ver = APP_VERSION
    ts  = int(time.time() * 1000)
    body = (
        f'# HELP app_info Application version info\n'
        f'# TYPE app_info gauge\n'
        f'app_info{{version="{ver}",pod="{pod}"}} 1 {ts}\n'
        f'# HELP app_requests_total Total HTTP requests\n'
        f'# TYPE app_requests_total counter\n'
        f'app_requests_total{{version="{ver}"}} 1 {ts}\n'
    )
    return body, 200, {"Content-Type": "text/plain; version=0.0.4"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)