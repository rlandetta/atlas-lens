from flask import Flask

from app.routes.web import web_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.register_blueprint(web_bp)
    return app
