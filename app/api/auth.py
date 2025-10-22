# /app/api/auth.py

from flask import request, jsonify, Blueprint
from app.models import User
from app import db, bcrypt, jwt
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity

# 'auth' adında yeni bir Blueprint (alt-rota grubu) oluşturuyoruz
auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['POST'])
def register():
    """Kullanıcı Kayıt Endpoint'i"""
    data = request.get_json()
    
    # 1. Gelen veriyi kontrol et
    if not data or not data.get('username') or not data.get('email') or not data.get('password'):
        return jsonify({'message': 'Eksik bilgi (username, email, password zorunludur).'}), 400

    username = data['username']
    email = data['email']
    password = data['password']

    # 2. Kullanıcı adı veya email zaten var mı diye kontrol et
    if User.query.filter_by(username=username).first():
        return jsonify({'message': 'Bu kullanıcı adı zaten alınmış.'}), 409 # 409 Conflict
    
    if User.query.filter_by(email=email).first():
        return jsonify({'message': 'Bu e-posta adresi zaten kullanımda.'}), 409

    # 3. Yeni kullanıcıyı oluştur
    new_user = User(
        username=username,
        email=email
    )
    # Şifreyi modeldeki set_password metoduyla hash'leyerek ata
    new_user.set_password(password)
    
    # 4. Veritabanına kaydet
    db.session.add(new_user)
    db.session.commit()
    
    return jsonify({'message': 'Kullanıcı başarıyla oluşturuldu.'}), 201 # 201 Created


@auth_bp.route('/login', methods=['POST'])
def login():
    """Kullanıcı Giriş Endpoint'i"""
    data = request.get_json()

    # 1. Gelen veriyi kontrol et
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'message': 'Eksik bilgi (username, password zorunludur).'}), 400

    username = data['username']
    password = data['password']

    # 2. Kullanıcıyı bul
    user = User.query.filter_by(username=username).first()

    # 3. Kullanıcı var mı ve şifre doğru mu kontrol et
    #    (models.py'de yazdığımız check_password metodunu kullanıyoruz)
    if not user or not user.check_password(password):
        return jsonify({'message': 'Geçersiz kullanıcı adı veya şifre.'}), 401 # 401 Unauthorized

    # 4. Şifre doğruysa, bir JWT (JSON Web Token) oluştur
    #    Bu token, kullanıcının kimliğini kanıtlar
    access_token = create_access_token(identity=user.id)
    
    return jsonify({
        'message': f'Hoş geldin, {user.username}!',
        'access_token': access_token
    }), 200