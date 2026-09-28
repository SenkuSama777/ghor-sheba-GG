from datetime import datetime

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    password_hash = db.Column(db.String(255), nullable=False)

    # 'customer' or 'provider'. Admin is a boolean flag layered on top.
    role = db.Column(db.String(20), nullable=False, default="customer")
    is_admin = db.Column(db.Boolean, default=False)

    # Where the customer actually is right now — many users of this platform
    # are outside Tripura (other states or abroad) but need work done there.
    based_in_tripura = db.Column(db.Boolean, default=True)
    current_location = db.Column(db.String(120))  # e.g. "Bengaluru", "Dubai" if away

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    provider_profile = db.relationship(
        "ProviderProfile", backref="user", uselist=False, cascade="all, delete-orphan"
    )
    requests = db.relationship(
        "ServiceRequest", backref="customer", lazy=True, cascade="all, delete-orphan"
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class ProviderProfile(db.Model):
    __tablename__ = "provider_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    business_name = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(50), nullable=False)  # matches Config.CATEGORIES keys
    district = db.Column(db.String(50), nullable=False)
    address = db.Column(db.String(255))
    years_experience = db.Column(db.Integer, default=0)
    description = db.Column(db.Text)
    # What they charge just to come look at the job, before any work is
    # agreed — common practice for trades like plumbing/electrical/carpentry.
    # NULL means "not applicable / ask directly" (e.g. materials suppliers).
    visit_fee = db.Column(db.Integer)

    verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    quotes = db.relationship(
        "Quote", backref="provider", lazy=True, cascade="all, delete-orphan"
    )
    reviews = db.relationship(
        "Review", backref="provider", lazy=True, cascade="all, delete-orphan"
    )

    @property
    def average_rating(self):
        if not self.reviews:
            return None
        return round(sum(r.rating for r in self.reviews) / len(self.reviews), 1)

    @property
    def review_count(self):
        return len(self.reviews)


class ServiceRequest(db.Model):
    __tablename__ = "service_requests"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    category = db.Column(db.String(50), nullable=False)
    district = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    budget_range = db.Column(db.String(50))

    # True when the customer submitting this can't be on-site to supervise
    # (out of state / abroad) and needs extra hand-holding: photos, video
    # calls, a trusted point of contact, etc.
    remote_client = db.Column(db.Boolean, default=False)
    site_contact_name = db.Column(db.String(120))  # local point of contact, if any
    site_contact_phone = db.Column(db.String(20))

    status = db.Column(db.String(20), default="open")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    quotes = db.relationship(
        "Quote", backref="request", lazy=True, cascade="all, delete-orphan"
    )


class Quote(db.Model):
    __tablename__ = "quotes"

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("service_requests.id"), nullable=False)
    provider_id = db.Column(db.Integer, db.ForeignKey("provider_profiles.id"), nullable=False)

    message = db.Column(db.Text, nullable=False)
    price_estimate = db.Column(db.String(50))
    status = db.Column(db.String(20), default="pending")  # pending, accepted, declined
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Review(db.Model):
    __tablename__ = "reviews"

    id = db.Column(db.Integer, primary_key=True)
    provider_id = db.Column(db.Integer, db.ForeignKey("provider_profiles.id"), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    request_id = db.Column(db.Integer, db.ForeignKey("service_requests.id"))

    rating = db.Column(db.Integer, nullable=False)  # 1-5
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("service_requests.id"), nullable=False)
    quote_id = db.Column(db.Integer, db.ForeignKey("quotes.id"), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    provider_id = db.Column(db.Integer, db.ForeignKey("provider_profiles.id"), nullable=False)

    amount = db.Column(db.Numeric(10, 2), nullable=False)  # rupees
    currency = db.Column(db.String(10), default="INR")

    razorpay_order_id = db.Column(db.String(64), unique=True)
    razorpay_payment_id = db.Column(db.String(64))
    razorpay_signature = db.Column(db.String(128))

    status = db.Column(db.String(20), default="created")  # created, paid, failed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    request = db.relationship("ServiceRequest", backref="payments")
    quote = db.relationship("Quote", backref=db.backref("payments", cascade="all, delete-orphan"))
