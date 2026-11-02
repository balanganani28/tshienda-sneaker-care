"""Unit tests for WhatsApp Phase 1 & Phase 2."""
import unittest
from app import create_app
from app.extensions import db
from app.models import Customer, Order
from app.utils.security import sanitize_sa_phone
from app.utils.whatsapp import get_wa_me_link, is_cloud_api_enabled, send_cloud_api_notification

class WhatsAppTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        self.cust = Customer(name='Kagiso Rabada', phone='082 123 4567', consent_flag=True)
        db.session.add(self.cust)
        db.session.commit()

        self.order = Order(
            order_number='TSH-WA001', customer_id=self.cust.id,
            service='standard', pairs=1, price=100.0, stage='washing'
        )
        db.session.add(self.order)
        db.session.commit()

    def tearDown(self):
        db.drop_all()
        self.ctx.pop()

    def test_phone_sanitization(self):
        self.assertEqual(sanitize_sa_phone('0821234567'), '27821234567')
        self.assertEqual(sanitize_sa_phone('+27 82 123 4567'), '27821234567')
        self.assertEqual(sanitize_sa_phone('071-234-5678'), '27712345678')
        self.assertIsNone(sanitize_sa_phone('12345'))

    def test_phase_1_wa_me_link(self):
        link = get_wa_me_link(self.order, self.cust, 'http://127.0.0.1:5000')
        self.assertIsNotNone(link)
        self.assertTrue(link.startswith('https://wa.me/27821234567?text='))
        self.assertIn('TSH-WA001', link)

    def test_phase_2_feature_flag_disabled_by_default(self):
        self.assertFalse(is_cloud_api_enabled())
        res = send_cloud_api_notification(self.order, self.cust, 'http://127.0.0.1:5000')
        self.assertEqual(res.get('status'), 'skipped')

if __name__ == '__main__':
    unittest.main()
