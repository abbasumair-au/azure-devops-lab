from flask import jsonify, request, Response
from typing import Tuple
from app.api.v1 import api_v1_blueprint
from app.services.health import HealthService

health_service = HealthService()


@api_v1_blueprint.route("/health")
def health() -> Tuple[Response, int]:
    # TODO: appeler health_service.get_status() et retourner en JSON avec 200
    raise NotImplementedError


@api_v1_blueprint.route("/resources", methods=["GET"])
def list_resources() -> Tuple[Response, int]:
    """
    GET /api/v1/resources
    Query params optionnels: ?type=VirtualMachine&region=eastus&compliant=true
    Réponse: {"resources": [...], "count": N}
    """
    # TODO:
    # 1. Récupérer request.args.get("type"), ("region"), ("compliant")
    # 2. Appeler health_service.get_resources(resource_type, region, compliant)
    # 3. Retourner {"resources": result, "count": len(result)} avec 200
    raise NotImplementedError


@api_v1_blueprint.route("/resources/<resource_id>", methods=["GET"])
def get_resource(resource_id: str) -> Tuple[Response, int]:
    # TODO:
    # - Appeler health_service.get_resource(resource_id)
    # - Si None → {"error": "Resource not found"} avec 404
    # - Sinon → resource dict avec 200
    raise NotImplementedError


@api_v1_blueprint.errorhandler(404)
def not_found(e) -> Tuple[Response, int]:
    return jsonify({"error": "Not found"}), 404
