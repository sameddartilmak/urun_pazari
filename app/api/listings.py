# /app/api/listings.py

from flask import request, jsonify, Blueprint
from app.models import Product, Listing, ListingType
from app import db
from flask_jwt_extended import jwt_required, get_jwt_identity

# 'listings' adında yeni bir Blueprint oluşturuyoruz
listings_bp = Blueprint('listings', __name__)


@listings_bp.route('/', methods=['POST'])
@jwt_required()
def create_listing():
    """
    Bir ürün için yeni bir ilan (satış, kiralama veya takas) oluşturur.
    """
    current_user_id = int(get_jwt_identity())
    data = request.get_json()

    product_id = data.get('product_id')
    listing_type_str = data.get('listing_type') # 'sale', 'rent', 'swap'

    # --- 1. Temel Doğrulamalar ---
    if not product_id or not listing_type_str:
        return jsonify({'message': 'product_id ve listing_type zorunludur.'}), 400

    # listing_type geçerli bir enum değeri mi?
    try:
        # Gelen string'i (örn: "sale") ListingType.SALE enum'una dönüştür
        listing_type = ListingType(listing_type_str)
    except ValueError:
        return jsonify({'message': "Geçersiz listing_type. 'sale', 'rent' veya 'swap' olmalı."}), 400

    # --- 2. Ürün Sahipliği Doğrulaması (Çok Önemli) ---
    product = Product.query.get(product_id)

    if not product:
        return jsonify({'message': 'Ürün bulunamadı.'}), 404
    
    if product.owner_id != current_user_id:
        return jsonify({'message': 'Sadece kendi ürünleriniz için ilan oluşturabilirsiniz.'}), 403 # 403 Forbidden

    # --- 3. İlan Türüne Göre Veri Doğrulaması ---
    
    # Yeni İlan nesnesini oluştur
    new_listing = Listing(
        product_id=product_id,
        lister_id=current_user_id,
        listing_type=listing_type
    )

    if listing_type == ListingType.SALE:
        price = data.get('price')
        if not price:
            return jsonify({'message': 'Satış ilanları için "price" zorunludur.'}), 400
        new_listing.price = price

    elif listing_type == ListingType.RENT:
        rental_price_per_day = data.get('rental_price_per_day')
        if not rental_price_per_day:
            return jsonify({'message': 'Kiralama ilanları için "rental_price_per_day" zorunludur.'}), 400
        new_listing.rental_price_per_day = rental_price_per_day

    elif listing_type == ListingType.SWAP:
        swap_preference = data.get('swap_preference')
        if not swap_preference:
            return jsonify({'message': 'Takas ilanları için "swap_preference" (takasta ne istediğiniz) zorunludur.'}), 400
        new_listing.swap_preference = swap_preference
    
    # --- 4. Kaydetme ---
    try:
        db.session.add(new_listing)
        db.session.commit()
    except Exception as e:
        # (Örn: unique constraint hatası - product_id'ye zaten bir ilan bağlıysa)
        db.session.rollback()
        return jsonify({'message': 'Bu ürün için zaten aktif bir ilan mevcut olabilir.', 'error': str(e)}), 409

    return jsonify({
        'message': f'{listing_type.value} ilanı başarıyla oluşturuldu.',
        'listing_id': new_listing.id
    }), 201


@listings_bp.route('/', methods=['GET'])
def get_all_active_listings():
    """
    Tüm aktif ilanları (satış, kiralama, takas) listeler.
    Bu herkese açık bir rotadır, token gerektirmez.
    """
    
    # Sadece aktif olan ilanları al
    listings = Listing.query.filter_by(is_active=True).all()
    
    output = []
    for listing in listings:
        # İlana bağlı ürünü (product) ve sahibini (lister) alıyoruz
        # Bu, 'backref' sayesinde mümkün oluyor
        product = listing.product 
        lister = listing.lister

        listing_data = {
            'listing_id': listing.id,
            'listing_type': listing.listing_type.value,
            'is_active': listing.is_active,
            'created_at': listing.created_at,
            'product_details': {
                'product_id': product.id,
                'title': product.title,
                'description': product.description,
                'category': product.category,
                'image_url': product.image_url
            },
            'lister_details': { # İlan sahibinin sadece kullanıcı adını gösterelim
                'username': lister.username
            }
        }
        
        # İlan türüne göre ekstra bilgileri ekle
        if listing.listing_type == ListingType.SALE:
            listing_data['price'] = float(listing.price)
        elif listing.listing_type == ListingType.RENT:
            listing_data['rental_price_per_day'] = float(listing.rental_price_per_day)
        elif listing.listing_type == ListingType.SWAP:
            listing_data['swap_preference'] = listing.swap_preference
            
        output.append(listing_data)
        
    return jsonify({'listings': output}), 200
