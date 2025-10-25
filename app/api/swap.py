# /app/api/swap.py

from flask import request, jsonify, Blueprint
from app.models import Listing, Product, SwapOffer, ListingType, OfferStatus
from app import db
from flask_jwt_extended import jwt_required, get_jwt_identity

swap_bp = Blueprint('swap', __name__)

@swap_bp.route('/offer', methods=['POST'])
@jwt_required()
def make_swap_offer():
    """Bir takas ilanına, kendi ürünlerinden biriyle teklif yapar."""
    
    current_user_id = int(get_jwt_identity())
    data = request.get_json()

    target_listing_id = data.get('target_listing_id') # Teklif yapılan ilan ID'si
    offered_product_id = data.get('offered_product_id') # Karşılığında teklif edilen ürün ID'si
    message = data.get('message', '') # İsteğe bağlı mesaj

    if not target_listing_id or not offered_product_id:
        return jsonify({'message': 'target_listing_id ve offered_product_id zorunludur.'}), 400

    # --- 1. Hedef İlanı Doğrula ---
    target_listing = Listing.query.get(target_listing_id)

    if not target_listing:
        return jsonify({'message': 'Teklif yapılmak istenen ilan bulunamadı.'}), 404
    
    if not target_listing.is_active:
        return jsonify({'message': 'Bu ilan artık aktif değil.'}), 410 # 410 Gone
    
    # İlanın türü 'swap' (takas) olmalı
    if target_listing.listing_type != ListingType.SWAP:
        return jsonify({'message': 'Teklifler sadece "swap" (takas) tipindeki ilanlara yapılabilir.'}), 400

    # --- 2. Teklif Edilen Ürünü Doğrula ---
    offered_product = Product.query.get(offered_product_id)

    if not offered_product:
        return jsonify({'message': 'Teklif ettiğiniz ürün bulunamadı.'}), 404
    
    # Ürün, teklifi yapan kullanıcıya ait olmalı
    if offered_product.owner_id != current_user_id:
        return jsonify({'message': 'Sadece kendi ürünlerinizle takas teklifi yapabilirsiniz.'}), 403 # 403 Forbidden

    # --- 3. Kendi İlanına Teklif Yapmayı Engelle ---
    if target_listing.lister_id == current_user_id:
        return jsonify({'message': 'Kendi ilanınıza takas teklifi yapamazsınız.'}), 400

    # --- 4. Teklifi Oluştur ve Kaydet ---
    new_offer = SwapOffer(
        target_listing_id=target_listing_id,
        offerer_id=current_user_id,
        offered_product_id=offered_product_id,
        message=message,
        status=OfferStatus.PENDING # Durumu "Beklemede" olarak başlar
    )

    db.session.add(new_offer)
    db.session.commit()

    return jsonify({
        'message': 'Takas teklifi başarıyla gönderildi.',
        'offer_id': new_offer.id,
        'status': new_offer.status.value
    }), 201