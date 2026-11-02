"""Staff operations portal routes."""
import csv, io
from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request, Response, current_app
from flask_login import login_required, current_user
from app.extensions import db
from app.models import User, Customer, Order, StageLog, Setting, STAGE_KEYS, STAGE_MAP, SERVICE_MAP, REFERRAL_MAP
from app.staff.forms import DropoffForm, SettingsForm, ManualScanForm
from app.utils.qr import generate_qr_base64
from app.utils.security import owner_required, sanitize_sa_phone, mask_phone, run_popia_phone_retention_cleanup
from app.utils.whatsapp import get_wa_me_link, send_cloud_api_notification, is_cloud_api_enabled, DEFAULT_TEMPLATES

staff_bp = Blueprint('staff', __name__, url_prefix='/staff')

@staff_bp.before_request
@login_required
def require_staff(): pass

@staff_bp.route('/dashboard')
def dashboard():
    current_filter = request.args.get('stage', 'all')
    search_query = request.args.get('q', '').strip()
    all_orders = Order.query.all()
    stage_counts = {'all': len(all_orders)}
    for s_key in STAGE_KEYS:
        stage_counts[s_key] = sum(1 for o in all_orders if o.stage == s_key)

    orders_query = Order.query
    if current_filter in STAGE_KEYS:
        orders_query = orders_query.filter_by(stage=current_filter)
    filtered_orders = orders_query.order_by('created_at desc').all()

    if search_query:
        sq_lower = search_query.lower()
        filtered_orders = [
            o for o in filtered_orders
            if sq_lower in o.order_number.lower()
            or sq_lower in (o.customer.name.lower() if o.customer else '')
        ]

    base_url = request.host_url.rstrip('/')
    orders_data = []
    for o in filtered_orders:
        c = o.customer
        wa_link = get_wa_me_link(o, c, base_url) if c else None
        orders_data.append({
            'order': o, 'customer': c,
            'masked_phone': mask_phone(c.phone) if c else '[No Phone]',
            'wa_link': wa_link
        })

    return render_template(
        'staff/dashboard.html',
        orders_data=orders_data, stage_counts=stage_counts,
        current_filter=current_filter, search_query=search_query,
        stage_map=STAGE_MAP, service_map=SERVICE_MAP
    )

@staff_bp.route('/dropoff', methods=['GET', 'POST'])
def dropoff():
    form = DropoffForm()
    if form.validate_on_submit():
        clean_phone = sanitize_sa_phone(form.whatsapp_phone.data)
        customer_name = form.customer_name.data.strip()

        customer = Customer.query.filter_by(phone=clean_phone).first() if clean_phone else None
        if not customer:
            customer = Customer(
                name=customer_name, phone=clean_phone,
                consent_flag=form.popia_consent.data,
                consent_timestamp=datetime.utcnow() if form.popia_consent.data else None
            )
            db.session.add(customer)
            db.session.commit()
        else:
            customer.name = customer_name
            customer.consent_flag = form.popia_consent.data
            customer.consent_timestamp = datetime.utcnow()
            customer.phone_anonymized = False
            db.session.commit()

        service_key = form.service.data
        default_prices = {'standard': 100.0, 'deep': 150.0, 'suede_leather': 200.0}
        price_val = Setting.get(f"price_{service_key}", str(default_prices.get(service_key, 100.0)))
        try: unit_price = float(price_val)
        except ValueError: unit_price = default_prices.get(service_key, 100.0)

        pairs = form.pairs.data
        total_price = unit_price * pairs
        order_code = Order.generate_order_number()

        new_order = Order(
            order_number=order_code, customer_id=customer.id,
            service=service_key, pairs=pairs, price=total_price,
            stage='dropped_off', notes=form.notes.data.strip() if form.notes.data else None,
            source=form.source.data
        )
        db.session.add(new_order)
        db.session.commit()

        log = StageLog(
            order_id=new_order.id, stage='dropped_off',
            user_id=current_user.id, timestamp=datetime.utcnow(),
            notes="Order intake and dropped off at UWC Student Centre kiosk."
        )
        db.session.add(log)
        db.session.commit()

        flash(f"Order {order_code} created for {customer.name}! Print tag below.", "success")
        return redirect(url_for('staff.qr_tag', order_id=new_order.id))

    return render_template('staff/dropoff.html', form=form)

@staff_bp.route('/orders/<int:order_id>/tag')
def qr_tag(order_id):
    order = Order.query.get_or_404(order_id)
    customer = order.customer
    track_url = url_for('public.track_order', order_code=order.order_number, _external=True)
    qr_b64 = generate_qr_base64(track_url, box_size=8, border=2)
    wa_link = get_wa_me_link(order, customer, request.host_url)
    return render_template('staff/qr_tag.html', order=order, customer=customer, qr_b64=qr_b64, track_url=track_url, wa_link=wa_link)

@staff_bp.route('/scan', methods=['GET', 'POST'])
def scan():
    form = ManualScanForm()
    scanned_order = None
    wa_link = None
    next_stage_name = None

    lookup_code = request.args.get('code', '').strip().upper()
    if form.validate_on_submit():
        lookup_code = form.order_number.data.strip().upper()

    if lookup_code:
        if '/track/' in lookup_code:
            lookup_code = lookup_code.split('/track/')[-1].strip().upper()
        scanned_order = Order.query.filter_by(order_number=lookup_code).first()
        if not scanned_order:
            flash(f"No order found with code '{lookup_code}'. Please check and try again.", "warning")
        else:
            customer = scanned_order.customer
            wa_link = get_wa_me_link(scanned_order, customer, request.host_url)
            next_stage_name = scanned_order.next_stage_display

    return render_template(
        'staff/scan.html', form=form, scanned_order=scanned_order,
        wa_link=wa_link, next_stage_name=next_stage_name,
        cloud_api_active=is_cloud_api_enabled()
    )

@staff_bp.route('/orders/<int:order_id>/advance', methods=['POST'])
def advance_order(order_id):
    order = Order.query.get_or_404(order_id)
    success, res = order.advance_stage(staff_user=current_user)
    if not success:
        flash(res, "warning")
        return redirect(request.referrer or url_for('staff.dashboard'))

    customer = order.customer
    base_url = request.host_url.rstrip('/')
    wa_link = get_wa_me_link(order, customer, base_url)

    if is_cloud_api_enabled():
        cloud_res = send_cloud_api_notification(order, customer, base_url)
        if cloud_res.get('status') == 'sent':
            flash(f"Order {order.order_number} moved to {order.stage_display}. WhatsApp Cloud API notification sent!", "success")
        else:
            flash(f"Order {order.order_number} moved to {order.stage_display}.", "info")
    else:
        flash(f"Order {order.order_number} advanced to {order.stage_display}!", "success")

    if request.args.get('from') == 'scan':
        return redirect(url_for('staff.scan', code=order.order_number))
    return redirect(url_for('staff.dashboard', stage=order.stage))

@staff_bp.route('/orders/<int:order_id>/collect', methods=['POST'])
def mark_collected(order_id):
    order = Order.query.get_or_404(order_id)
    if order.stage != 'collected':
        order.stage = 'collected'
        order.updated_at = datetime.utcnow()
        log = StageLog(
            order_id=order.id, stage='collected',
            user_id=current_user.id, timestamp=datetime.utcnow(),
            notes="Marked as Collected by customer at UWC kiosk."
        )
        db.session.add(log)
        db.session.commit()
        flash(f"Order {order.order_number} marked as Collected. Thank you!", "success")
    return redirect(request.referrer or url_for('staff.dashboard'))

@staff_bp.route('/reports')
def reports():
    orders = Order.query.all()
    now = datetime.utcnow()
    daily_stats = []
    for d in range(6, -1, -1):
        day_date = (now - timedelta(days=d)).date()
        day_orders = [o for o in orders if o.created_at.date() == day_date]
        daily_stats.append({
            'date': day_date.strftime('%a, %d %b'),
            'orders': len(day_orders),
            'pairs': sum(o.pairs for o in day_orders),
            'revenue': sum(o.price for o in day_orders)
        })

    weekly_stats = []
    for w in range(3, -1, -1):
        start_w = (now - timedelta(days=(w + 1) * 7)).date()
        end_w = (now - timedelta(days=w * 7)).date()
        week_orders = [o for o in orders if start_w <= o.created_at.date() < end_w]
        weekly_stats.append({
            'label': f"Week -{w} ({start_w.strftime('%d %b')} - {end_w.strftime('%d %b')})" if w > 0 else f"Current Week (from {start_w.strftime('%d %b')})",
            'orders': len(week_orders),
            'pairs': sum(o.pairs for o in week_orders),
            'revenue': sum(o.price for o in week_orders)
        })

    customers = Customer.query.all()
    repeat_customers = [c for c in customers if c.orders.count() > 1]
    repeat_rate = (len(repeat_customers) / len(customers) * 100) if customers else 0.0

    referral_counts = {r_label: 0 for r_label in REFERRAL_MAP.values()}
    for o in orders:
        lbl = REFERRAL_MAP.get(o.source, 'Other')
        referral_counts[lbl] = referral_counts.get(lbl, 0) + 1

    return render_template(
        'staff/reports.html',
        daily_stats=daily_stats, weekly_stats=weekly_stats,
        total_pairs=sum(o.pairs for o in orders),
        total_revenue=sum(o.price for o in orders),
        total_customers=len(customers),
        repeat_customers_count=len(repeat_customers),
        repeat_rate=round(repeat_rate, 1),
        referral_counts=referral_counts
    )

@staff_bp.route('/reports/export.csv')
def export_csv():
    orders = Order.query.order_by('created_at desc').all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Order Number', 'Date Dropped Off', 'Service', 'Pairs',
        'Price (ZAR)', 'Current Stage', 'Referral Source',
        'Customer Name', 'Consent Given', 'Notes'
    ])
    for o in orders:
        c = o.customer
        writer.writerow([
            o.order_number, o.created_at.strftime('%Y-%m-%d %H:%M'),
            o.service_display, o.pairs, f"{o.price:.2f}", o.stage_display,
            o.source_display, c.name if c else 'Unknown',
            'Yes' if (c and c.consent_flag) else 'No', o.notes or ''
        ])
    return Response(
        output.getvalue(), mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename="tshienda_orders_export.csv"'}
    )

@staff_bp.route('/settings', methods=['GET', 'POST'])
@owner_required
def settings():
    form = SettingsForm()
    if form.validate_on_submit():
        Setting.set('price_standard', form.price_standard.data.strip())
        Setting.set('price_deep', form.price_deep.data.strip())
        Setting.set('price_suede_leather', form.price_suede_leather.data.strip())
        Setting.set('whatsapp_template_dropped_off', form.whatsapp_template_dropped_off.data.strip())
        Setting.set('whatsapp_template_washing', form.whatsapp_template_washing.data.strip())
        Setting.set('whatsapp_template_drying', form.whatsapp_template_drying.data.strip())
        Setting.set('whatsapp_template_ready', form.whatsapp_template_ready.data.strip())
        Setting.set('whatsapp_template_collected', form.whatsapp_template_collected.data.strip())
        flash("Settings and message templates updated successfully!", "success")
        return redirect(url_for('staff.settings'))

    if request.method == 'GET':
        form.price_standard.data = Setting.get('price_standard', '100')
        form.price_deep.data = Setting.get('price_deep', '150')
        form.price_suede_leather.data = Setting.get('price_suede_leather', '200')
        form.whatsapp_template_dropped_off.data = Setting.get('whatsapp_template_dropped_off', DEFAULT_TEMPLATES['dropped_off'])
        form.whatsapp_template_washing.data = Setting.get('whatsapp_template_washing', DEFAULT_TEMPLATES['washing'])
        form.whatsapp_template_drying.data = Setting.get('whatsapp_template_drying', DEFAULT_TEMPLATES['drying'])
        form.whatsapp_template_ready.data = Setting.get('whatsapp_template_ready', DEFAULT_TEMPLATES['ready'])
        form.whatsapp_template_collected.data = Setting.get('whatsapp_template_collected', DEFAULT_TEMPLATES['collected'])

    cutoff_12m = datetime.utcnow() - timedelta(days=365)
    eligible_popia_customers = Customer.query.filter(Customer.phone_anonymized == False, Customer.created_at < cutoff_12m).count()

    return render_template(
        'staff/settings.html', form=form,
        eligible_popia_customers=eligible_popia_customers,
        cloud_api_active=is_cloud_api_enabled()
    )

@staff_bp.route('/settings/cleanup-popia', methods=['POST'])
@owner_required
def cleanup_popia():
    retention_months = current_app.config.get('POPIA_PHONE_RETENTION_MONTHS', 12)
    anonymized_count = run_popia_phone_retention_cleanup(retention_months=retention_months)
    flash(f"POPIA Maintenance Complete: Anonymized phone records for {anonymized_count} customer(s).", "info")
    return redirect(url_for('staff.settings'))
