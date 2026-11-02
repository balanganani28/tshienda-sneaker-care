"""Public marketing and order tracking pages."""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.models import Order, Customer, Setting, ORDER_STAGES, STAGE_KEYS, STAGE_MAP
from app.public.forms import TrackLookupForm, DeletionRequestForm
from app.utils.rate_limiter import rate_limit
from app.utils.security import sanitize_sa_phone

public_bp = Blueprint('public', __name__)

@public_bp.route('/')
def index():
    form = TrackLookupForm()
    prices = {
        'standard': Setting.get('price_standard', '100'),
        'deep': Setting.get('price_deep', '150'),
        'suede_leather': Setting.get('price_suede_leather', '200')
    }
    return render_template('public/index.html', form=form, prices=prices)

@public_bp.route('/prices')
def prices():
    service_prices = {
        'standard': Setting.get('price_standard', '100'),
        'deep': Setting.get('price_deep', '150'),
        'suede_leather': Setting.get('price_suede_leather', '200')
    }
    return render_template('public/prices.html', prices=service_prices)

@public_bp.route('/track', methods=['GET', 'POST'])
@rate_limit(max_requests=15, window_seconds=60)
def track_index():
    form = TrackLookupForm()
    if form.validate_on_submit():
        code = form.order_code.data.strip().upper()
        return redirect(url_for('public.track_order', order_code=code))

    code_param = request.args.get('code', '').strip().upper()
    if code_param:
        return redirect(url_for('public.track_order', order_code=code_param))

    return render_template('public/track.html', form=form, order=None)

@public_bp.route('/track/<string:order_code>')
@rate_limit(max_requests=15, window_seconds=60)
def track_order(order_code):
    form = TrackLookupForm()
    form.order_code.data = order_code.upper()
    order = Order.query.filter_by(order_number=order_code.upper()).first()

    if not order:
        flash(f"Order '{order_code}' was not found. Please double-check the code on your tag or WhatsApp message.", "warning")
        return render_template('public/track.html', form=form, order=None, searched_code=order_code)

    logs = order.stage_logs.order_by('timestamp asc').all()
    stage_timestamps = {log.stage: log.timestamp for log in logs}

    return render_template(
        'public/track.html',
        form=form, order=order, stages=ORDER_STAGES,
        stage_keys=STAGE_KEYS, stage_map=STAGE_MAP,
        stage_timestamps=stage_timestamps,
        current_index=order.stage_index
    )

@public_bp.route('/faq')
def faq(): return render_template('public/faq.html')

@public_bp.route('/privacy')
def privacy(): return render_template('public/privacy.html')

@public_bp.route('/terms')
def terms(): return render_template('public/terms.html')

@public_bp.route('/privacy/request-deletion', methods=['GET', 'POST'])
def request_deletion():
    form = DeletionRequestForm()
    if form.validate_on_submit():
        clean_phone = sanitize_sa_phone(form.phone.data)
        customer = Customer.query.filter_by(phone=clean_phone).first() if clean_phone else None
        if customer:
            customer.anonymize_phone()
            flash("Your POPIA deletion request has been processed. Your phone number has been permanently erased.", "success")
        else:
            flash("Request received. No active customer matched that phone number, or data was already anonymized.", "info")
        return redirect(url_for('public.privacy'))

    return render_template('public/deletion_request.html', form=form)
