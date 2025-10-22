# /app/config.py

import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or '123321'
    
    # FORMAT: 'postgresql://<kullanici_adi>:<sifre>@<host>:<port>/<veritabani_adi>'
    # Kendi PostgreSQL şifrenizi 'sifreniz' yazan yere girin.
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'postgresql://postgres:123321@localhost:5432/urun_kiralama_db'
        
    SQLALCHEMY_TRACK_MODIFICATIONS = False