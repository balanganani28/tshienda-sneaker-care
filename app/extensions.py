"""Extensions module for Tshienda application."""
import sys, os

if 'flask' not in sys.modules:
    try:
        import flask
    except ImportError:
        try:
            import compat
        except ImportError:
            from app import compat

from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_wtf import CSRFProtect

db = SQLAlchemy()
login_manager = LoginManager()
bcrypt = Bcrypt()
csrf = CSRFProtect()

login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in with your staff account to continue.'
login_manager.login_message_category = 'warning'
