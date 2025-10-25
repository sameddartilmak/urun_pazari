# /app/api/transactions.py

from flask import request, jsonify, Blueprint
# datetime'i tarih işlemleri için import ediyoruz
from datetime import datetime
from app.models import Listing, Transaction, ListingType, TransactionStatus,User
from app import db
from flask_jwt_extended import jwt_required, get_jwt_identity


transactions_bp = Blueprint('transactions', __name__)


@transactions_bp.route('/buy', methods=['POST'])
@jwt_required()
def buy_listing():
    """
    Bir 'sale' (satış) ilanını satın alır.
    """
    # ... (Bu fonksiyonu zaten yazmıştık, olduğu gibi kalıyor) ...
    current_user_id = int(get_jwt_identity())
    data = request.get_json()
    
    listing_id = data.get('listing_id')
    if not listing_id:
        return jsonify({'message': 'listing_id zorunludur.'}), 400

    # --- 1. İlanı Doğrula ---
    listing = Listing.query.get(listing_id)

    if not listing:
        return jsonify({'message': 'İlan bulunamadı.'}), 404
    
    if not listing.is_active:
        return jsonify({'message': 'Bu ilan artık aktif (satışta) değil.'}), 410 # 410 Gone

    # --- 2. İş Mantığını Doğrula ---
    if listing.listing_type != ListingType.SALE:
        return jsonify({'message': 'Bu API sadece "sale" (satış) tipindeki ilanları satın almak içindir.'}), 400

    if listing.lister_id == current_user_id:
        return jsonify({'message': 'Kendi ilanınızı satın alamazsınız.'}), 400

    # --- 3. Satış İşlemini Gerçekleştir ---
    listing.is_active = False
    
    new_transaction = Transaction(
        listing_id=listing_id,
        buyer_or_renter_id=current_user_id,
        transaction_type=ListingType.SALE,
        total_price=listing.price,
        status=TransactionStatus.COMPLETED
    )
    
    try:
        db.session.add(new_transaction)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'İşlem sırasında bir hata oluştu.', 'error': str(e)}), 500

    return jsonify({
        'message': f'Satın alma işlemi başarılı. (İlan: {listing.product.title})',
        'transaction_id': new_transaction.id,
        'total_price_paid': float(new_transaction.total_price)
    }), 201


# --- YENİ EKLENEN KOD AŞAĞIDA ---

@transactions_bp.route('/rent', methods=['POST'])
@jwt_required()
def rent_listing():
    """
    Bir 'rent' (kiralama) ilanını belirli tarihler için kiralar.
    Tarih çakışması kontrolü yapar.
    """
    current_user_id = int(get_jwt_identity())
    data = request.get_json()

    listing_id = data.get('listing_id')
    start_date_str = data.get('start_date') # Format: 'YYYY-MM-DD'
    end_date_str = data.get('end_date')   # Format: 'YYYY-MM-DD'

    if not all([listing_id, start_date_str, end_date_str]):
        return jsonify({'message': 'listing_id, start_date ve end_date zorunludur.'}), 400

    # --- 1. Tarihleri Python'un anlayacağı formata çevir ---
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'message': 'Tarih formatı geçersiz. Lütfen "YYYY-MM-DD" formatını kullanın.'}), 400

    # --- 2. Tarih Mantığını Kontrol Et ---
    if start_date < datetime.utcnow().date():
        return jsonify({'message': 'Kiralama başlangıç tarihi geçmiş bir tarih olamaz.'}), 400
    if end_date < start_date:
        return jsonify({'message': 'Bitiş tarihi, başlangıç tarihinden önce olamaz.'}), 400
    if start_date == end_date:
        return jsonify({'message': 'En az 1 gün kiralanmalıdır (bitiş tarihi başlangıçtan sonra olmalı).'}), 400
        
    # --- 3. İlanı Doğrula ---
    listing = Listing.query.get(listing_id)
    if not listing:
        return jsonify({'message': 'İlan bulunamadı.'}), 404
    if not listing.is_active:
        return jsonify({'message': 'Bu ilan artık kiralamaya aktif değil.'}), 410
    if listing.listing_type != ListingType.RENT:
        return jsonify({'message': 'Bu API sadece "rent" (kiralama) tipindeki ilanlar içindir.'}), 400
    if listing.lister_id == current_user_id:
        return jsonify({'message': 'Kendi ilanınızı kiralayamazsınız.'}), 400

    # --- 4. TARİH ÇAKIŞMASI KONTROLÜ (En Önemli Kısım) ---
    # Bu ilana ait, istenen tarih aralığıyla çakışan başka bir kiralama (transaction) var mı?
    
    # SQLAlchemy'nin 'and_' ve 'or_' fonksiyonlarını import etmemiz gerekebilir,
    # ama şimdilik basit filtreleme ile deneyelim.
    # Logic: (İstenen_Başlangıç < Mevcut_Bitiş) AND (İstenen_Bitiş > Mevcut_Başlangıç)
    
    overlapping_rentals = Transaction.query.filter(
        Transaction.listing_id == listing_id,
        Transaction.transaction_type == ListingType.RENT,
        Transaction.status != TransactionStatus.CANCELLED, # İptal edilenler hariç
        Transaction.start_date < end_date,
        Transaction.end_date > start_date
    ).first() # Çakışan ilk kaydı bul

    if overlapping_rentals:
        return jsonify({
            'message': 'Seçtiğiniz tarihlerde bu ürün zaten kiralanmış.',
            'conflicting_rental_starts': overlapping_rentals.start_date.isoformat(),
            'conflicting_rental_ends': overlapping_rentals.end_date.isoformat()
        }), 409 # 409 Conflict

    # --- 5. Kiralama İşlemini Gerçekleştir ---
    
    # Toplam fiyatı hesapla
    num_days = (end_date - start_date).days
    total_price = num_days * listing.rental_price_per_day

    new_transaction = Transaction(
        listing_id=listing_id,
        buyer_or_renter_id=current_user_id,
        transaction_type=ListingType.RENT,
        total_price=total_price,
        status=TransactionStatus.PENDING, # Kiralama işlemi 'onay bekliyor' olabilir
        start_date=start_date,
        end_date=end_date
    )
    
    db.session.add(new_transaction)
    db.session.commit()

    return jsonify({
        'message': f'Kiralama talebi başarıyla oluşturuldu. (İlan: {listing.product.title})',
        'transaction_id': new_transaction.id,
        'start_date': new_transaction.start_date.isoformat(),
        'end_date': new_transaction.end_date.isoformat(),
        'total_price': float(new_transaction.total_price)
    }), 201

@transactions_bp.route('/my_purchases', methods=['GET'])
@jwt_required()
def get_my_purchases():
    """
    Giriş yapmış kullanıcının 'satın aldığı' (sale) tüm işlemleri listeler.
    """
    current_user_id = int(get_jwt_identity())
    
    # Sadece bu kullanıcıya ait ve tipi 'sale' olan işlemleri bul
    purchases = Transaction.query.filter_by(
        buyer_or_renter_id=current_user_id,
        transaction_type=ListingType.SALE,
        status=TransactionStatus.COMPLETED
    ).order_by(Transaction.created_at.desc()).all() # Yeniden eskiye sırala

    output = []
    for purchase in purchases:
        # İşleme bağlı ilanı ve ürünü alalım
        listing = purchase.listing
        product = listing.product
        
        purchase_data = {
            'transaction_id': purchase.id,
            'date_purchased': purchase.created_at,
            'price_paid': float(purchase.total_price),
            'product_details': {
                'title': product.title,
                'description': product.description,
                'category': product.category
            },
            'seller_username': listing.lister.username # Satıcının kullanıcı adı
        }
        output.append(purchase_data)

    return jsonify({'purchases': output}), 200


@transactions_bp.route('/my_rentals', methods=['GET'])
@jwt_required()
def get_my_rentals():
    """
    Giriş yapmış kullanıcının 'kiraladığı' (rent) tüm işlemleri listeler.
    """
    current_user_id = int(get_jwt_identity())
    
    # Sadece bu kullanıcıya ait ve tipi 'rent' olan işlemleri bul
    rentals = Transaction.query.filter_by(
        buyer_or_renter_id=current_user_id,
        transaction_type=ListingType.RENT
    ).order_by(Transaction.start_date.desc()).all() # Başlangıç tarihine göre sırala

    output = []
    for rental in rentals:
        listing = rental.listing
        product = listing.product
        
        rental_data = {
            'transaction_id': rental.id,
            'status': rental.status.value,
            'start_date': rental.start_date.isoformat(),
            'end_date': rental.end_date.isoformat(),
            'total_price_paid': float(rental.total_price),
            'product_details': {
                'title': product.title,
                'description': product.description
            },
            'owner_username': listing.lister.username # Ürün sahibinin kullanıcı adı
        }
        output.append(rental_data)

    return jsonify({'rentals': output}), 200  

@transactions_bp.route('/received', methods=['GET'])
@jwt_required()
def get_received_transactions():
    """
    Giriş yapmış kullanıcının ilanlarına gelen 'tüm' işlemleri (satışlar ve kiralamalar) listeler.
    Bu, bir "Satıcı Paneli" API'sidir.
    """
    current_user_id = int(get_jwt_identity())
    
    # 1. Bu kullanıcıya ait tüm ilan ID'lerini bul
    my_listing_ids = [listing.id for listing in Listing.query.filter_by(lister_id=current_user_id).all()]

    if not my_listing_ids:
        return jsonify({'message': 'Henüz yayınlanmış bir ilanınız bulunmuyor.', 'transactions': []}), 200

    # 2. 'listing_id'si bu listede olan tüm 'transactions' kayıtlarını bul
    received_transactions = Transaction.query.filter(
        Transaction.listing_id.in_(my_listing_ids)
    ).order_by(Transaction.created_at.desc()).all()

    output = []
    for transaction in received_transactions:
        # Bu işlemi yapan kişiyi (alıcı/kiralayan) ve ilgili ürünü al
        buyer_or_renter = User.query.get(transaction.buyer_or_renter_id)
        product = transaction.listing.product
        
        transaction_data = {
            'transaction_id': transaction.id,
            'type': transaction.transaction_type.value, # 'sale' veya 'rent'
            'status': transaction.status.value,
            'date': transaction.created_at,
            'product_title': product.title,
            'total_price': float(transaction.total_price),
            'client_username': buyer_or_renter.username, # İşlemi yapan kişinin adı
            'start_date': transaction.start_date.isoformat() if transaction.start_date else None,
            'end_date': transaction.end_date.isoformat() if transaction.end_date else None,
        }
        output.append(transaction_data)

    return jsonify({'received_transactions': output}), 200  

@transactions_bp.route('/rent/respond/<int:transaction_id>', methods=['POST'])
@jwt_required()
def respond_to_rent_transaction(transaction_id):
    """
    Beklemedeki (pending) bir kiralama talebini kabul eder (accept) veya reddeder (reject).
    Sadece ilanın sahibi bu işlemi yapabilir.
    """
    current_user_id = int(get_jwt_identity())
    data = request.get_json()
    action = data.get('action') # 'accept' veya 'reject'

    if not action or action not in ['accept', 'reject']:
        return jsonify({'message': '"action" alanı "accept" veya "reject" olmalıdır.'}), 400

    # 1. İşlemi (Transaction) bul
    transaction = Transaction.query.get(transaction_id)
    if not transaction:
        return jsonify({'message': 'Kiralama talebi bulunamadı.'}), 404

    # 2. Güvenlik: Giriş yapan kullanıcı, bu işlemin yapıldığı ilanın sahibi mi?
    target_listing = transaction.listing
    if target_listing.lister_id != current_user_id:
        return jsonify({'message': 'Sadece kendi ilanınıza gelen talepleri yanıtlayabilirsiniz.'}), 403

    # 3. Zaten yanıtlanmış mı?
    if transaction.status != TransactionStatus.PENDING:
        return jsonify({'message': f'Bu talep zaten yanıtlanmış (Durum: {transaction.status.value}).'}), 400
    
    # 4. İşlemi gerçekleştir
    if action == 'accept':
        # (Burada tekrar tarih çakışması kontrolü yapılabilir, ama 'rent'
        # fonksiyonu zaten bunu yaptığı için 'pending'e düşmüştür.)
        
        transaction.status = TransactionStatus.COMPLETED # Veya 'CONFIRMED' olabilirdi
        db.session.commit()
        return jsonify({'message': 'Kiralama talebi kabul edildi.', 'status': 'completed'}), 200

    elif action == 'reject':
        transaction.status = TransactionStatus.CANCELLED
        db.session.commit()
        return jsonify({'message': 'Kiralama talebi reddedildi.', 'status': 'cancelled'}), 200