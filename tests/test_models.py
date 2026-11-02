"""Unit tests for database models."""
import unittest
from datetime import datetime, timedelta
from app import create_app
from app.extensions import db
from app.models import User, Customer, Order, StageLog, Setting

class ModelTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

    def tearDown(self):
        db.drop_all()
        self.ctx.pop()

    def test_user_password_hashing(self):
        u = User(email='test@tshienda.co.za', name='Test User')
        u.set_password('SecretPass123!')
        self.assertTrue(u.check_password('SecretPass123!'))
        self.assertFalse(u.check_password('WrongPass'))

    def test_user_lockout_mechanism(self):
        u = User(email='lockout@tshienda.co.za', name='Lockout User')
        u.set_password('Secret123!')
        db.session.add(u)
        db.session.commit()

        self.assertFalse(u.is_locked())
        for _ in range(5):
            u.record_failed_login(max_attempts=5, lockout_minutes=15)
        self.assertTrue(u.is_locked())
        u.reset_failed_logins()
        self.assertFalse(u.is_locked())

    def test_order_generation_and_progression(self):
        c = Customer(name='Student One', phone='27821112233', consent_flag=True)
        db.session.add(c)
        db.session.commit()

        code = Order.generate_order_number()
        self.assertTrue(code.startswith('TSH-'))
        self.assertEqual(len(code), 9)

        order = Order(
            order_number=code, customer_id=c.id, service='standard',
            pairs=1, price=100.0, stage='dropped_off'
        )
        db.session.add(order)
        db.session.commit()

        self.assertEqual(order.stage_display, 'Dropped off')
        self.assertEqual(order.next_stage, 'washing')
        self.assertTrue(order.can_advance)

        order.advance_stage()
        self.assertEqual(order.stage, 'washing')
        self.assertEqual(order.next_stage, 'drying')

if __name__ == '__main__':
    unittest.main()
