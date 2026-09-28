"""
Seed the database with demo providers across every category and district, so
the app doesn't look empty while you're testing the browse/filter/admin
flows.

Usage:
    python seed_demo_data.py

Safe to run more than once — it looks up each demo account by email first
and skips it if it already exists, rather than creating duplicates. All
demo provider accounts share the password below so you can log in as any
of them.
"""
from app import create_app
from models import db, User, ProviderProfile, Review

DEMO_PASSWORD = "Demo@1234"

# (business_name, category, district, years_experience, verified, description, visit_fee)
DEMO_PROVIDERS = [
    ("Tripura Interiors & Decor", "interior_design", "West Tripura", 6, True,
     "Full-service interior design and home decor — living rooms, kitchens, and "
     "custom furnishing for flats and independent houses.", 500),
    ("Hills Home Styling", "interior_design", "Khowai", 2, False,
     "Budget-friendly interior styling and decor for small flats and rentals.", None),

    ("Agartala Builders Co.", "construction", "West Tripura", 12, True,
     "Residential and small commercial construction — new builds, extensions, "
     "and renovations across Agartala.", 1000),
    ("Unakoti Construction Works", "construction", "Unakoti", 8, True,
     "General contracting for houses and boundary walls, with an in-house mason team.", 500),

    ("Tripura Building Materials", "raw_materials", "Sepahijala", 15, True,
     "Wholesale bricks, cement, sand, and steel — delivery arranged across nearby districts.", None),
    ("Gomati Bricks & Cement", "raw_materials", "Gomati", 3, False,
     "Local supplier of bricks, cement, and aggregate for small builds.", None),

    ("QuickFix Plumbing Services", "plumbing", "West Tripura", 5, True,
     "Leak repairs, bathroom fittings, and full plumbing lines for new construction.", 150),
    ("South Tripura Plumbers", "plumbing", "South Tripura", 1, False,
     "Plumbing repairs and installation for homes in and around Udaipur.", 100),

    ("Master Carpenters Guild", "carpentry", "Dhalai", 10, True,
     "Custom furniture, wardrobes, and door/window frames in local and imported wood.", 200),
    ("Khowai Wood Works", "carpentry", "Khowai", 4, False,
     "Furniture repair and small carpentry jobs at reasonable rates.", 100),

    ("Bright Spark Electricals", "electrical", "West Tripura", 7, True,
     "House wiring, fittings, and inverter/solar setup for homes and small shops.", 150),
    ("North Tripura Electric Co.", "electrical", "North Tripura", 9, True,
     "Licensed electrical contracting — rewiring, panel upgrades, and repairs.", 200),
]

# A few reviews on the verified providers so ratings show up in listings.
DEMO_REVIEWS = [
    ("Tripura Interiors & Decor", 5, "Redid our living room while we were still abroad — sent photos at every step."),
    ("Tripura Interiors & Decor", 4, "Good work, took a little longer than quoted but the finish was worth it."),
    ("Agartala Builders Co.", 5, "Reliable and finished the extension on schedule."),
    ("Tripura Building Materials", 4, "Delivered on time, quality bricks."),
    ("QuickFix Plumbing Services", 5, "Fixed a persistent leak same day."),
    ("Master Carpenters Guild", 5, "Beautiful wardrobe, exactly as discussed."),
    ("Bright Spark Electricals", 4, "Rewired the whole flat safely, explained everything clearly."),
    ("North Tripura Electric Co.", 5, "Very professional, fair pricing."),
]


def get_or_create_user(name, email, phone, role):
    user = User.query.filter_by(email=email).first()
    if user:
        return user, False
    user = User(name=name, email=email, phone=phone, role=role, based_in_tripura=True)
    user.set_password(DEMO_PASSWORD)
    db.session.add(user)
    db.session.flush()  # get an id without a full commit yet
    return user, True


def seed():
    created_count = 0

    # One demo customer, used as the author of the seeded reviews.
    reviewer, _ = get_or_create_user(
        "Demo Customer", "demo.customer@example.com", "9000000000", "customer"
    )

    business_to_profile = {}

    for i, (name, category, district, years, verified, description, visit_fee) in enumerate(DEMO_PROVIDERS, start=1):
        email = f"demo.provider{i}@example.com"
        user, is_new_user = get_or_create_user(name, email, f"90000000{i:02d}", "provider")

        profile = ProviderProfile.query.filter_by(user_id=user.id).first()
        if not profile:
            profile = ProviderProfile(
                user_id=user.id,
                business_name=name,
                category=category,
                district=district,
                years_experience=years,
                description=description,
                verified=verified,
                visit_fee=visit_fee,
            )
            db.session.add(profile)
            db.session.flush()
            created_count += 1
        business_to_profile[name] = profile

    for business_name, rating, comment in DEMO_REVIEWS:
        profile = business_to_profile.get(business_name)
        if not profile:
            continue
        exists = Review.query.filter_by(
            provider_id=profile.id, customer_id=reviewer.id, comment=comment
        ).first()
        if not exists:
            db.session.add(Review(
                provider_id=profile.id, customer_id=reviewer.id, rating=rating, comment=comment
            ))

    db.session.commit()
    print(f"Done. {created_count} new provider profile(s) created (existing ones left as-is).")
    print(f"All demo provider accounts use the password: {DEMO_PASSWORD}")
    print("Example login: demo.provider1@example.com")


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        seed()
