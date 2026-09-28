import logging
import os
from decimal import Decimal, InvalidOperation
from functools import wraps

from flask import Flask, render_template, redirect, url_for, request, flash, abort
from flask_login import (
    LoginManager,
    login_user,
    logout_user,
    login_required,
    current_user,
)
from flask_wtf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config, IS_PRODUCTION
from models import db, User, ProviderProfile, ServiceRequest, Quote, Review, Payment

try:
    import razorpay
except ImportError:  # optional dependency — payments just stay disabled without it
    razorpay = None

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.login_message = "Please sign in to continue."
csrf = CSRFProtect()


def create_app():
    # Vercel serves anything in /public/** directly from its CDN and
    # recommends against relying on Flask's own static_folder there — so we
    # point Flask at the same /public directory with an empty URL prefix.
    # url_for('static', filename='css/style.css') then resolves to
    # /css/style.css both locally and once deployed.
    app = Flask(__name__, static_folder="public", static_url_path="")
    app.config.from_object(Config)

    # Vercel (like most PaaS) puts the app behind a reverse proxy — without
    # this, request.is_secure and url_for(..., _external=True) get the
    # scheme/host wrong, which breaks secure cookies and redirects.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    app.logger.setLevel(logging.INFO if IS_PRODUCTION else logging.DEBUG)
    if not Config.PAYMENTS_ENABLED:
        app.logger.warning(
            "RAZORPAY_KEY_ID/RAZORPAY_KEY_SECRET not set — online payments are disabled; "
            "customers will see a 'payments not configured' message instead of checkout."
        )

    with app.app_context():
        # Safe to call on every cold start: it only creates tables that
        # don't exist yet. For schema changes down the line, switch to
        # Flask-Migrate rather than relying on this.
        db.create_all()

    register_routes(app)
    register_security_headers(app)
    return app


def register_security_headers(app):
    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if IS_PRODUCTION:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def _parse_visit_fee(raw):
    """Blank/zero/invalid all mean 'no visit fee' rather than an error —
    this field is optional (e.g. materials suppliers don't have one)."""
    if raw is None or not str(raw).strip():
        return None
    try:
        fee = int(str(raw).replace(",", "").strip())
    except ValueError:
        return None
    return fee if fee > 0 else None


def provider_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != "provider":
            abort(403)
        return f(*args, **kwargs)

    return wrapped


def admin_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)

    return wrapped


def register_routes(app):

    @app.context_processor
    def inject_globals():
        return {
            "categories": Config.CATEGORIES,
            "districts": Config.DISTRICTS,
            "category_label": dict(Config.CATEGORIES),
            "category_color": Config.CATEGORY_COLORS,
            "category_icon": Config.CATEGORY_ICONS,
            "payments_enabled": Config.PAYMENTS_ENABLED,
        }

    # ---------- Ops ----------

    @app.route("/healthz")
    def healthz():
        return {"status": "ok"}, 200

    # ---------- Public pages ----------

    @app.route("/")
    def home():
        featured = (
            ProviderProfile.query.filter_by(verified=True)
            .order_by(ProviderProfile.created_at.desc())
            .limit(6)
            .all()
        )
        return render_template("index.html", featured=featured)

    @app.route("/providers")
    def providers():
        category = request.args.get("category", "")
        district = request.args.get("district", "")

        query = ProviderProfile.query
        if category:
            query = query.filter_by(category=category)
        if district:
            query = query.filter_by(district=district)

        results = query.order_by(ProviderProfile.verified.desc(), ProviderProfile.created_at.desc()).all()
        return render_template(
            "providers.html", results=results, selected_category=category, selected_district=district
        )

    @app.route("/providers/<int:provider_id>")
    def provider_detail(provider_id):
        provider = ProviderProfile.query.get_or_404(provider_id)
        reviews = (
            Review.query.filter_by(provider_id=provider.id)
            .order_by(Review.created_at.desc())
            .all()
        )
        return render_template("provider_detail.html", provider=provider, reviews=reviews)

    # ---------- Auth ----------

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            name = request.form["name"].strip()
            email = request.form["email"].strip().lower()
            phone = request.form.get("phone", "").strip()
            password = request.form["password"]
            role = request.form.get("role", "customer")
            based_in_tripura = request.form.get("based_in_tripura") == "yes"
            current_location = request.form.get("current_location", "").strip()

            if User.query.filter_by(email=email).first():
                flash("An account with that email already exists.", "error")
                return render_template("register.html")

            user = User(
                name=name,
                email=email,
                phone=phone,
                role=role,
                based_in_tripura=based_in_tripura,
                current_location=current_location if not based_in_tripura else None,
            )
            user.set_password(password)
            db.session.add(user)
            db.session.commit()

            if role == "provider":
                profile = ProviderProfile(
                    user_id=user.id,
                    business_name=request.form.get("business_name", name),
                    category=request.form.get("category", Config.CATEGORIES[0][0]),
                    district=request.form.get("district", Config.DISTRICTS[0]),
                    years_experience=int(request.form.get("years_experience") or 0),
                    description=request.form.get("description", ""),
                    visit_fee=_parse_visit_fee(request.form.get("visit_fee")),
                )
                db.session.add(profile)
                db.session.commit()

            login_user(user)
            flash("Welcome — your account is set up.", "success")
            return redirect(url_for("dashboard"))

        return render_template("register.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form["email"].strip().lower()
            password = request.form["password"]
            user = User.query.filter_by(email=email).first()
            if user and user.check_password(password):
                login_user(user)
                return redirect(url_for("dashboard"))
            flash("Incorrect email or password.", "error")
        return render_template("login.html")

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("home"))

    # ---------- Customer flow ----------

    @app.route("/request-service", methods=["GET", "POST"])
    @login_required
    def request_service():
        if request.method == "POST":
            req = ServiceRequest(
                customer_id=current_user.id,
                category=request.form["category"],
                district=request.form["district"],
                title=request.form["title"].strip(),
                description=request.form["description"].strip(),
                budget_range=request.form.get("budget_range", "").strip(),
                remote_client=request.form.get("remote_client") == "yes",
                site_contact_name=request.form.get("site_contact_name", "").strip(),
                site_contact_phone=request.form.get("site_contact_phone", "").strip(),
            )
            db.session.add(req)
            db.session.commit()
            flash("Your request is live. Verified providers in that district will send quotes.", "success")
            return redirect(url_for("dashboard"))

        return render_template("request_service.html")

    @app.route("/requests/<int:request_id>/accept/<int:quote_id>", methods=["POST"])
    @login_required
    def accept_quote(request_id, quote_id):
        req = ServiceRequest.query.get_or_404(request_id)
        if req.customer_id != current_user.id:
            abort(403)
        quote = Quote.query.get_or_404(quote_id)
        quote.status = "accepted"
        req.status = "in_progress"
        db.session.commit()
        flash("Quote accepted. The provider has been notified.", "success")
        return redirect(url_for("dashboard"))

    @app.route("/requests/<int:request_id>/complete", methods=["POST"])
    @login_required
    def complete_request(request_id):
        req = ServiceRequest.query.get_or_404(request_id)
        if req.customer_id != current_user.id:
            abort(403)
        req.status = "completed"
        db.session.commit()
        flash("Marked as completed. You can leave a review from your dashboard.", "success")
        return redirect(url_for("dashboard"))

    @app.route("/requests/<int:request_id>/review", methods=["POST"])
    @login_required
    def leave_review(request_id):
        req = ServiceRequest.query.get_or_404(request_id)
        if req.customer_id != current_user.id:
            abort(403)
        accepted_quote = next((q for q in req.quotes if q.status == "accepted"), None)
        if not accepted_quote:
            flash("No accepted provider on this request yet.", "error")
            return redirect(url_for("dashboard"))

        review = Review(
            provider_id=accepted_quote.provider_id,
            customer_id=current_user.id,
            request_id=req.id,
            rating=int(request.form["rating"]),
            comment=request.form.get("comment", "").strip(),
        )
        db.session.add(review)
        db.session.commit()
        flash("Thanks — your review has been posted.", "success")
        return redirect(url_for("dashboard"))

    # ---------- Payments ----------

    def _parse_amount(raw):
        try:
            amount = Decimal(str(raw).replace(",", "").strip())
        except (InvalidOperation, TypeError):
            return None
        if amount <= 0:
            return None
        return amount

    @app.route("/requests/<int:request_id>/pay", methods=["GET", "POST"])
    @login_required
    def pay_request(request_id):
        req = ServiceRequest.query.get_or_404(request_id)
        if req.customer_id != current_user.id:
            abort(403)

        accepted_quote = next((q for q in req.quotes if q.status == "accepted"), None)
        if not accepted_quote:
            flash("Accept a quote before paying.", "error")
            return redirect(url_for("dashboard"))

        existing_paid = Payment.query.filter_by(request_id=req.id, status="paid").first()
        pending_payment = Payment.query.filter_by(request_id=req.id, status="created").order_by(
            Payment.created_at.desc()
        ).first()

        if not Config.PAYMENTS_ENABLED or razorpay is None:
            return render_template(
                "payment.html", req=req, quote=accepted_quote, existing_paid=existing_paid,
                payment=None, gateway_configured=False,
            )

        if request.method == "POST" and not existing_paid:
            amount = _parse_amount(request.form.get("amount"))
            if not amount:
                flash("Enter a valid amount to pay.", "error")
                return redirect(url_for("pay_request", request_id=req.id))

            client = razorpay.Client(auth=(Config.RAZORPAY_KEY_ID, Config.RAZORPAY_KEY_SECRET))
            order = client.order.create({
                "amount": int(amount * 100),  # Razorpay wants paise
                "currency": "INR",
                "receipt": f"req{req.id}-{current_user.id}",
                "payment_capture": 1,
            })

            payment = Payment(
                request_id=req.id,
                quote_id=accepted_quote.id,
                customer_id=current_user.id,
                provider_id=accepted_quote.provider_id,
                amount=amount,
                razorpay_order_id=order["id"],
                status="created",
            )
            db.session.add(payment)
            db.session.commit()
            pending_payment = payment

        suggested_amount = None
        try:
            suggested_amount = _parse_amount(
                "".join(ch for ch in (accepted_quote.price_estimate or "") if ch.isdigit() or ch == ".")
            )
        except Exception:
            suggested_amount = None

        return render_template(
            "payment.html",
            req=req,
            quote=accepted_quote,
            existing_paid=existing_paid,
            payment=pending_payment,
            gateway_configured=True,
            razorpay_key_id=Config.RAZORPAY_KEY_ID,
            suggested_amount=suggested_amount,
        )

    @app.route("/payment/verify", methods=["POST"])
    @login_required
    def verify_payment():
        order_id = request.form.get("razorpay_order_id")
        payment_id = request.form.get("razorpay_payment_id")
        signature = request.form.get("razorpay_signature")

        payment = Payment.query.filter_by(razorpay_order_id=order_id).first_or_404()
        if payment.customer_id != current_user.id:
            abort(403)

        if razorpay is None or not Config.PAYMENTS_ENABLED:
            abort(400)

        client = razorpay.Client(auth=(Config.RAZORPAY_KEY_ID, Config.RAZORPAY_KEY_SECRET))
        try:
            client.utility.verify_payment_signature({
                "razorpay_order_id": order_id,
                "razorpay_payment_id": payment_id,
                "razorpay_signature": signature,
            })
        except razorpay.errors.SignatureVerificationError:
            payment.status = "failed"
            db.session.commit()
            flash("Payment verification failed. If money was deducted, it will be refunded automatically.", "error")
            return redirect(url_for("pay_request", request_id=payment.request_id))

        payment.status = "paid"
        payment.razorpay_payment_id = payment_id
        payment.razorpay_signature = signature
        db.session.commit()
        flash("Payment received — thank you.", "success")
        return redirect(url_for("dashboard"))

    # ---------- Provider flow ----------

    @app.route("/requests/<int:request_id>/quote", methods=["POST"])
    @login_required
    @provider_required
    def submit_quote(request_id):
        req = ServiceRequest.query.get_or_404(request_id)
        profile = current_user.provider_profile
        quote = Quote(
            request_id=req.id,
            provider_id=profile.id,
            message=request.form["message"].strip(),
            price_estimate=request.form.get("price_estimate", "").strip(),
        )
        if req.status == "open":
            req.status = "quoted"
        db.session.add(quote)
        db.session.commit()
        flash("Quote sent to the customer.", "success")
        return redirect(url_for("dashboard"))

    @app.route("/provider/profile", methods=["GET", "POST"])
    @login_required
    @provider_required
    def edit_provider_profile():
        profile = current_user.provider_profile
        if request.method == "POST":
            profile.business_name = request.form["business_name"].strip()
            profile.category = request.form["category"]
            profile.district = request.form["district"]
            profile.address = request.form.get("address", "").strip()
            profile.years_experience = int(request.form.get("years_experience") or 0)
            profile.description = request.form.get("description", "").strip()
            profile.visit_fee = _parse_visit_fee(request.form.get("visit_fee"))
            db.session.commit()
            flash("Profile updated.", "success")
            return redirect(url_for("dashboard"))
        return render_template("edit_provider_profile.html", profile=profile)

    # ---------- Dashboard ----------

    @app.route("/dashboard")
    @login_required
    def dashboard():
        if current_user.role == "provider":
            profile = current_user.provider_profile
            matching_requests = (
                ServiceRequest.query.filter_by(category=profile.category, district=profile.district)
                .filter(ServiceRequest.status.in_(["open", "quoted"]))
                .order_by(ServiceRequest.created_at.desc())
                .all()
            )
            my_quotes = Quote.query.filter_by(provider_id=profile.id).all()
            quoted_request_ids = {q.request_id for q in my_quotes}
            return render_template(
                "dashboard_provider.html",
                profile=profile,
                matching_requests=matching_requests,
                quoted_request_ids=quoted_request_ids,
            )
        else:
            my_requests = (
                ServiceRequest.query.filter_by(customer_id=current_user.id)
                .order_by(ServiceRequest.created_at.desc())
                .all()
            )
            return render_template("dashboard_customer.html", my_requests=my_requests)

    # ---------- Admin ----------

    @app.route("/admin")
    @login_required
    @admin_required
    def admin_panel():
        pending = ProviderProfile.query.order_by(ProviderProfile.created_at.desc()).filter_by(verified=False).all()
        verified = ProviderProfile.query.order_by(ProviderProfile.created_at.desc()).filter_by(verified=True).all()
        stats = {
            "total_providers": len(pending) + len(verified),
            "verified_count": len(verified),
            "pending_count": len(pending),
            "total_customers": User.query.filter_by(role="customer").count(),
            "total_requests": ServiceRequest.query.count(),
            "total_payments": Payment.query.filter_by(status="paid").count(),
        }
        return render_template("admin.html", pending=pending, verified=verified, stats=stats)

    @app.route("/admin/verify/<int:provider_id>", methods=["POST"])
    @login_required
    @admin_required
    def verify_provider(provider_id):
        profile = ProviderProfile.query.get_or_404(provider_id)
        profile.verified = True
        db.session.commit()
        flash(f"{profile.business_name} is now verified.", "success")
        return redirect(url_for("admin_panel"))

    @app.route("/admin/providers/<int:provider_id>/delete", methods=["POST"])
    @login_required
    @admin_required
    def delete_provider(provider_id):
        profile = ProviderProfile.query.get_or_404(provider_id)
        name = profile.business_name
        # Deleting the underlying account (rather than just the listing)
        # cascades cleanly through their quotes, payments and reviews —
        # see the cascade config on User.provider_profile in models.py.
        db.session.delete(profile.user)
        db.session.commit()
        flash(f"{name} and all of their listings have been removed.", "success")
        return redirect(url_for("admin_panel"))

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("error.html", code=403, message="You don't have access to that page."), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("error.html", code=404, message="That page doesn't exist."), 404

    @app.errorhandler(500)
    def server_error(e):
        db.session.rollback()
        app.logger.exception("Unhandled server error")
        return render_template(
            "error.html", code=500, message="Something went wrong on our end. Please try again."
        ), 500


app = create_app()

if __name__ == "__main__":
    app.run(debug=not IS_PRODUCTION, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
