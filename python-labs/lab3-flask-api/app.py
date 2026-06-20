import logging
from datetime import datetime
from flask import Flask, jsonify, request, Response
from typing import Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

_metrics = {
    "requests_total": 0,
    "errors_total": 0,
    "uptime_start": datetime.utcnow().isoformat(),
}


@app.route("/health")
def health() -> Tuple[Response, int]:
    # TODO: retourner {"status": "ok", "timestamp": <ISO datetime>} avec code 200
    raise NotImplementedError


@app.route("/metrics")
def metrics() -> Tuple[Response, int]:
    # TODO: retourner _metrics comme JSON avec code 200
    raise NotImplementedError


@app.route("/webhook", methods=["POST"])
def webhook() -> Tuple[Response, int]:
    """
    POST /webhook
    Body JSON obligatoire avec le champ "event_type".

    Retours:
        200: {"status": "received", "event_type": <value>}
        400: {"error": "Request body must be JSON"}       si Content-Type incorrect
        400: {"error": "Missing required field: event_type"} si champ absent
    """
    # TODO:
    # 1. Vérifier request.is_json → 400 si False
    # 2. Parser request.get_json()
    # 3. Vérifier "event_type" présent → 400 si absent
    # 4. Incrémenter _metrics["requests_total"]
    # 5. Retourner la réponse 200
    raise NotImplementedError


@app.errorhandler(404)
def not_found(e) -> Tuple[Response, int]:
    # TODO: retourner {"error": "Not found"} avec 404
    raise NotImplementedError


@app.errorhandler(405)
def method_not_allowed(e) -> Tuple[Response, int]:
    # TODO: retourner {"error": "Method not allowed"} avec 405
    raise NotImplementedError


if __name__ == "__main__":
    app.run(debug=True, port=5000)
