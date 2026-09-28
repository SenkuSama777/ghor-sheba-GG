# Ghor Sheba — Tripura Service Provider Network

A Flask web app that lets anyone in Tripura get trades work done online —
whether they're local, new to the state, or living elsewhere but still have
property there. It connects customers with local service providers across
six colour-coded categories:

- 🟣 Interior Design & Home Decor
- 🟠 Construction & Renovation
- ⚪ Raw Materials Supply
- 🔵 Plumbing
- 🟤 Carpentry
- 🟡 Electrical

## How it works

1. **Customers** register, then post a service request (category, district,
   description, budget, and whether they're physically on-site or need
   remote coordination through a local contact).
2. **Providers** register with a business profile (category + district they
   serve), see matching open requests on their dashboard, and send quotes.
3. The customer accepts a quote, **pays online** through Razorpay (or
   arranges payment directly if the gateway isn't configured), marks the
   job complete, and leaves a review.
4. **Admins** verify provider accounts from `/admin` so customers can tell
   genuine, checked businesses apart from new/unverified sign-ups.

The 8 districts of Tripura (West Tripura, Sepahijala, Khowai, Gomati, South
Tripura, Dhalai, Unakoti, North Tripura) are built in as the matching unit
between requests and providers — edit the list in `config.py` if you want
finer-grained areas (block/tehsil level) later.

## Design

Each of the six categories has its own accent colour and icon (set in
`config.py` → `CATEGORY_COLORS` / `CATEGORY_ICONS`), used consistently for
category cards, chips on provider/request cards, and the **Services**
sidebar that sits on the right of the homepage and provider-search page for
quick browsing by trade.

## Payments

Payments run through [Razorpay](https://razorpay.com) (the standard India
gateway — supports UPI, cards, netbanking). The flow:

1. Customer accepts a provider's quote.
2. Customer opens **Pay provider** from their dashboard, enters (or
   confirms) the amount, and pays through Razorpay's checkout.
3. The app verifies Razorpay's payment signature server-side before marking
   it paid — this is the step that actually matters for security; never
   trust a "payment succeeded" message from the browser alone.

**Payments are optional.** With no Razorpay keys configured, the app runs
fine end-to-end — the payment page just shows a note to arrange payment
with the provider directly, instead of a checkout button. To turn payments
on:

1. Create a free account at [razorpay.com](https://razorpay.com).
2. Go to **Settings → API Keys** in the Razorpay dashboard and generate a
   **test mode** key pair (no business verification needed for test mode).
3. Set `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET` — in `.env` locally, or
   as Environment Variables on Vercel.
4. Test mode gives you fake card numbers (see
   [Razorpay's test card docs](https://razorpay.com/docs/payments/payments/test-card-upi-details/))
   so you can run a full payment without moving real money. Switch to live
   keys only once you've gone through Razorpay's activation/KYC process.

## Production hardening already in place

- **CSRF protection** on every form (Flask-WTF) — including the
  admin-verify, accept-quote and mark-complete actions, which are POST
  requests rather than plain links.
- **Payment signatures verified server-side** — the browser never gets to
  decide whether a payment succeeded.
- **Secure sessions** — HttpOnly, SameSite=Lax cookies, and Secure
  (HTTPS-only) cookies automatically once `VERCEL`/`FLASK_ENV=production`
  is detected.
- **Security headers** (`X-Content-Type-Options`, `X-Frame-Options`,
  `Referrer-Policy`, `Strict-Transport-Security` in production).
- **Proxy-aware** (`ProxyFix`) so it correctly detects HTTPS/host behind
  Vercel's reverse proxy.
- A `/healthz` endpoint for uptime checks.
- A real 500 error page instead of a stack trace, with the DB session
  rolled back so one failed request can't corrupt the next one.
- Fails loudly at startup in production if `SECRET_KEY` or `DATABASE_URL`
  is missing, instead of silently falling back to something insecure.

## ⚠️ Before you deploy to Vercel: the database

**Vercel's filesystem is read-only and ephemeral outside `/tmp`.** SQLite —
what this app uses for local development — cannot be used in production
there; any data written to it would vanish between requests. This app is
already wired to require a real database in production:

- Locally, with no `DATABASE_URL` set, it uses SQLite automatically — no
  setup needed.
- In production, it requires `DATABASE_URL` to point at a Postgres
  database, and will refuse to start without it.

Two free options that work well with Vercel's Hobby plan:

- **[Neon](https://neon.tech)** — free Postgres, generous limits, integrates
  with Vercel directly from their marketplace/integrations page.
- **[Supabase](https://supabase.com)** — free Postgres with a dashboard, if
  you'd also like to browse your data outside the app.

Either way, copy the connection string they give you (it usually starts
`postgresql://` or `postgres://` — both work here) into `DATABASE_URL`.

**Also worth knowing before you rely on Vercel's free Hobby plan:** it's
scoped to personal/non-commercial use, and serverless functions there have
a short execution timeout (seconds, not minutes). Fine for this app's
request/response pages, but worth checking Vercel's current
[pricing and limits](https://vercel.com/docs/plans/hobby) page if you plan
to charge for the service or expect heavy traffic.

---

## Running it locally on Windows (VS Code)

1. **Install Python**, if you haven't: get it from
   [python.org/downloads](https://www.python.org/downloads/) — during
   install, tick **"Add python.exe to PATH"**.
2. **Install the VS Code Python extension**: open VS Code → Extensions
   (`Ctrl+Shift+X`) → search "Python" → install Microsoft's official one.
3. **Open the project folder**: `File → Open Folder…` → select the
   `tripura-services` folder you unzipped.
4. **Open a terminal in VS Code**: `` Ctrl+` `` (or `Terminal → New
   Terminal`). By default this opens PowerShell on Windows.
5. **Create a virtual environment**:
   ```powershell
   python -m venv venv
   ```
6. **Activate it**:
   ```powershell
   .\venv\Scripts\Activate.ps1
   ```
   If you get an error like *"running scripts is disabled on this
   system"*, PowerShell's execution policy is blocking it. Run this once
   (only affects the current terminal window, nothing permanent):
   ```powershell
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
   ```
   then re-run the activate command. Alternatively, switch the VS Code
   terminal to **Command Prompt** (click the dropdown next to the `+` in
   the terminal panel → "Command Prompt") and activate with:
   ```cmd
   venv\Scripts\activate.bat
   ```
7. **Select the interpreter in VS Code** so linting/debugging use the venv
   too: `Ctrl+Shift+P` → "Python: Select Interpreter" → pick the one under
   `.\venv\Scripts\python.exe`.
8. **Install dependencies**:
   ```powershell
   pip install -r requirements.txt
   ```
9. **Set up your environment file**:
   ```powershell
   copy .env.example .env
   ```
   Open `.env` in VS Code and set `SECRET_KEY` at minimum. Generate one
   with:
   ```powershell
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
   Paste the result in as `SECRET_KEY=...`. Leave `DATABASE_URL` and the
   `RAZORPAY_*` lines commented out for now — SQLite and no-payments mode
   both work fine for local testing.
10. **Run it**:
    ```powershell
    python app.py
    ```
11. Open **http://localhost:5000** in your browser. A local SQLite file
    (`tripura_services.db`) is created automatically on first run.

Each time you come back to work on it: reopen the folder in VS Code,
reopen the terminal, run `.\venv\Scripts\Activate.ps1` again (you'll see
`(venv)` appear in the prompt), then `python app.py`.

### Adding demo providers (Windows)

To populate the app with sample providers spread across every category and
district (useful for testing search/filter, or just so it doesn't look
empty):

```powershell
python seed_demo_data.py
```

This creates 12 demo provider accounts (all using the password
`Demo@1234`) plus a few reviews. It's safe to run more than once — it skips
any demo account that already exists rather than duplicating it.

### Making yourself an admin (Windows)

With the venv activated and the app's database already created (run the
app once first), register a normal account through the site, then run:

```powershell
python make_admin.py you@example.com
```

Log out and back in — you'll now see an **Admin** link for verifying
providers.

---

## Hosting it on Vercel (free)

Vercel auto-detects a Flask app from the `app` variable in `app.py` at the
project root — no manual server configuration needed (the included
`vercel.json` only sets a function timeout).

1. **Get the code onto GitHub.** In VS Code: `Source Control` panel
   (`Ctrl+Shift+G`) → "Publish to GitHub" (installs GitHub auth the first
   time), or manually:
   ```powershell
   git init
   git add .
   git commit -m "Initial commit"
   ```
   then create a repo on [github.com/new](https://github.com/new) and
   follow its "push an existing repository" instructions.
2. **Set up a free Postgres database** (required — see the warning above):
   sign up at [neon.tech](https://neon.tech) or [supabase.com](https://supabase.com),
   create a project, and copy the connection string.
3. **(Optional) Set up Razorpay** if you want online payments live — see
   the Payments section above for test-mode keys.
4. **Import the project into Vercel**:
   - Go to [vercel.com](https://vercel.com), sign up/log in (GitHub login
     is easiest).
   - **Add New → Project** → select your GitHub repo → **Import**.
5. **Add environment variables** before deploying — under the import
   screen's "Environment Variables" section (or later under **Project →
   Settings → Environment Variables**):
   | Key | Value |
   |---|---|
   | `SECRET_KEY` | output of `python -c "import secrets; print(secrets.token_hex(32))"` |
   | `DATABASE_URL` | your Neon/Supabase connection string |
   | `RAZORPAY_KEY_ID` | *(optional)* from Razorpay dashboard |
   | `RAZORPAY_KEY_SECRET` | *(optional)* from Razorpay dashboard |
6. **Deploy.** Vercel installs `requirements.txt` and builds automatically.
   First deploys typically take under a minute.
7. **Create your first admin** — Vercel doesn't give you a terminal on the
   live server, so run `make_admin.py` from your own machine pointed at
   the *production* database:
   ```powershell
   $env:DATABASE_URL="your-neon-or-supabase-url-here"
   python make_admin.py you@example.com
   ```
   (In Command Prompt instead of PowerShell, use `set DATABASE_URL=...`
   on its own line first.)

Every time you push new commits to GitHub, Vercel redeploys automatically.

## Project structure

```
app.py                     — routes, app factory, security/error handling
models.py                  — User, ProviderProfile, ServiceRequest, Quote, Payment, Review
config.py                  — categories, colours, icons, districts, env-based settings
templates/                 — Jinja2 HTML templates
  _services_sidebar.html   — shared right-hand category navigation
public/                    — static assets (css, favicon) — served by Vercel's CDN
                              directly in production, and by Flask locally
make_admin.py               — CLI helper to promote a user to admin
seed_demo_data.py           — CLI helper to add demo providers/reviews
vercel.json                 — function timeout config for Vercel
.env.example                — template for local environment variables
```

## Where to take it next

This is a solid, deployable first version — not a finished product. Natural
next steps, roughly in order of what a real launch would need:

- **Database migrations** — right now `db.create_all()` runs on startup,
  which is fine for the initial schema but won't handle future column
  changes safely. Add [Flask-Migrate](https://flask-migrate.readthedocs.io/)
  once the schema needs to evolve.
- **Photo/video uploads** on requests and quotes — important for remote
  clients who can't inspect work in person. (Note: uploads can't be saved
  to Vercel's local filesystem either — you'd want S3, Cloudinary, or
  Vercel Blob storage.)
- **Real notifications** (SMS/WhatsApp/email) when a quote arrives or a
  request matches a provider — right now it's dashboard-only.
- **Rate limiting** on login and registration (e.g. Flask-Limiter) to
  slow down credential-stuffing attempts.
- **Payment webhooks** — right now payment confirmation relies on the
  customer's browser completing the redirect back to the app. Adding a
  [Razorpay webhook](https://razorpay.com/docs/webhooks/) means payments
  still get marked correctly even if that redirect is interrupted.
- **Identity/business verification** workflow for admins (currently a
  single "Verify" button — no document upload yet).
- **Search ranking** beyond verified-first (e.g. by rating, response time).
