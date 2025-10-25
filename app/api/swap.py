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
@swap_bp.route('/offers/received/<int:listing_id>', methods=['GET'])
@jwt_required()
def get_offers_for_my_listing(listing_id):
    """
    Kullanıcının, belirli bir ilanına gelen tüm takas tekliflerini listeler.
    Sadece ilan sahibi bu teklifleri görebilir.
    """
    current_user_id = int(get_jwt_identity())
    
    # 1. İlanı bul
    listing = Listing.query.get(listing_id)

    if not listing:
        return jsonify({'message': 'İlan bulunamadı.'}), 404

    # 2. Güvenlik: Giriş yapan kullanıcı, bu ilanın sahibi mi?
    if listing.lister_id != current_user_id:
        return jsonify({'message': 'Sadece kendi ilanlarınıza gelen teklifleri görebilirsiniz.'}), 403

    # 3. İlana ait teklifleri bul (models.py'deki 'backref' sayesinde)
    offers = listing.swap_offers_received
    
    output = []
    for offer in offers:
        # Teklifi yapanı ve teklif edilen ürünü al
        offerer = offer.offerer 
        offered_product = offer.offered_product

        offer_data = {
            'offer_id': offer.id,
            'status': offer.status.value,
            'message': offer.message,
            'created_at': offer.created_at,
            'offerer_username': offerer.username,
            'offered_product': {
                'product_id': offered_product.id,
                'title': offered_product.title,
                'description': offered_product.description,
                'category': offered_product.category
            }
        }
        output.append(offer_data)

    return jsonify({'offers': output}), 200


@swap_bp.route('/offers/respond/<int:offer_id>', methods=['POST'])
@jwt_required()
def respond_to_offer(offer_id):
    """
    Bir takas teklifini kabul eder (accept) veya reddeder (reject).
    Sadece ilanın sahibi bu işlemi yapabilir.
    """
    current_user_id = int(get_jwt_identity())
    data = request.get_json()
    action = data.get('action') # 'accept' veya 'reject'

    if not action or action not in ['accept', 'reject']:
        return jsonify({'message': '"action" alanı "accept" veya "reject" olmalıdır.'}), 400

    # 1. Teklifi bul
    offer = SwapOffer.query.get(offer_id)
    if not offer:
        return jsonify({'message': 'Teklif bulunamadı.'}), 404

    # 2. Güvenlik: Giriş yapan kullanıcı, bu teklifin yapıldığı ilanın sahibi mi?
    target_listing = offer.target_listing
    if target_listing.lister_id != current_user_id:
        return jsonify({'message': 'Sadece kendi ilanınıza gelen teklifleri yanıtlayabilirsiniz.'}), 403

    # 3. Zaten yanıtlanmış mı?
    if offer.status != OfferStatus.PENDING:
        return jsonify({'message': f'Bu teklif zaten yanıtlanmış (Durum: {offer.status.value}).'}), 400

    # 4. İşlemi gerçekleştir
    if action == 'accept':
        offer.status = OfferStatus.ACCEPTED
        
        # --- ÖNEMLİ İŞ MANTIĞI ---
        # Teklif kabul edildiğinde, ilgili ilanları deaktive etmeliyiz.
        # 1. Takas ilanı (Eski Ekran Kartı) artık 'is_active = False' olmalı.
        target_listing.is_active = False
        
        # 2. Teklif edilen ürünün (8GB RAM) durumu ne olacak?
        #    Belki onun da başka ilanları vardı? Şimdilik sadece ürünü 'değiştirildi'
        #    olarak işaretleyebiliriz (models.py'de 'status' ekleyerek)
        #    Şimdilik basit tutalım: Sadece ilanı deaktive edelim.
        
        db.session.commit()
        return jsonify({'message': 'Teklif kabul edildi. İlan devre dışı bırakıldı.', 'status': 'accepted'}), 200

    elif action == 'reject':
        offer.status = OfferStatus.REJECTED
        db.session.commit()
        return jsonify({'message': 'Teklif reddedildi.', 'status': 'rejected'}), 200   

@swap_bp.route('/offers/sent', methods=['GET'])
@jwt_required()
def get_my_sent_offers():
    """
    Giriş yapmış kullanıcının 'yaptığı' (gönderdiği) tüm takas tekliflerini listeler.
    """
    current_user_id = int(get_jwt_identity())
    
    # Sadece bu kullanıcıya ait (offerer_id) teklifleri bul
    sent_offers = SwapOffer.query.filter_by(
        offerer_id=current_user_id
    ).order_by(SwapOffer.created_at.desc()).all() # Yeniden eskiye sırala

    output = []
    for offer in sent_offers:
        # Teklifin yapıldığı ilanı ve o ilanın ürününü alalım
        target_listing = offer.target_listing
        target_product = target_listing.product
        
        offer_data = {
            'offer_id': offer.id,
            'status': offer.status.value, # pending, accepted, rejected
            'date_offered': offer.created_at,
            'my_offered_product': { # Benim teklif ettiğim ürün
                'title': offer.offered_product.title
            },
            'target_listing': { # Teklif yaptığım ilan
                'listing_id': target_listing.id,
                'title': target_product.title,
                'owner_username': target_listing.lister.username # İlan sahibinin adı
            }
        }
        output.append(offer_data)

    return jsonify({'sent_offers': output}), 200     