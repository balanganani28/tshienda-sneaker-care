"""Unit tests for public order tracking & privacy."""
import unittest
from app import create_app
from app.extensions import db
from app.models import Customer, Order

class TrackingTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        self.customer = Customer(name='Lindiwe Zulu', phone='27829998877', consent_flag=True)
        db.session.add(self.customer)
        db.session.commit()

        self.order = Order(
            order_number='TSH-TEST1', customer_id=self.customer.id,
            service='deep', pairs=1, price=150.0, stage='washing'
        )
        db.session.add(self.order)
        db.session.commit()

    def tearDown(self):
        db.drop_all()
        self.ctx.pop()

    def test_tracking_page_found(self):
        resp = self.client.get('/track/TSH-TEST1')
        self.assertEqual(resp.status_code, 200)
        # Ensure customer phone number is NEVER leaked on public page
        self.assertNotIn(b'27829998877', resp.data)
        self.assertNotIn(b'0829998877', resp.data)
        self.assertIn(b'TSH-TEST1', resp.data)
        self.assertIn(b'Deep Clean', resp.data)

    def test_tracking_page_not_found(self):
        resp = self.client.get('/track/NONEXISTENT')
        self.assertEqual(resp.status_code, 200)

if __name__ == '__main__':
    unittest.main()
