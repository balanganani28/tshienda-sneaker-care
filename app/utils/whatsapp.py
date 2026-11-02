"""WhatsApp integration: Phase 1 (wa.me) & Phase 2 (Cloud API)."""
import json, logging, urllib.parse, urllib.request
from flask import current_app
from app.models import Setting, Order, Customer
from app.utils.security import sanitize_sa_phone

logger = logging.getLogger(__name__)

DEFAULT_TEMPLATES = {
    'dropped_off': (
        "Hi {name}! Your Tshienda sneaker care order {order_number} ({service}, {pairs} pair) "
        "has been received at our UWC Student Centre kiosk. Stage: Dropped off. "
        "Track your kicks live here: {track_url}"
    ),
    'washing': (
        "Hi {name}! Your Tshienda order {order_number} is now: Washing. "
        "Our team is hand-cleaning your sneakers with eco-friendly solutions. "
        "Track live: {track_url}"
    ),
    'drying': (
        "Hi {name}! Your Tshienda order {order_number} is now: Drying. "
        "Sneakers are safely air-drying to preserve delicate materials. "
        "Track live: {track_url}"
    ),
    'ready': (
        "Hi {name}! Great news: Your Tshienda sneaker care order {order_number} is READY for collection! "
        "Pick up your fresh kicks at the UWC Student Centre kiosk. "
        "Show your order number {order_number} at pickup: {track_url}"
    ),
    'collected': (
        "Hi {name}! Your Tshienda order {order_number} has been marked as Collected. "
        "Thank you for supporting our student business on UWC campus! Walk fresh! "
        "Tag us @tshienda."
    )
}

def build_order_message_text(order: Order, customer: Customer, base_url: str = "") -> str:
    template = Setting.get(f"whatsapp_template_{order.stage}", DEFAULT_TEMPLATES.get(order.stage, DEFAULT_TEMPLATES['dropped_off']))
    track_url = f"{base_url.rstrip('/')}/track/{order.order_number}"
    reps = {
        '{name}': customer.name,
        '{order_number}': order.order_number,
        '{stage}': order.stage_display,
        '{service}': order.service_display,
        '{pairs}': str(order.pairs),
        '{track_url}': track_url
    }
    msg = template
    for k, v in reps.items(): msg = msg.replace(k, v)
    return msg

def get_wa_me_link(order: Order, customer: Customer, base_url: str = "") -> str | None:
    if not customer.phone: return None
    clean = sanitize_sa_phone(customer.phone)
    if not clean: return None
    text = build_order_message_text(order, customer, base_url)
    return f"https://wa.me/{clean}?text={urllib.parse.quote(text)}"

def is_cloud_api_enabled() -> bool:
    try: return current_app.config.get('WHATSAPP_CLOUD_API_ENABLED', False)
    except Exception: return False

def send_cloud_api_notification(order: Order, customer: Customer, base_url: str = "") -> dict:
    if not is_cloud_api_enabled():
        return {'status': 'skipped', 'reason': 'WhatsApp Cloud API feature flag is disabled.'}
    if not customer.consent_flag:
        return {'status': 'blocked', 'reason': 'Customer did not consent to WhatsApp updates (POPIA).'}
    clean = sanitize_sa_phone(customer.phone)
    if not clean: return {'status': 'error', 'reason': 'Invalid South African phone number.'}
    
    phone_id = current_app.config.get('WHATSAPP_PHONE_NUMBER_ID', '')
    token = current_app.config.get('WHATSAPP_ACCESS_TOKEN', '')
    if not phone_id or not token:
        return {'status': 'error', 'reason': 'Missing WhatsApp Cloud API credentials in environment.'}

    url = f"https://graph.facebook.com/v18.0/{phone_id}/messages"
    body_text = build_order_message_text(order, customer, base_url)
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": clean,
        "type": "text",
        "text": {"preview_url": True, "body": body_text}
    }
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return {'status': 'sent', 'meta_response': data}
    except Exception as e:
        return {'status': 'failed', 'error': str(e)}

def verify_webhook_token(mode: str, token: str, challenge: str) -> tuple[bool, str]:
    exp = current_app.config.get('WHATSAPP_WEBHOOK_VERIFY_TOKEN', '')
    if mode == 'subscribe' and token and token == exp:
        return True, challenge
    return False, ""

def process_webhook_event(payload: dict) -> dict:
    events = []
    for entry in payload.get('entry', []):
        for ch in entry.get('changes', []):
            for st in ch.get('value', {}).get('statuses', []):
                events.append({
                    'recipient': st.get('recipient_id'),
                    'status': st.get('status'),
                    'timestamp': st.get('timestamp')
                })
    return {'events': events}
