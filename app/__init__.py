# /app/__init__.py

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager
from .config import Config  # Az önce oluşturduğumuz config dosyasını import et

# Eklentileri başlatıyoruz
db = SQLAlchemy()
migrate = Migrate()
bcrypt = Bcrypt()
jwt = JWTManager()

def create_app(config_class=Config):
    """Uygulama Fabrikası (Application Factory)"""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Eklentileri uygulama ile ilişkilendiriyoruz
    db.init_app(app)
    migrate.init_app(app, db) # migrate'i db ile ilişkilendir
    bcrypt.init_app(app)
    jwt.init_app(app)

    # --- Blueprint Kayıtları Buraya Gelecek ---
    # (API rotalarını yazdıkça burayı dolduracağız)

    @app.route('/')
    def hello():
        return "Ürün Kiralama API'si Çalışıyor!"

    return app