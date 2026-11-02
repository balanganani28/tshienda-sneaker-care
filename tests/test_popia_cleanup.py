"""Unit tests for POPIA phone retention cleanup."""
import unittest
from datetime import datetime, timedelta
from app import create_app
from app.extensions import db
from app.models import Customer, Order
from app.utils.security import run_popia_phone_retention_cleanup

class PopiaCleanupTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

    def tearDown(self):
        db.drop_all()
        self.ctx.pop()

    def test_popia_phone_anonymization(self):
        # 1. Old customer completed 14 months ago
        old_time = datetime.utcnow() - timedelta(days=420)
        c_old = Customer(name='Old Customer', phone='27820000001', consent_flag=True, created_at=old_time)
        db.session.add(c_old)
        db.session.commit()

        o_old = Order(
            order_number='TSH-OLD01', customer_id=c_old.id, service='standard',
            pairs=1, price=100.0, stage='collected', created_at=old_time, updated_at=old_time
        )
        db.session.add(o_old)

        # 2. Recent customer active 1 month ago
        recent_time = datetime.utcnow() - timedelta(days=30)
        c_recent = Customer(name='Recent Customer', phone='27820000002', consent_flag=True, created_at=recent_time)
        db.session.add(c_recent)
        db.session.commit()

        o_recent = Order(
            order_number='TSH-REC01', customer_id=c_recent.id, service='deep',
            pairs=1, price=150.0, stage='collected', created_at=recent_time, updated_at=recent_time
        )
        db.session.add(o_recent)
        db.session.commit()

        # Run cleanup with 12 months retention
        cleaned_count = run_popia_phone_retention_cleanup(retention_months=12)
        self.assertEqual(cleaned_count, 1)

        c_old_refreshed = Customer.query.get(c_old.id)
        self.assertIsNone(c_old_refreshed.phone)
        self.assertTrue(c_old_refreshed.phone_anonymized)

        c_recent_refreshed = Customer.query.get(c_recent.id)
        self.assertIsNotNone(c_recent_refreshed.phone)
        self.assertFalse(c_recent_refreshed.phone_anonymized)

if __name__ == '__main__':
    unittest.main()
