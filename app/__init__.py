from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()
login_manager = LoginManager()

def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    from app.models import User, Product
    from app import routes

    app.register_blueprint(routes.auth_bp)
    app.register_blueprint(routes.main_bp)

    with app.app_context():
        db.create_all()

    return app
