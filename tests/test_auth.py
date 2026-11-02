"""Unit tests for staff authentication and lockout."""
import unittest
from app import create_app
from app.extensions import db
from app.models import User

class AuthTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        self.user = User(email='staff@tshienda.co.za', name='Staff User', role='staff')
        self.user.set_password('Password2026!')
        db.session.add(self.user)
        db.session.commit()

    def tearDown(self):
        db.drop_all()
        self.ctx.pop()

    def test_login_success(self):
        resp = self.client.post('/auth/login', data={
            'email': 'staff@tshienda.co.za',
            'password': 'Password2026!'
        })
        self.assertIn(resp.status_code, [200, 302])

    def test_login_invalid_password(self):
        resp = self.client.post('/auth/login', data={
            'email': 'staff@tshienda.co.za',
            'password': 'WrongPassword!'
        })
        self.assertEqual(resp.status_code, 200)
        u = User.query.filter_by(email='staff@tshienda.co.za').first()
        self.assertEqual(u.failed_login_attempts, 1)

if __name__ == '__main__':
    unittest.main()
