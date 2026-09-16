import logging

from flask import Flask, request

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)


@app.route("/health")
def health():
    return {"health": "healthy"}


# Dapr's sidecar calls this once at startup to learn what to subscribe to —
# not app-facing, Dapr-facing.
@app.route("/dapr/subscribe")
def subscribe():
    return [{"pubsubname": "pubsub", "topic": "notifications", "route": "/notifications"}]


# Dapr delivers every message published to the "notifications" topic here.
@app.route("/notifications", methods=["POST"])
def notifications():
    event = request.get_json(silent=True) or {}
    app.logger.info("[notifier] received: %r", event)
    return "", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
