from flask import Flask
from app.api.v1 import api_v1_blueprint


def create_app(config: dict = None) -> Flask:
    """Application factory."""
    app = Flask(__name__)

    if config:
        app.config.update(config)

    # TODO: enregistrer api_v1_blueprint avec url_prefix="/api/v1"
    raise NotImplementedError

    return app
