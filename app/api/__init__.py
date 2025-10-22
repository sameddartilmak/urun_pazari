# /app/__init__.py

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager
from .config import Config

# ... (db, migrate, bcrypt, jwt eklentileri burada) ...
db = SQLAlchemy()
migrate = Migrate()
bcrypt = Bcrypt()
jwt = JWTManager()


def create_app(config_class=Config):
    """Uygulama Fabrikası (Application Factory)"""
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    jwt.init_app(app)

    # --- Blueprint Kayıtları Buraya Gelecek ---
    
    # YENİ EKLENEN SATIRLAR:
    from .api.auth import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    # ----------------------------------------

    @app.route('/')
    def hello():
        return "Ürün Kiralama API'si Çalışıyor!"

    return app