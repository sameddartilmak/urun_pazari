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

@products_bp.route('/<int:product_id>', methods=['PUT'])
@jwt_required()
def update_product(product_id):
    """
    Belirli bir ürünü günceller.
    Sadece ürünün sahibi bu ürünü güncelleyebilir.
    """
    current_user_id = int(get_jwt_identity())
    data = request.get_json()

    # 1. Ürünü bul
    product = Product.query.get(product_id)
    if not product:
        return jsonify({'message': 'Ürün bulunamadı.'}), 404

    # 2. Güvenlik: Kullanıcı bu ürünün sahibi mi?
    if product.owner_id != current_user_id:
        return jsonify({'message': 'Sadece kendi ürünlerinizi güncelleyebilirsiniz.'}), 403

    # 3. Güncelle
    # Sadece gönderilen alanları güncelliyoruz
    if 'title' in data:
        product.title = data['title']
    if 'description' in data:
        product.description = data['description']
    if 'category' in data:
        product.category = data['category']
    if 'image_url' in data:
        product.image_url = data['image_url']
    
    db.session.commit()

    return jsonify({
        'message': 'Ürün başarıyla güncellendi.',
        'product': {
            'id': product.id,
            'title': product.title,
            'description': product.description,
            'category': product.category
        }
    }), 200


@products_bp.route('/<int:product_id>', methods=['DELETE'])
@jwt_required()
def delete_product(product_id):
    """
    Belirli bir ürünü siler.
    Sadece ürünün sahibi bu ürünü silebilir.
    Eğer ürünün aktif bir ilanı varsa silme işlemi engellenir.
    """
    current_user_id = int(get_jwt_identity())

    # 1. Ürünü bul
    product = Product.query.get(product_id)
    if not product:
        return jsonify({'message': 'Ürün bulunamadı.'}), 404

    # 2. Güvenlik: Kullanıcı bu ürünün sahibi mi?
    if product.owner_id != current_user_id:
        return jsonify({'message': 'Sadece kendi ürünlerinizi silebilirsiniz.'}), 403

    # 3. İŞ MANTIĞI KONTROLÜ: Ürünün aktif bir ilanı var mı?
    #    (models.py'deki backref 'listing' sayesinde)
    if product.listing and product.listing.is_active:
        return jsonify({
            'message': 'Bu ürün şu anda aktif bir ilanda (satış/kiralama/takas). Silmek için önce ilanı kaldırın.',
            'listing_id': product.listing.id
        }), 409 # 409 Conflict

    # 4. Güvenle Sil
    # Bu ürüne bağlı (artık aktif olmayan) ilanlar, teklifler, işlemler varsa
    # veritabanı modelimizde 'ondelete' ayarı yapmamız gerekirdi.
    # Şimdilik, sadece aktif ilanı yoksa silmeye izin veriyoruz.
    # (Daha güvenli bir yöntem, ilişkili her şeyi silmek veya ürünü de 'soft delete' yapmaktır)
    
    # Not: Eğer bu ürüne bağlı 'swap_offers' veya 'transactions' varsa
    # bu silme işlemi veritabanı hatası verebilir (Foreign Key Constraint).
    # Bu durumda, db.session.delete(product) yerine product.status = 'deleted'
    # gibi bir 'soft delete' yapmak daha iyidir.
    # Şimdilik 'hard delete' (gerçek silme) deneyelim:
    
    try:
        db.session.delete(product)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'message': 'Silme hatası. Bu ürüne bağlı tamamlanmış işlemler veya teklifler olabilir.',
            'error': str(e)
        }), 500 # 500 Internal Server Error (veya 409 Conflict)

    return jsonify({'message': 'Ürün başarıyla silindi.'}), 200