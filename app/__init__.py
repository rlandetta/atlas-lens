from __future__ import annotations


def create_app():
    from flask import Flask

    from app.routes.web import web_bp

    app = Flask(__name__)
    app.register_blueprint(web_bp)
    return app
