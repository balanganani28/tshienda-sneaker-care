"""API routes for scanner and WhatsApp Phase 2 webhooks."""
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.models import Order
from app.utils.whatsapp import verify_webhook_token, process_webhook_event, get_wa_me_link, send_cloud_api_notification, is_cloud_api_enabled

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/whatsapp/webhook', methods=['GET'])
def whatsapp_webhook_verification():
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    is_valid, verified_challenge = verify_webhook_token(mode, token, challenge)
    if is_valid: return verified_challenge, 200
    return "Forbidden", 403

@api_bp.route('/whatsapp/webhook', methods=['POST'])
def whatsapp_webhook_events():
    payload = request.get_json(silent=True) or {}
    result = process_webhook_event(payload)
    return jsonify({'status': 'received', 'processed': len(result.get('events', []))}), 200

@api_bp.route('/orders/<string:order_code>', methods=['GET'])
@login_required
def api_get_order(order_code):
    clean_code = order_code.strip().upper()
    order = Order.query.filter_by(order_number=clean_code).first()
    if not order: return jsonify({'error': 'Order not found'}), 404
    customer = order.customer
    base_url = request.host_url.rstrip('/')
    wa_link = get_wa_me_link(order, customer, base_url)
    return jsonify({
        'id': order.id, 'order_number': order.order_number,
        'customer_name': customer.name if customer else 'Unknown',
        'service': order.service_display, 'pairs': order.pairs,
        'price': order.price, 'stage': order.stage,
        'stage_display': order.stage_display, 'next_stage': order.next_stage,
        'next_stage_display': order.next_stage_display,
        'can_advance': order.can_advance, 'notes': order.notes or '',
        'wa_link': wa_link
    })

@api_bp.route('/orders/<string:order_code>/advance', methods=['POST'])
@login_required
def api_advance_order(order_code):
    clean_code = order_code.strip().upper()
    order = Order.query.filter_by(order_number=clean_code).first()
    if not order: return jsonify({'error': 'Order not found'}), 404
    success, res = order.advance_stage(staff_user=current_user)
    if not success: return jsonify({'error': res}), 400
    customer = order.customer
    base_url = request.host_url.rstrip('/')
    wa_link = get_wa_me_link(order, customer, base_url)
    cloud_status = send_cloud_api_notification(order, customer, base_url) if is_cloud_api_enabled() else None
    return jsonify({
        'success': True, 'order_number': order.order_number,
        'stage': order.stage, 'stage_display': order.stage_display,
        'next_stage': order.next_stage, 'next_stage_display': order.next_stage_display,
        'can_advance': order.can_advance, 'wa_link': wa_link,
        'cloud_api_status': cloud_status
    })
