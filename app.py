import os
import secrets
from datetime import datetime
from decimal import Decimal
from functools import wraps
from pathlib import Path
from urllib.parse import urlparse

from flask import Flask, abort, flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from sqlalchemy import case
from sqlalchemy.ext.hybrid import hybrid_property
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from PIL import Image

try:
    import cloudinary
    import cloudinary.uploader
except ImportError:
    cloudinary = None

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-me-" + secrets.token_hex(16))
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", f"sqlite:///{BASE_DIR / 'store.db'}"
).replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024
app.config["UPLOAD_FOLDER"] = str(UPLOAD_DIR)
app.config["WTF_CSRF_TIME_LIMIT"] = 3600
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("COOKIE_SECURE", "0") == "1"

db = SQLAlchemy(app)
csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = "admin_login"

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}

class Admin(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    slug = db.Column(db.String(140), unique=True, nullable=False)
    description = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    products = db.relationship("Product", backref="category", lazy=True)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(220), nullable=False)
    slug = db.Column(db.String(240), unique=True, nullable=False)
    brand = db.Column(db.String(120), default="")
    price = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    discount_price = db.Column(db.Numeric(12, 2), nullable=True)
    stock = db.Column(db.Integer, nullable=False, default=0)
    short_description = db.Column(db.String(500), default="")
    description = db.Column(db.Text, default="")
    specifications = db.Column(db.Text, default="")
    tags = db.Column(db.String(500), default="")
    rating = db.Column(db.Float, default=0)
    review_count = db.Column(db.Integer, default=0)
    featured = db.Column(db.Boolean, default=False)
    best_seller = db.Column(db.Boolean, default=False)
    new_arrival = db.Column(db.Boolean, default=True)
    sale_item = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"), nullable=True)
    images = db.relationship("ProductImage", backref="product", cascade="all, delete-orphan", lazy=True)
    reviews = db.relationship("Review", backref="product", cascade="all, delete-orphan", lazy=True)

    @hybrid_property
    def effective_price(self):
        return self.discount_price if self.discount_price is not None else self.price

    @effective_price.expression
    def effective_price(cls):
        return case((cls.discount_price.isnot(None), cls.discount_price), else_=cls.price)

    @property
    def in_stock(self):
        return self.stock > 0

class ProductImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    image_url = db.Column(db.String(500), nullable=False)
    alt_text = db.Column(db.String(220), default="")
    sort_order = db.Column(db.Integer, default=0)

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    phone = db.Column(db.String(40), nullable=False)
    email = db.Column(db.String(180), default="")
    address = db.Column(db.String(500), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    area = db.Column(db.String(120), default="")
    postal_code = db.Column(db.String(20), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    orders = db.relationship("Order", backref="customer", lazy=True)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(40), unique=True, nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey("customer.id"), nullable=False)
    subtotal = db.Column(db.Numeric(12, 2), nullable=False)
    delivery_charge = db.Column(db.Numeric(12, 2), nullable=False)
    total = db.Column(db.Numeric(12, 2), nullable=False)
    payment_method = db.Column(db.String(40), nullable=False, default="cod")
    status = db.Column(db.String(30), nullable=False, default="Pending")
    notes = db.Column(db.String(500), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    items = db.relationship("OrderItem", backref="order", cascade="all, delete-orphan", lazy=True)

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    product_name = db.Column(db.String(220), nullable=False)
    unit_price = db.Column(db.Numeric(12, 2), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    product = db.relationship("Product")

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    customer_name = db.Column(db.String(120), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, default="")
    approved = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class Wishlist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    visitor_key = db.Column(db.String(100), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    product = db.relationship("Product", cascade="all")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class Advertisement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(220), nullable=False)
    description = db.Column(db.String(500), default="")
    image_url = db.Column(db.String(500), nullable=False)
    cta_text = db.Column(db.String(80), default="Shop Now")
    cta_link = db.Column(db.String(500), default="/shop")
    placement = db.Column(db.String(50), default="home")
    enabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class Banner(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(220), nullable=False)
    subtitle = db.Column(db.String(500), default="")
    image_url = db.Column(db.String(500), nullable=False)
    button_text = db.Column(db.String(80), default="Shop Now")
    button_link = db.Column(db.String(500), default="/shop")
    enabled = db.Column(db.Boolean, default=True)
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class SiteSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(80), unique=True, nullable=False)
    value = db.Column(db.Text, default="")

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Admin, int(user_id))

@app.context_processor
def inject_globals():
    settings = {x.key: x.value for x in SiteSetting.query.all()}
    cart = session.get("cart", {})
    cart_count = sum(int(v) for v in cart.values())
    wishlist_count = Wishlist.query.filter_by(visitor_key=get_visitor_key()).count() if request else 0
    return {
        "store": settings,
        "cart_count": cart_count,
        "wishlist_count": wishlist_count,
        "current_year": datetime.utcnow().year,
    }

@app.template_filter("money")
def money(value):
    try:
        return f"{Decimal(value):,.2f}"
    except Exception:
        return "0.00"

def get_visitor_key():
    if "visitor_key" not in session:
        session["visitor_key"] = secrets.token_urlsafe(24)
    return session["visitor_key"]

def slugify(value):
    import re
    value = re.sub(r"[^a-zA-Z0-9\s-]", "", value).strip().lower()
    return re.sub(r"[\s-]+", "-", value) or secrets.token_hex(4)

def unique_slug(model, value, current_id=None):
    base = slugify(value)
    slug = base
    i = 2
    while True:
        q = model.query.filter_by(slug=slug)
        if current_id:
            q = q.filter(model.id != current_id)
        if not q.first():
            return slug
        slug = f"{base}-{i}"
        i += 1

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def save_upload(file):
    if not file or not file.filename:
        return None
    if not allowed_file(file.filename):
        raise ValueError("Unsupported image type. Use JPG, PNG, WEBP or GIF.")
    # Validate the file contents, not just the filename extension.
    try:
        file.stream.seek(0)
        with Image.open(file.stream) as image:
            image.verify()
        file.stream.seek(0)
    except Exception as exc:
        raise ValueError("The uploaded file is not a valid image.") from exc
    # Production: use Cloudinary when CLOUDINARY_URL is configured.
    # Local development: save to the local uploads directory.
    if cloudinary and os.environ.get("CLOUDINARY_URL"):
        result = cloudinary.uploader.upload(file, folder="novastore", resource_type="image", unique_filename=True)
        return result.get("secure_url")
    ext = file.filename.rsplit(".", 1)[1].lower()
    name = f"{secrets.token_hex(16)}.{ext}"
    path = UPLOAD_DIR / secure_filename(name)
    file.save(path)
    return f"/uploads/{path.name}"

def admin_required(fn):
    @wraps(fn)
    @login_required
    def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)
    return wrapper

@app.get("/")
def home():
    banners = Banner.query.filter_by(enabled=True).order_by(Banner.sort_order.asc()).all()
    featured = Product.query.filter_by(featured=True).order_by(Product.created_at.desc()).limit(8).all()
    best = Product.query.filter_by(best_seller=True).order_by(Product.created_at.desc()).limit(8).all()
    newest = Product.query.order_by(Product.created_at.desc()).limit(8).all()
    sale = Product.query.filter_by(sale_item=True).order_by(Product.created_at.desc()).limit(8).all()
    ads = Advertisement.query.filter_by(enabled=True, placement="home").order_by(Advertisement.created_at.desc()).limit(3).all()
    categories = Category.query.order_by(Category.name.asc()).all()
    return render_template("home.html", banners=banners, featured=featured, best=best, newest=newest, sale=sale, ads=ads, categories=categories)

@app.get("/shop")
def shop():
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    sort = request.args.get("sort", "newest")
    min_price = request.args.get("min_price", type=float)
    max_price = request.args.get("max_price", type=float)
    min_rating = request.args.get("min_rating", type=float)
    in_stock = request.args.get("in_stock") == "1"
    on_sale = request.args.get("on_sale") == "1"
    products_q = Product.query
    if q:
        like = f"%{q}%"
        products_q = products_q.filter(
            db.or_(Product.name.ilike(like), Product.brand.ilike(like), Product.tags.ilike(like))
        )
    if category:
        products_q = products_q.join(Category).filter(Category.slug == category)
    if min_price is not None:
        products_q = products_q.filter(Product.effective_price >= min_price)
    if max_price is not None:
        products_q = products_q.filter(Product.effective_price <= max_price)
    if min_rating is not None:
        products_q = products_q.filter(Product.rating >= min_rating)
    if in_stock:
        products_q = products_q.filter(Product.stock > 0)
    if on_sale:
        products_q = products_q.filter(Product.discount_price.isnot(None))
    if sort == "price_asc":
        products_q = products_q.order_by(Product.effective_price.asc())
    elif sort == "price_desc":
        products_q = products_q.order_by(Product.effective_price.desc())
    elif sort == "popular":
        products_q = products_q.order_by(Product.best_seller.desc(), Product.review_count.desc())
    elif sort == "rating":
        products_q = products_q.order_by(Product.rating.desc())
    else:
        products_q = products_q.order_by(Product.created_at.desc())
    products = products_q.all()
    return render_template("shop.html", products=products, categories=Category.query.order_by(Category.name.asc()).all(), q=q, selected_category=category, selected_sort=sort, min_price=min_price, max_price=max_price, min_rating=min_rating, in_stock=in_stock, on_sale=on_sale)

@app.get("/product/<slug>")
def product_detail(slug):
    product = Product.query.filter_by(slug=slug).first_or_404()
    reviews = Review.query.filter_by(product_id=product.id, approved=True).order_by(Review.created_at.desc()).all()
    related = Product.query.filter(Product.category_id == product.category_id, Product.id != product.id).limit(4).all() if product.category_id else []
    return render_template("product.html", product=product, reviews=reviews, related=related)

@app.post("/product/<int:product_id>/review")
def add_review(product_id):
    product = db.session.get(Product, product_id)
    if not product:
        abort(404)
    try:
        rating = int(request.form.get("rating", "5"))
        if rating < 1 or rating > 5:
            raise ValueError
    except ValueError:
        flash("Rating must be between 1 and 5.", "error")
        return redirect(url_for("product_detail", slug=product.slug))
    name = request.form.get("name", "").strip()[:120]
    comment = request.form.get("comment", "").strip()[:2000]
    if not name or not comment:
        flash("Please provide your name and review.", "error")
        return redirect(url_for("product_detail", slug=product.slug))
    db.session.add(Review(product_id=product.id, customer_name=name, rating=rating, comment=comment))
    product.review_count += 1
    product.rating = ((product.rating * (product.review_count - 1)) + rating) / product.review_count
    db.session.commit()
    flash("Thanks! Your review was submitted.", "success")
    return redirect(url_for("product_detail", slug=product.slug))

@app.get("/cart")
def cart():
    cart_data = session.get("cart", {})
    items, subtotal = [], Decimal("0")
    for pid, qty in cart_data.items():
        product = db.session.get(Product, int(pid))
        if not product:
            continue
        qty = max(1, min(int(qty), product.stock))
        price = Decimal(product.effective_price)
        line = price * qty
        subtotal += line
        items.append({"product": product, "quantity": qty, "line_total": line})
    delivery = Decimal(store_value("delivery_charge", "60"))
    if subtotal >= Decimal(store_value("free_delivery_minimum", "1500")):
        delivery = Decimal("0")
    total = subtotal + delivery
    return render_template("cart.html", items=items, subtotal=subtotal, delivery=delivery, total=total)

@app.post("/api/cart/add")
def cart_add():
    data = request.get_json(silent=True) or request.form
    product = db.session.get(Product, int(data.get("product_id", 0)))
    if not product:
        return jsonify(ok=False, message="Product not found."), 404
    if product.stock < 1:
        return jsonify(ok=False, message="This product is out of stock."), 400
    qty = max(1, int(data.get("quantity", 1)))
    cart_data = session.get("cart", {})
    current = int(cart_data.get(str(product.id), 0))
    cart_data[str(product.id)] = min(product.stock, current + qty)
    session["cart"] = cart_data
    session.modified = True
    return jsonify(ok=True, cart_count=sum(cart_data.values()), message="Added to cart.")

@app.post("/api/cart/update")
def cart_update():
    data = request.get_json(silent=True) or {}
    cart_data = session.get("cart", {})
    pid = str(data.get("product_id"))
    qty = int(data.get("quantity", 0))
    product = db.session.get(Product, int(pid))
    if not product or qty <= 0:
        cart_data.pop(pid, None)
    else:
        cart_data[pid] = min(qty, product.stock)
    session["cart"] = cart_data
    session.modified = True
    return jsonify(ok=True, cart_count=sum(cart_data.values()))

@app.post("/api/cart/remove")
def cart_remove():
    data = request.get_json(silent=True) or request.form
    pid = str(data.get("product_id"))
    cart_data = session.get("cart", {})
    cart_data.pop(pid, None)
    session["cart"] = cart_data
    session.modified = True
    return jsonify(ok=True, cart_count=sum(cart_data.values()))

@app.get("/wishlist")
def wishlist():
    rows = Wishlist.query.filter_by(visitor_key=get_visitor_key()).order_by(Wishlist.created_at.desc()).all()
    return render_template("wishlist.html", rows=rows)

@app.post("/api/wishlist/toggle")
def wishlist_toggle():
    data = request.get_json(silent=True) or request.form
    product = db.session.get(Product, int(data.get("product_id", 0)))
    if not product:
        return jsonify(ok=False, message="Product not found."), 404
    key = get_visitor_key()
    row = Wishlist.query.filter_by(visitor_key=key, product_id=product.id).first()
    if row:
        db.session.delete(row)
        active = False
    else:
        db.session.add(Wishlist(visitor_key=key, product_id=product.id))
        active = True
    db.session.commit()
    return jsonify(ok=True, active=active, wishlist_count=Wishlist.query.filter_by(visitor_key=key).count())

@app.get("/checkout")
def checkout():
    cart_data = session.get("cart", {})
    if not cart_data:
        flash("Your cart is empty.", "error")
        return redirect(url_for("shop"))
    items = []
    subtotal = Decimal("0")
    for pid, qty in cart_data.items():
        product = db.session.get(Product, int(pid))
        if product and product.stock > 0:
            qty = min(int(qty), product.stock)
            price = Decimal(product.effective_price)
            subtotal += price * qty
            items.append({"product": product, "quantity": qty, "line_total": price * qty})
    delivery = Decimal(store_value("delivery_charge", "60"))
    if subtotal >= Decimal(store_value("free_delivery_minimum", "1500")):
        delivery = Decimal("0")
    return render_template("checkout.html", items=items, subtotal=subtotal, delivery=delivery, total=subtotal+delivery)

@app.post("/checkout")
def create_order():
    cart_data = session.get("cart", {})
    if not cart_data:
        flash("Your cart is empty.", "error")
        return redirect(url_for("shop"))
    name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    email = request.form.get("email", "").strip()
    address = request.form.get("address", "").strip()
    city = request.form.get("city", "").strip()
    area = request.form.get("area", "").strip()
    postal = request.form.get("postal_code", "").strip()
    payment = request.form.get("payment_method", "cod")
    if not name or not phone or not address or not city:
        flash("Please fill all required delivery fields.", "error")
        return redirect(url_for("checkout"))
    minimum_order = Decimal(store_value("minimum_order_amount", "0") or "0")
    if minimum_order > 0:
        cart_subtotal = Decimal("0")
        for pid, qty in cart_data.items():
            product = db.session.get(Product, int(pid))
            if product and product.stock > 0:
                cart_subtotal += Decimal(product.effective_price) * min(int(qty), product.stock)
        if cart_subtotal < minimum_order:
            flash(f"Minimum order amount is {store_value('currency', '৳')}{minimum_order:,.2f}.", "error")
            return redirect(url_for("checkout"))
    if payment != "cod":
        flash("Only Cash on Delivery is active. No fake online payment is used.", "error")
        return redirect(url_for("checkout"))
    customer = Customer(name=name[:160], phone=phone[:40], email=email[:180], address=address[:500], city=city[:100], area=area[:120], postal_code=postal[:20])
    db.session.add(customer)
    db.session.flush()
    subtotal = Decimal("0")
    order_items = []
    for pid, qty in cart_data.items():
        product = db.session.get(Product, int(pid))
        if not product or product.stock < int(qty):
            db.session.rollback()
            flash(f"Insufficient stock for {product.name if product else 'a product'}.", "error")
            return redirect(url_for("cart"))
        qty = int(qty)
        price = Decimal(product.effective_price)
        subtotal += price * qty
        product.stock -= qty
        order_items.append((product, price, qty))
    delivery = Decimal(store_value("delivery_charge", "60"))
    if subtotal >= Decimal(store_value("free_delivery_minimum", "1500")):
        delivery = Decimal("0")
    order = Order(
        order_number=f"ORD-{datetime.utcnow().strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}",
        customer_id=customer.id, subtotal=subtotal, delivery_charge=delivery, total=subtotal+delivery,
        payment_method="cod", status="Pending", notes=request.form.get("notes", "").strip()[:500]
    )
    db.session.add(order)
    db.session.flush()
    for product, price, qty in order_items:
        db.session.add(OrderItem(order_id=order.id, product_id=product.id, product_name=product.name, unit_price=price, quantity=qty))
    db.session.commit()
    session["cart"] = {}
    session.modified = True
    return render_template("order_success.html", order=order)

def store_value(key, default=""):
    row = SiteSetting.query.filter_by(key=key).first()
    return row.value if row else default

@app.get("/about")
def about():
    return render_template("about.html")

@app.get("/contact")
def contact():
    return render_template("contact.html")

@app.get("/faq")
def faq():
    return render_template("faq.html")

@app.get("/robots.txt")
def robots():
    return "User-agent: *\nAllow: /\nSitemap: /sitemap.xml\n", 200, {"Content-Type": "text/plain"}

@app.get("/sitemap.xml")
def sitemap():
    urls = [url_for("home", _external=True), url_for("shop", _external=True), url_for("about", _external=True), url_for("contact", _external=True)]
    urls += [url_for("product_detail", slug=p.slug, _external=True) for p in Product.query.all()]
    body = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    body += "".join(f"<url><loc>{u}</loc></url>" for u in urls) + "</urlset>"
    return body, 200, {"Content-Type": "application/xml"}

@app.get("/uploads/<path:filename>")
def uploaded_file(filename):
    from flask import send_from_directory
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

# ---------------- Admin ----------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if current_user.is_authenticated:
        return redirect(url_for("admin_dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        admin = Admin.query.filter_by(username=username).first()
        if admin and admin.check_password(password):
            login_user(admin, remember=True)
            return redirect(url_for("admin_dashboard"))
        flash("Invalid admin username or password.", "error")
    return render_template("admin/login.html")

@app.post("/admin/logout")
@admin_required
def admin_logout():
    logout_user()
    return redirect(url_for("admin_login"))

@app.get("/admin")
@admin_required
def admin_dashboard():
    stats = {
        "products": Product.query.count(),
        "orders": Order.query.count(),
        "pending": Order.query.filter_by(status="Pending").count(),
        "completed": Order.query.filter_by(status="Delivered").count(),
        "customers": Customer.query.count(),
        "sales": sum((Decimal(o.total) for o in Order.query.filter(Order.status != "Cancelled").all()), Decimal("0")),
        "low_stock": Product.query.filter(Product.stock <= 5).count(),
    }
    recent = Order.query.order_by(Order.created_at.desc()).limit(8).all()
    top = (db.session.query(Product, db.func.coalesce(db.func.sum(OrderItem.quantity), 0).label("sold"))
           .outerjoin(OrderItem, Product.id == OrderItem.product_id)
           .outerjoin(Order, Order.id == OrderItem.order_id)
           .filter(db.or_(Order.id.is_(None), Order.status != "Cancelled"))
           .group_by(Product.id).order_by(db.desc("sold"), Product.best_seller.desc()).limit(8).all())
    return render_template("admin/dashboard.html", stats=stats, recent=recent, top=top)

@app.route("/admin/products", methods=["GET", "POST"])
@admin_required
def admin_products():
    if request.method == "POST":
        try:
            name = request.form.get("name", "").strip()
            if not name:
                raise ValueError("Product name is required.")
            product = Product(
                product_id=request.form.get("product_id", "").strip() or f"SKU-{secrets.token_hex(4).upper()}",
                name=name[:220], slug=unique_slug(Product, name), brand=request.form.get("brand", "").strip()[:120],
                price=Decimal(request.form.get("price", "0")), discount_price=(Decimal(request.form["discount_price"]) if request.form.get("discount_price") else None),
                stock=int(request.form.get("stock", 0)), short_description=request.form.get("short_description", "").strip()[:500],
                description=request.form.get("description", "").strip(), specifications=request.form.get("specifications", "").strip(),
                tags=request.form.get("tags", "").strip()[:500], featured=bool(request.form.get("featured")),
                best_seller=bool(request.form.get("best_seller")), new_arrival=bool(request.form.get("new_arrival")),
                sale_item=bool(request.form.get("sale_item")), category_id=(int(request.form["category_id"]) if request.form.get("category_id") else None)
            )
            db.session.add(product)
            db.session.flush()
            urls = [u.strip() for u in request.form.get("image_urls", "").splitlines() if u.strip()]
            for f in request.files.getlist("images"):
                saved = save_upload(f)
                if saved: urls.append(saved)
            if not urls:
                urls.append("https://images.unsplash.com/photo-1523275335684-37898b6baf30?auto=format&fit=crop&w=900&q=80")
            for i, u in enumerate(urls):
                db.session.add(ProductImage(product_id=product.id, image_url=u[:500], alt_text=product.name, sort_order=i))
            db.session.commit()
            flash("Product created successfully.", "success")
        except Exception as exc:
            db.session.rollback()
            flash(str(exc), "error")
        return redirect(url_for("admin_products"))
    products = Product.query.order_by(Product.created_at.desc()).all()
    return render_template("admin/products.html", products=products, categories=Category.query.order_by(Category.name.asc()).all())

@app.route("/admin/products/<int:product_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_product_edit(product_id):
    product = db.session.get(Product, product_id) or abort(404)
    if request.method == "POST":
        try:
            product.name = request.form.get("name", "").strip()[:220]
            product.slug = unique_slug(Product, product.name, product.id)
            product.product_id = request.form.get("product_id", "").strip()[:50]
            product.brand = request.form.get("brand", "").strip()[:120]
            product.price = Decimal(request.form.get("price", "0"))
            product.discount_price = Decimal(request.form["discount_price"]) if request.form.get("discount_price") else None
            product.stock = int(request.form.get("stock", 0))
            product.short_description = request.form.get("short_description", "").strip()[:500]
            product.description = request.form.get("description", "").strip()
            product.specifications = request.form.get("specifications", "").strip()
            product.tags = request.form.get("tags", "").strip()[:500]
            product.category_id = int(request.form["category_id"]) if request.form.get("category_id") else None
            for field in ("featured", "best_seller", "new_arrival", "sale_item"):
                setattr(product, field, bool(request.form.get(field)))
            for f in request.files.getlist("images"):
                saved = save_upload(f)
                if saved:
                    db.session.add(ProductImage(product_id=product.id, image_url=saved, alt_text=product.name, sort_order=len(product.images)))
            db.session.commit()
            flash("Product updated.", "success")
            return redirect(url_for("admin_products"))
        except Exception as exc:
            db.session.rollback()
            flash(str(exc), "error")
    return render_template("admin/product_edit.html", product=product, categories=Category.query.order_by(Category.name.asc()).all())

@app.post("/admin/products/<int:product_id>/delete")
@admin_required
def admin_product_delete(product_id):
    product = db.session.get(Product, product_id) or abort(404)
    db.session.delete(product)
    db.session.commit()
    flash("Product deleted.", "success")
    return redirect(url_for("admin_products"))

@app.route("/admin/categories", methods=["GET", "POST"])
@admin_required
def admin_categories():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if name:
            try:
                db.session.add(Category(name=name[:120], slug=unique_slug(Category, name)))
                db.session.commit()
                flash("Category added.", "success")
            except Exception:
                db.session.rollback()
                flash("Category already exists.", "error")
        return redirect(url_for("admin_categories"))
    return render_template("admin/categories.html", categories=Category.query.order_by(Category.name.asc()).all())

@app.post("/admin/categories/<int:category_id>/edit")
@admin_required
def admin_category_edit(category_id):
    category = db.session.get(Category, category_id) or abort(404)
    name = request.form.get("name", "").strip()
    if not name:
        flash("Category name is required.", "error")
    else:
        try:
            category.name = name[:120]
            category.slug = unique_slug(Category, name, category.id)
            db.session.commit(); flash("Category updated.", "success")
        except Exception:
            db.session.rollback(); flash("Category name already exists.", "error")
    return redirect(url_for("admin_categories"))

@app.post("/admin/categories/<int:category_id>/delete")
@admin_required
def admin_category_delete(category_id):
    category = db.session.get(Category, category_id) or abort(404)
    for p in category.products:
        p.category_id = None
    db.session.delete(category)
    db.session.commit()
    flash("Category deleted.", "success")
    return redirect(url_for("admin_categories"))

@app.get("/admin/orders")
@admin_required
def admin_orders():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    query = Order.query.join(Customer)
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Order.order_number.ilike(like), Customer.name.ilike(like), Customer.phone.ilike(like)))
    if status:
        query = query.filter(Order.status == status)
    orders = query.order_by(Order.created_at.desc()).all()
    return render_template("admin/orders.html", orders=orders, selected_status=status)

@app.post("/admin/orders/<int:order_id>/status")
@admin_required
def admin_order_status(order_id):
    order = db.session.get(Order, order_id) or abort(404)
    allowed = {"Pending", "Confirmed", "Processing", "Shipped", "Delivered", "Cancelled"}
    status = request.form.get("status")
    if status not in allowed:
        flash("Invalid order status.", "error")
    else:
        order.status = status
        db.session.commit()
        flash("Order status updated.", "success")
    return redirect(url_for("admin_orders"))

@app.post("/admin/orders/<int:order_id>/delete")
@admin_required
def admin_order_delete(order_id):
    order = db.session.get(Order, order_id) or abort(404)
    db.session.delete(order)
    db.session.commit()
    flash("Order deleted.", "success")
    return redirect(url_for("admin_orders"))

@app.route("/admin/ads", methods=["GET", "POST"])
@admin_required
def admin_ads():
    if request.method == "POST":
        try:
            image_url = request.form.get("image_url", "").strip()
            saved = save_upload(request.files.get("image"))
            image_url = saved or image_url
            if not image_url:
                raise ValueError("Provide an image URL or upload an image.")
            ad = Advertisement(title=request.form.get("title", "").strip()[:220], description=request.form.get("description", "").strip()[:500],
                image_url=image_url[:500], cta_text=request.form.get("cta_text", "Shop Now").strip()[:80], cta_link=request.form.get("cta_link", "/shop").strip()[:500],
                placement=request.form.get("placement", "home").strip()[:50], enabled=bool(request.form.get("enabled")))
            db.session.add(ad); db.session.commit(); flash("Advertisement created.", "success")
        except Exception as exc:
            db.session.rollback(); flash(str(exc), "error")
        return redirect(url_for("admin_ads"))
    return render_template("admin/ads.html", ads=Advertisement.query.order_by(Advertisement.created_at.desc()).all())

@app.route("/admin/ads/<int:ad_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_ad_edit(ad_id):
    ad = db.session.get(Advertisement, ad_id) or abort(404)
    if request.method == "POST":
        try:
            ad.title = request.form.get("title", "").strip()[:220]
            ad.description = request.form.get("description", "").strip()[:500]
            ad.cta_text = request.form.get("cta_text", "Shop Now").strip()[:80]
            ad.cta_link = request.form.get("cta_link", "/shop").strip()[:500]
            ad.placement = request.form.get("placement", "home").strip()[:50]
            ad.enabled = bool(request.form.get("enabled"))
            saved = save_upload(request.files.get("image"))
            if saved: ad.image_url = saved
            elif request.form.get("image_url", "").strip(): ad.image_url = request.form.get("image_url").strip()[:500]
            db.session.commit(); flash("Advertisement updated.", "success")
            return redirect(url_for("admin_ads"))
        except Exception as exc:
            db.session.rollback(); flash(str(exc), "error")
    return render_template("admin/ad_edit.html", ad=ad)

@app.post("/admin/ads/<int:ad_id>/delete")
@admin_required
def admin_ad_delete(ad_id):
    ad = db.session.get(Advertisement, ad_id) or abort(404)
    db.session.delete(ad); db.session.commit(); flash("Advertisement deleted.", "success")
    return redirect(url_for("admin_ads"))

@app.route("/admin/banners", methods=["GET", "POST"])
@admin_required
def admin_banners():
    if request.method == "POST":
        try:
            image_url = request.form.get("image_url", "").strip()
            saved = save_upload(request.files.get("image"))
            image_url = saved or image_url
            if not image_url:
                raise ValueError("Provide an image URL or upload an image.")
            banner = Banner(title=request.form.get("title", "").strip()[:220], subtitle=request.form.get("subtitle", "").strip()[:500],
                image_url=image_url[:500], button_text=request.form.get("button_text", "Shop Now").strip()[:80],
                button_link=request.form.get("button_link", "/shop").strip()[:500], enabled=bool(request.form.get("enabled")),
                sort_order=int(request.form.get("sort_order", 0)))
            db.session.add(banner); db.session.commit(); flash("Banner created.", "success")
        except Exception as exc:
            db.session.rollback(); flash(str(exc), "error")
        return redirect(url_for("admin_banners"))
    return render_template("admin/banners.html", banners=Banner.query.order_by(Banner.sort_order.asc()).all())

@app.route("/admin/banners/<int:banner_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_banner_edit(banner_id):
    banner = db.session.get(Banner, banner_id) or abort(404)
    if request.method == "POST":
        try:
            banner.title = request.form.get("title", "").strip()[:220]
            banner.subtitle = request.form.get("subtitle", "").strip()[:500]
            banner.button_text = request.form.get("button_text", "Shop Now").strip()[:80]
            banner.button_link = request.form.get("button_link", "/shop").strip()[:500]
            banner.sort_order = int(request.form.get("sort_order", 0))
            banner.enabled = bool(request.form.get("enabled"))
            saved = save_upload(request.files.get("image"))
            if saved: banner.image_url = saved
            elif request.form.get("image_url", "").strip(): banner.image_url = request.form.get("image_url").strip()[:500]
            db.session.commit(); flash("Banner updated.", "success")
            return redirect(url_for("admin_banners"))
        except Exception as exc:
            db.session.rollback(); flash(str(exc), "error")
    return render_template("admin/banner_edit.html", banner=banner)

@app.post("/admin/banners/<int:banner_id>/delete")
@admin_required
def admin_banner_delete(banner_id):
    banner = db.session.get(Banner, banner_id) or abort(404)
    db.session.delete(banner); db.session.commit(); flash("Banner deleted.", "success")
    return redirect(url_for("admin_banners"))

@app.route("/admin/settings", methods=["GET", "POST"])
@admin_required
def admin_settings():
    keys = ["store_name", "logo_url", "store_description", "phone", "email", "address", "facebook", "instagram", "youtube", "footer_text", "currency", "delivery_charge", "free_delivery_minimum", "minimum_order_amount"]
    if request.method == "POST":
        for key in keys:
            row = SiteSetting.query.filter_by(key=key).first()
            if not row:
                row = SiteSetting(key=key)
                db.session.add(row)
            row.value = request.form.get(key, "").strip()[:2000]
        db.session.commit()
        flash("Store settings saved.", "success")
        return redirect(url_for("admin_settings"))
    values = {key: store_value(key, "") for key in keys}
    return render_template("admin/settings.html", values=values)

@app.get("/admin/reviews")
@admin_required
def admin_reviews():
    reviews = Review.query.order_by(Review.created_at.desc()).all()
    return render_template("admin/reviews.html", reviews=reviews)

@app.post("/admin/reviews/<int:review_id>/delete")
@admin_required
def admin_review_delete(review_id):
    review = db.session.get(Review, review_id) or abort(404)
    db.session.delete(review); db.session.commit(); flash("Review deleted.", "success")
    return redirect(url_for("admin_reviews"))

@app.errorhandler(404)
def not_found(_):
    return render_template("error.html", code=404, message="The page or product could not be found."), 404

@app.errorhandler(413)
def too_large(_):
    return render_template("error.html", code=413, message="That upload is too large. Maximum file size is 8 MB."), 413

@app.errorhandler(500)
def server_error(_):
    db.session.rollback()
    return render_template("error.html", code=500, message="Something went wrong. Please try again."), 500

def seed():
    db.create_all()
    if not Admin.query.filter_by(username=os.environ.get("ADMIN_USERNAME", "admin")).first():
        admin = Admin(username=os.environ.get("ADMIN_USERNAME", "admin"))
        admin.set_password(os.environ.get("ADMIN_PASSWORD", "ChangeMe123!"))
        db.session.add(admin)
    if Category.query.count() == 0:
        names = ["Electronics", "Fashion", "Home & Living", "Beauty", "Accessories"]
        for n in names:
            db.session.add(Category(name=n, slug=slugify(n)))
        db.session.commit()
    if Product.query.count() == 0:
        cats = {c.name: c for c in Category.query.all()}
        demo = [
            ("AeroWatch X1", "Electronics", 6990, 5490, 18, "Smart everyday watch with a premium metal finish.", "A stylish smartwatch for daily fitness, calls and notifications.", "Display: 1.8 inch; Battery: 7 days; Water resistance: IP68", "watch,smartwatch", True, True, True, True, "https://images.unsplash.com/photo-1523275335684-37898b6baf30?auto=format&fit=crop&w=1000&q=85"),
            ("Urban Runner Pro", "Fashion", 3490, 2890, 25, "Lightweight sneakers built for everyday comfort.", "Comfortable street sneakers with breathable mesh and durable rubber sole.", "Upper: Mesh; Sole: Rubber; Sizes: 39-44", "shoes,sneakers", True, True, True, True, "https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=1000&q=85"),
            ("Minimal Desk Lamp", "Home & Living", 2490, None, 12, "Warm LED desk lamp with a clean silhouette.", "A modern lamp for desks, reading corners and workspaces.", "LED: 12W; Color temperature: 3000K; USB-C", "lamp,desk,home", False, False, True, False, "https://images.unsplash.com/photo-1507473885765-e6ed057f782c?auto=format&fit=crop&w=1000&q=85"),
            ("PureGlow Skincare Set", "Beauty", 1890, 1590, 30, "Simple daily skincare essentials.", "A gentle routine set for a clean, hydrated feel.", "Includes: cleanser, serum, moisturizer", "beauty,skincare", True, False, True, True, "https://images.unsplash.com/photo-1556228578-8c89e6adf883?auto=format&fit=crop&w=1000&q=85"),
            ("Everyday Leather Wallet", "Accessories", 1290, 990, 40, "Slim wallet with multiple card slots.", "Minimal genuine-leather style wallet for everyday carry.", "Material: Leather; Slots: 8", "wallet,leather", False, True, False, True, "https://images.unsplash.com/photo-1627123424574-724758594e93?auto=format&fit=crop&w=1000&q=85"),
            ("NoiseCancel Headphones", "Electronics", 5990, 4990, 10, "Wireless over-ear headphones with active noise control.", "Long-battery wireless headphones for music and work.", "Battery: 35h; Bluetooth 5.3; USB-C", "headphones,audio", True, True, True, True, "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&w=1000&q=85"),
        ]
        for row in demo:
            name, cat, price, disc, stock, short, desc, specs, tags, feat, best, new, sale, image = row
            p = Product(product_id=f"SKU-{secrets.token_hex(4).upper()}", name=name, slug=unique_slug(Product, name), brand="NovaStore",
                        price=price, discount_price=disc, stock=stock, short_description=short, description=desc,
                        specifications=specs, tags=tags, featured=feat, best_seller=best, new_arrival=new, sale_item=sale,
                        category_id=cats[cat].id, rating=4.7, review_count=0)
            db.session.add(p); db.session.flush()
            db.session.add(ProductImage(product_id=p.id, image_url=image, alt_text=name, sort_order=0))
    defaults = {
        "store_name": "NovaStore", "logo_url": "", "store_description": "A modern online store for quality products.",
        "phone": "+880 1XXXXXXXXX", "email": "hello@example.com", "address": "Dhaka, Bangladesh",
        "facebook": "#", "instagram": "#", "youtube": "#", "footer_text": "Quality products. Simple shopping. Fast delivery.",
        "currency": "৳", "delivery_charge": "60", "free_delivery_minimum": "1500", "minimum_order_amount": "0"
    }
    for k, v in defaults.items():
        if not SiteSetting.query.filter_by(key=k).first():
            db.session.add(SiteSetting(key=k, value=v))
    if Banner.query.count() == 0:
        db.session.add(Banner(title="Upgrade your everyday", subtitle="Premium products, honest prices and easy Cash on Delivery.", image_url="https://images.unsplash.com/photo-1441986300917-64674bd600d8?auto=format&fit=crop&w=1800&q=85", button_text="Shop Deals", button_link="/shop", enabled=True, sort_order=1))
        db.session.add(Banner(title="Fresh arrivals are here", subtitle="Discover new picks selected for modern living.", image_url="https://images.unsplash.com/photo-1441984904996-e0b6ba687e04?auto=format&fit=crop&w=1800&q=85", button_text="Explore New", button_link="/shop?sort=newest", enabled=True, sort_order=2))
    db.session.commit()

with app.app_context():
    db.create_all()
    seed()