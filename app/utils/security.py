"""Security and POPIA compliance utilities."""
import re
from datetime import datetime, timedelta
from functools import wraps
from flask import abort, flash, redirect, url_for, request
from flask_login import current_user

def sanitize_sa_phone(phone_input: str) -> str | None:
    if not phone_input: return None
    cleaned = re.sub(r'[\s\-\(\)\.]', '', phone_input.strip())
    if cleaned.startswith('+'): cleaned = cleaned[1:]
    if len(cleaned) == 10 and cleaned.startswith('0') and cleaned[1] in ('6', '7', '8'):
        return '27' + cleaned[1:]
    if len(cleaned) == 11 and cleaned.startswith('27') and cleaned[2] in ('6', '7', '8'):
        return cleaned
    if re.match(r'^27[678]\d{8}$', cleaned): return cleaned
    return None

def mask_phone(phone: str | None) -> str:
    if not phone: return "[None / Anonymized]"
    c = str(phone)
    return f"{c[:4]} *** {c[-4:]}" if len(c) >= 9 else "***"

def owner_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("Please log in to access this area.", "warning")
            return redirect(url_for('auth.login', next=request.url))
        if getattr(current_user, 'role', '') != 'owner':
            flash("Owner access required for this action.", "danger")
            return redirect(url_for('staff.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def run_popia_phone_retention_cleanup(retention_months: int = 12) -> int:
    from app.extensions import db
    from app.models import Customer
    cutoff = datetime.utcnow() - timedelta(days=retention_months * 30)
    customers = Customer.query.filter_by(phone_anonymized=False).all()
    count = 0
    for c in customers:
        if not c.phone: continue
        orders = list(c.orders)
        if not orders:
            if c.created_at < cutoff:
                c.anonymize_phone()
                count += 1
            continue
        if all(o.stage == 'collected' and o.updated_at < cutoff for o in orders):
            c.anonymize_phone()
            count += 1
    db.session.commit()
    return count
