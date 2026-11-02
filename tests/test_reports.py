"""Unit tests for reports and CSV export."""
import unittest
from app import create_app
from app.extensions import db
from app.models import User, Customer, Order
from app.utils.qr import generate_qr_base64

class ReportsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        self.owner = User(email='owner@tshienda.co.za', name='Owner', role='owner')
        self.owner.set_password('Pass123!')
        db.session.add(self.owner)
        db.session.commit()

    def tearDown(self):
        db.drop_all()
        self.ctx.pop()

    def test_qr_generation(self):
        b64 = generate_qr_base64('https://tshienda.co.za/track/TSH-7K2M9')
        self.assertTrue(b64.startswith('data:image/'))

if __name__ == '__main__':
    unittest.main()
