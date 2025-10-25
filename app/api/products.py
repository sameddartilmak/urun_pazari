# /app/api/products.py

from flask import request, jsonify, Blueprint
from app.models import Product, User
from app import db
from flask_jwt_extended import jwt_required, get_jwt_identity

# 'products' adında yeni bir Blueprint oluşturuyoruz
products_bp = Blueprint('products', __name__)


@products_bp.route('/', methods=['POST'])
@jwt_required() # Bu satır, bu rotanın token gerektirdiğini belirtir!
def create_product():
    """Yeni bir ürün oluşturur."""
    
    # 1. Giriş yapan kullanıcının kimliğini (ID) al
    # Bu ID'yi, /login olduğunda oluşturduğumuz token'dan alır
    current_user_id = int(get_jwt_identity())
    
    data = request.get_json()

    # 2. Gerekli veriler geldi mi?
    if not data or not data.get('title') or not data.get('category'):
        return jsonify({'message': 'Eksik bilgi (title ve category zorunludur).'}), 400

    # 3. Yeni ürünü oluştur ve sahibini (owner_id) giriş yapan kullanıcı olarak ata
    new_product = Product(
        title=data['title'],
        description=data.get('description'), # .get() kullanılırsa, veri yoksa None döner
        category=data['category'],
        image_url=data.get('image_url'),
        owner_id=current_user_id  # Ürünü giriş yapan kullanıcıya bağla
    )
    
    db.session.add(new_product)
    db.session.commit()
    
    # (Daha iyi bir API için, oluşturulan ürünün JSON halini döndürmek iyidir)
    return jsonify({
        'message': 'Ürün başarıyla eklendi.',
        'product': {
            'id': new_product.id,
            'title': new_product.title,
            'owner_id': new_product.owner_id
        }
    }), 201


@products_bp.route('/', methods=['GET'])
@jwt_required() # Bu rota da token gerektirir
def get_my_products():
    """Giriş yapmış kullanıcının kendi ürünlerini listeler."""
    
    # 1. Giriş yapan kullanıcının kimliğini (ID) al
    current_user_id = int(get_jwt_identity())

    # 2. Sadece bu kullanıcıya ait olan ürünleri veritabanından bul
    user_products = Product.query.filter_by(owner_id=current_user_id).all()

    # 3. Ürünleri JSON formatına dönüştür
    output = []
    for product in user_products:
        product_data = {
            'id': product.id,
            'title': product.title,
            'description': product.description,
            'category': product.category,
            'status': product.status, # models.py'de 'available' olarak varsayılan
            'created_at': product.created_at
        }
        output.append(product_data)

    return jsonify({'products': output}), 200