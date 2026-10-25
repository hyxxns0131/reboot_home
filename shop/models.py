from datetime import datetime, timezone
from core.extensions import db

class Product(db.Model):
    __tablename__ = 'shop_product'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    is_active = db.Column(db.Boolean, default=True)    # False = hidden from the site (admin "Hide")
    is_deleted = db.Column(db.Boolean, nullable=False, default=False)  # archived by admin "Delete" (kept for past orders)
    options = db.relationship('ProductOption', backref='product', lazy=True)

class ProductOption(db.Model):
    __tablename__ = 'shop_product_option'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('shop_product.id'), nullable=False)
    sku = db.Column(db.String(100), unique=True, nullable=False)
    label = db.Column(db.String(60), nullable=False)
    unit_count = db.Column(db.Integer, default=1)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    is_active = db.Column(db.Boolean, default=True)

class ReferralLink(db.Model):
    __tablename__ = 'shop_referral_link'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), unique=True, nullable=False)
    influencer_name = db.Column(db.String(100))
    platform = db.Column(db.String(30))
    discount_rate = db.Column(db.Numeric(5, 4))
    commission_rate = db.Column(db.Numeric(5, 4))
    clicks = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    landing = db.Column(db.String(120), nullable=False, default='')  # page the link opens ('' = home)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

class ProductDiscount(db.Model):
    """Store-wide sale set on the admin Homepage manager. option_id NULL = every option of the product."""
    __tablename__ = 'shop_product_discount'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('shop_product.id'), nullable=False)
    option_id = db.Column(db.Integer, db.ForeignKey('shop_product_option.id'))
    kind = db.Column(db.String(10), nullable=False)  # 'percent' or 'amount' (USD off per unit)
    value = db.Column(db.Numeric(10, 2), nullable=False)
    label = db.Column(db.String(60), nullable=False, default='')
    starts_on = db.Column(db.Date)
    ends_on = db.Column(db.Date)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    product = db.relationship('Product')
    option = db.relationship('ProductOption')

class Order(db.Model):
    __tablename__ = 'shop_order'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('auth_user.id'))
    referral_link_id = db.Column(db.Integer, db.ForeignKey('shop_referral_link.id'))
    status = db.Column(db.String(20), default='paid')
    points_used = db.Column(db.Integer, nullable=False, default=0)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    discount = db.Column(db.Numeric(10, 2), nullable=False)
    total = db.Column(db.Numeric(10, 2), nullable=False)
    ship_name = db.Column(db.String(100))
    ship_state = db.Column(db.String(2))
    ship_city = db.Column(db.String(100))
    is_dummy = db.Column(db.Boolean, default=False)
    ordered_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    referral = db.relationship('ReferralLink')
    items = db.relationship('OrderItem', backref='order', cascade='all, delete-orphan')

class OrderItem(db.Model):
    __tablename__ = 'shop_order_item'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('shop_order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('shop_product.id'), nullable=False)
    option_id = db.Column(db.Integer, db.ForeignKey('shop_product_option.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    points_used = db.Column(db.Integer, nullable=False, default=0)
    line_discount = db.Column(db.Numeric(10, 2), nullable=False)
    line_total = db.Column(db.Numeric(10, 2), nullable=False)
    product = db.relationship('Product')
    option = db.relationship('ProductOption')
