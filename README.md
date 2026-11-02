# Tshienda Sneaker Care

> *"Sneaker care with real time order tracking."*

Tshienda is a South African student business operating at the **University of the Western Cape (UWC)** Student Centre in Bellville, Cape Town. The name is a Tshivenda word for shoe.

---

## Table of Contents
1. [Overview & Tech Stack](#overview--tech-stack)
2. [Public & Staff Features](#public--staff-features)
3. [Setup & Local Development](#setup--local-development)
4. [Deployment Guide (PythonAnywhere & Render)](#deployment-guide-pythonanywhere--render)
5. [WhatsApp Notifications (Phase 1 & Phase 2)](#whatsapp-notifications)
6. [POPIA Compliance & Security](#popia-compliance--security)
7. [Running Tests](#running-tests)

---

## 1. Overview & Tech Stack
- **Backend**: Python 3, Flask, SQLAlchemy ORM (configured for SQLite in development, seamless PostgreSQL in production via `DATABASE_URL`).
- **Security & Auth**: Flask-Login for session management, Flask-Bcrypt for password hashing, Flask-WTF for CSRF protection.
- **Frontend**: Mobile-first, responsive plain HTML5, CSS3 with custom design tokens, vanilla JavaScript (no heavy JavaScript framework), light and dark mode.
- **QR Operations**: In-browser camera scanning (`BarcodeDetector` API with fallback) and printable 80x55mm label tag generator.

---

## 2. Public & Staff Features

### Public Portal (No login required)
- **Home (`/`)**: Hero with live order lookup, 4-step workflow, prices preview, About section, and kiosk campus contact info.
- **Prices (`/prices`)**: Standard clean (from R100), Deep clean (from R150), Suede & leather (from R200). Dynamic prices editable by staff. Marked placeholders for launch specials and referral offers.
- **Track Order (`/track` & `/track/<order_code>`)**: Rate-limited status lookup. Displays the **5-stage sneaker progress bar** (Dropped off ➔ Washing ➔ Drying ➔ Ready ➔ Collected) with warm yellow active pulse and timestamp history. Strictly hides personal phone numbers.
- **FAQ (`/faq`)**: Turnaround times (24–48h), damage policy, uncollected pairs policy, and POPIA WhatsApp consent.
- **Privacy (`/privacy`)**: Full POPIA policy detailing collection purpose, retention limits, and data subject rights.
- **Terms (`/terms`)**: Service contract, liability disclaimers, and uncollected pairs policies.
- **Data Erasure (`/privacy/request-deletion`)**: Self-service POPIA right-to-erasure form.

### Staff Portal (Login required)
- **Login (`/auth/login`)**: Account lockout after 5 consecutive failed attempts (15 minutes lockout), 30-minute session inactivity timeout.
- **New Drop-off (`/staff/dropoff`)**: Customer name, South African WhatsApp number validation (`+27...` / `0...`), service tier, pair count, condition notes, referral channel, and **mandatory POPIA consent checkbox**.
- **Printable QR Tag (`/staff/orders/<id>/tag`)**: Compact printable tag with crisp QR code, bold order number, customer name, and intake timestamp.
- **QR Scanner (`/staff/scan`)**: Phone camera scanning with audio beep/vibration feedback + manual order code fallback. One-tap button advances order to next stage and opens prefilled WhatsApp message.
- **Dashboard (`/staff/dashboard`)**: Stage filter cards (All, Dropped off, Washing, Drying, Ready, Collected), live customer search, and quick "Mark Collected" button.
- **Reports (`/staff/reports`)**: Daily and weekly pairs cleaned, revenue generated, repeat customer analytics, referral sources breakdown, and **CSV Export**.
- **Settings (`/staff/settings`)** *(Owner only)*: Editable service prices, customizable WhatsApp stage templates, and 1-click POPIA phone retention maintenance.

---

## 3. Setup & Local Development

### Prerequisites
- Python 3.10+
- Virtual environment tool (`venv`)

### Installation Steps
```bash
# 1. Clone repository
git clone <repo-url>
cd tshienda

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scriptsctivate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env

# 5. Seed database with demo accounts and sample orders
python seed.py

# 6. Start development server
python run.py
```
Open **http://127.0.0.1:5000** in your browser.

### Default Seed Credentials
- **Owner Account**: `owner@tshienda.co.za` | Password: `TshiendaOwner2026!`
- **Staff Account**: `staff@tshienda.co.za` | Password: `TshiendaStaff2026!`
- **Demo Order Numbers**: `TSH-7K2M9`, `TSH-4W8B2`, `TSH-9R1P6`, `TSH-2M5T8`, `TSH-6H3X7`

---

## 4. Deployment Guide (PythonAnywhere & Render)

### Deploying to PythonAnywhere (Low-Cost / Free)
1. Sign up for a free account at [pythonanywhere.com](https://www.pythonanywhere.com).
2. Go to the **Consoles** tab and open a Bash console:
   ```bash
   git clone <repo-url> tshienda
   cd tshienda
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   python seed.py
   ```
3. Go to the **Web** tab:
   - Click **Add a new web app** ➔ Choose **Manual configuration** ➔ Python 3.11.
   - Under **Virtualenv**, enter path: `/home/<username>/tshienda/venv`.
   - Edit the **WSGI configuration file**:
     ```python
     import sys, os
     path = '/home/<username>/tshienda'
     if path not in sys.path:
         sys.path.insert(0, path)

     os.environ['FLASK_CONFIG'] = 'production'
     os.environ['SECRET_KEY'] = 'generate-a-strong-random-key'
     from wsgi import application
     ```
   - Under **Static files**, configure:
     - URL: `/static/` ➔ Directory: `/home/<username>/tshienda/app/static/`
4. Click **Reload <username>.pythonanywhere.com**.

### Deploying to Render
1. Create a free account at [render.com](https://render.com).
2. Click **New +** ➔ **Web Service** and connect your GitHub repository.
3. Configure settings:
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt && python seed.py`
   - **Start Command**: `gunicorn wsgi:application`
4. Add Environment Variables:
   - `FLASK_CONFIG`: `production`
   - `SECRET_KEY`: `<secure-random-string>`
   - `DATABASE_URL`: Attach a Render PostgreSQL database if desired.
5. Deploy! Render provisions free HTTPS SSL automatically.

---

## 5. WhatsApp Notifications

### Phase 1 (Built & Active Now)
After every stage change, a button opens a prefilled WhatsApp message through a `https://wa.me/<phone>?text=...` link. Staff can send the message with one tap from any phone or desktop browser. Example:
> *"Hi Ayanda! Your Tshienda sneaker care order TSH-7K2M9 (Standard Clean) is now: Washing. Track your kicks live: https://tshienda.co.za/track/TSH-7K2M9"*

### Phase 2 (Behind Feature Flag: `WHATSAPP_CLOUD_API_ENABLED`)
Phase 2 provides direct server-to-server messaging using Meta's official WhatsApp Business Cloud API.
To enable:
1. Register a Meta Business account at [business.facebook.com](https://business.facebook.com).
2. Complete Meta Business Verification (requires business registration documents or university trade letter).
3. Create a WhatsApp Business App in [developers.facebook.com](https://developers.facebook.com).
4. Register a phone number and obtain your `Phone Number ID` and `System User Permanent Access Token`.
5. Submit message templates for approval matching the stages (Dropped off, Washing, Drying, Ready, Collected).
6. In `.env`, set:
   ```env
   WHATSAPP_CLOUD_API_ENABLED=true
   WHATSAPP_ACCESS_TOKEN=your-permanent-access-token
   WHATSAPP_PHONE_NUMBER_ID=your-phone-number-id
   WHATSAPP_WEBHOOK_VERIFY_TOKEN=your-chosen-verify-token
   ```
7. Configure Meta Webhooks to point to `https://your-domain/api/whatsapp/webhook` with event subscriptions for `messages`.

---

## 6. POPIA Compliance & Security
- **Data Minimization**: Only Customer Name, WhatsApp mobile number, and referral channel are collected.
- **Mandatory Consent**: The drop-off form rejects order creation unless the customer explicitly consents to WhatsApp tracking.
- **Rate Limiting**: Public `/track` and staff `/auth/login` lookups are throttled using an in-memory sliding window rate limiter.
- **Hard-to-guess Codes**: Order codes (`TSH-XXXXX`) are cryptographically generated across 24+ million combinations to prevent brute-force order scanning.
- **Privacy on Public Tracking**: Customer phone numbers and personal identifiers are never rendered on public tracking pages.
- **12-Month Automated Cleanup**: Phone numbers for orders completed more than 12 months ago are permanently anonymized via `run_popia_phone_retention_cleanup()`.

---

## 7. Running Tests
Run the automated test suite covering models, authentication, tracking rate limits, WhatsApp links, and POPIA cleanup:
```bash
python run_tests.py
```
