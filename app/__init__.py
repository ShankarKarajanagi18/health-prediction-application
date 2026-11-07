from flask import Flask

from . import db
from .config import Config
from .routes import bp


def create_app(overrides=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if overrides:
        app.config.update(overrides)

    app.teardown_appcontext(db.close_db)
    app.register_blueprint(bp)

    with app.app_context():
        db.init_db()

    return app
