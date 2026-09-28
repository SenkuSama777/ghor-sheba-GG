import os

from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))  # no-op if the file doesn't exist

# Running on Vercel sets this automatically — used to tell dev and prod apart
# without a separate flag to remember to set.
IS_VERCEL = os.environ.get("VERCEL") == "1"
IS_PRODUCTION = IS_VERCEL or os.environ.get("FLASK_ENV") == "production"


def _database_url():
    """
    Resolve the DB connection string.

    Vercel's filesystem is read-only and ephemeral outside /tmp, so SQLite
    cannot be used there — data would silently vanish between invocations.
    In production we require DATABASE_URL (a Postgres URL from Neon,
    Supabase, Vercel Postgres, etc). Locally, SQLite is fine for development
    and is used automatically if DATABASE_URL isn't set.
    """
    url = os.environ.get("DATABASE_URL")

    if not url:
        if IS_PRODUCTION:
            raise RuntimeError(
                "DATABASE_URL is not set. On Vercel, SQLite cannot be used "
                "(the filesystem is read-only/ephemeral) — set DATABASE_URL "
                "to a Postgres connection string (e.g. from Neon or Supabase) "
                "in your Vercel project's Environment Variables."
            )
        return f"sqlite:///{os.path.join(BASE_DIR, 'tripura_services.db')}"

    # Some providers hand out "postgres://" URLs; SQLAlchemy 1.4+/2.x wants
    # "postgresql://".
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    if not SECRET_KEY:
        if IS_PRODUCTION:
            raise RuntimeError(
                "SECRET_KEY is not set. Set it in your Vercel project's "
                "Environment Variables (generate one with: "
                "python -c \"import secrets; print(secrets.token_hex(32))\")."
            )
        SECRET_KEY = "dev-only-secret-do-not-use-in-production"

    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Serverless functions are short-lived — pool_pre_ping avoids handing out
    # dead connections after a cold start; pool_recycle keeps connections
    # from going stale between invocations. SQLite ignores these options.
    if SQLALCHEMY_DATABASE_URI.startswith("postgresql"):
        SQLALCHEMY_ENGINE_OPTIONS = {
            "pool_pre_ping": True,
            "pool_recycle": 280,
        }

    # Cookie security — only force HTTPS-only cookies in production so local
    # http://localhost dev still works without HTTPS.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = IS_PRODUCTION

    WTF_CSRF_TIME_LIMIT = None  # don't expire CSRF tokens on long-lived forms

    # Fixed reference data for the platform
    DISTRICTS = [
        "West Tripura",
        "Sepahijala",
        "Khowai",
        "Gomati",
        "South Tripura",
        "Dhalai",
        "Unakoti",
        "North Tripura",
    ]

    CATEGORIES = [
        ("interior_design", "Interior Design & Home Decor"),
        ("construction", "Construction & Renovation"),
        ("raw_materials", "Raw Materials Supply"),
        ("plumbing", "Plumbing"),
        ("carpentry", "Carpentry"),
        ("electrical", "Electrical"),
    ]

    # One accent colour per category, used for icon badges, borders and
    # status chips so each trade is visually distinct at a glance.
    CATEGORY_COLORS = {
        "interior_design": "#A6577A",
        "construction": "#C97A2B",
        "raw_materials": "#6B6259",
        "plumbing": "#2E7D8C",
        "carpentry": "#8C5A2B",
        "electrical": "#B8901F",
    }

    # Minimal inline-SVG line icons (24x24, stroke="currentColor" unless
    # noted) — kept here rather than as image files so no extra requests
    # are needed and the colour above can tint them via CSS `color`.
    CATEGORY_ICONS = {
        "interior_design": (
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">'
            '<rect x="3" y="3" width="11" height="6" rx="1.5"/>'
            '<rect x="7.5" y="9" width="2" height="8"/>'
            '<rect x="5" y="17" width="7" height="4" rx="1"/></svg>'
        ),
        "construction": (
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">'
            '<path d="M4 21V9l8-5 8 5v12"/><path d="M9 21v-6h6v6"/></svg>'
        ),
        "raw_materials": (
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6">'
            '<rect x="3" y="4" width="7" height="4"/><rect x="12" y="4" width="9" height="4"/>'
            '<rect x="3" y="10" width="9" height="4"/><rect x="14" y="10" width="7" height="4"/>'
            '<rect x="3" y="16" width="7" height="4"/><rect x="12" y="16" width="9" height="4"/></svg>'
        ),
        "plumbing": (
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">'
            '<path d="M7 3v4M17 3v4M7 7h10a2 2 0 0 1 2 2v1H5V9a2 2 0 0 1 2-2Z"/>'
            '<path d="M12 13c0 2-2 2.5-2 4.5A2 2 0 0 0 12 20a2 2 0 0 0 2-2.5C14 15.5 12 15 12 13Z"/></svg>'
        ),
        "carpentry": (
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">'
            '<path d="M3 17 17 3l4 4L7 21z"/><path d="M13 7l4 4"/></svg>'
        ),
        "electrical": (
            '<svg viewBox="0 0 24 24" fill="currentColor" stroke="none">'
            '<path d="M13 2 3 14h7l-1 8 11-14h-7z"/></svg>'
        ),
    }

    REQUEST_STATUSES = ["open", "quoted", "in_progress", "completed", "cancelled"]

    # Payments (Razorpay — the standard gateway for INR/UPI in India).
    # Optional: the app runs fine without these set, it just shows a
    # "payments not configured" message instead of a checkout button.
    RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID")
    RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET")
    PAYMENTS_ENABLED = bool(RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET)
