from . import db, bcrypt  # __init__.py dosyamızdan db ve bcrypt'i alıyoruz
from datetime import datetime
import enum

# Enum: Belirli alanlar için sabit seçenekler tanımlamak (daha temiz kod)
class ListingType(enum.Enum):
    SALE = 'sale'
    RENT = 'rent'
    SWAP = 'swap'

class TransactionStatus(enum.Enum):
    PENDING = 'pending'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'

class OfferStatus(enum.Enum):
    PENDING = 'pending'
    ACCEPTED = 'accepted'
    REJECTED = 'rejected'


class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # İlişkiler: Bu kullanıcının sahip olduğu ürünler, ilanlar vb.
    # "backref" bu ilişkiyi ters taraftan (örn: Product.owner) çağırmamızı sağlar
    # "lazy=True" verilerin sadece ihtiyaç duyulduğunda yüklenmesini sağlar
    products = db.relationship('Product', backref='owner', lazy=True)
    listings = db.relationship('Listing', backref='lister', lazy=True)

    def set_password(self, password):
        """Şifreyi hash'leyerek kaydeder."""
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        """Verilen şifrenin hash ile uyuşup uyuşmadığını kontrol eder."""
        return bcrypt.check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'


class Product(db.Model):
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(100))
    image_url = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Yabancı Anahtar (Foreign Key): Bu ürünün sahibini 'users' tablosuna bağlar
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # İlişki: Bu ürüne ait ilan (genellikle bir ürünün tek bir aktif ilanı olur)
    # uselist=False, bunun "bire-çok" değil, "bire-bir" ilişki olduğunu belirtir
    listing = db.relationship('Listing', backref='product', lazy=True, uselist=False)
    
    def __repr__(self):
        return f'<Product {self.title}>'


class Listing(db.Model):
    __tablename__ = 'listings'
    
    id = db.Column(db.Integer, primary_key=True)
    listing_type = db.Column(db.Enum(ListingType), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=True) # Satış fiyatı (10 hane, 2 ondalık)
    rental_price_per_day = db.Column(db.Numeric(10, 2), nullable=True) # Günlük kiralama bedeli
    swap_preference = db.Column(db.Text, nullable=True) # Takasta ne istendiği
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Yabancı Anahtarlar
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, unique=True) # Bir ürünün tek ilanı olabilir
    lister_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # İlişkiler
    # Bu ilana yapılan takas teklifleri
    swap_offers_received = db.relationship('SwapOffer', backref='target_listing', lazy=True, foreign_keys='SwapOffer.target_listing_id')
    
    def __repr__(self):
        return f'<Listing {self.id} ({self.listing_type.value}) for Product {self.product_id}>'


class Transaction(db.Model):
    __tablename__ = 'transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    transaction_type = db.Column(db.Enum(ListingType), nullable=False) # 'sale' veya 'rent' olacak
    total_price = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.Enum(TransactionStatus), default=TransactionStatus.PENDING, nullable=False)
    
    # Kiralama için
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Yabancı Anahtarlar
    listing_id = db.Column(db.Integer, db.ForeignKey('listings.id'), nullable=False)
    # Satın alan / Kiralayan kişi
    buyer_or_renter_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # İlişkiler
    listing = db.relationship('Listing', backref='transactions', lazy=True)
    buyer = db.relationship('User', backref='transactions', lazy=True)

    def __repr__(self):
        return f'<Transaction {self.id} - {self.status.value}>'


class SwapOffer(db.Model):
    __tablename__ = 'swap_offers'
    
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.Enum(OfferStatus), default=OfferStatus.PENDING, nullable=False)
    message = db.Column(db.Text, nullable=True) # Teklif mesajı
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Yabancı Anahtarlar
    # Teklifin yapıldığı ilan
    target_listing_id = db.Column(db.Integer, db.ForeignKey('listings.id'), nullable=False)
    # Teklifi yapan kişi
    offerer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    # Karşılığında teklif edilen ürün
    offered_product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)

    # İlişkiler
    offerer = db.relationship('User', backref='swap_offers_made', lazy=True)
    offered_product = db.relationship('Product', backref='swap_offers', lazy=True)

    def __repr__(self):
        return f'<SwapOffer {self.id} by User {self.offerer_id} for Listing {self.target_listing_id}>'