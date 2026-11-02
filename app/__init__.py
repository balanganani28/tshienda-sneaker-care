"""App factory for Tshienda Sneaker Care."""
import sys, os

basedir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if basedir not in sys.path:
    sys.path.insert(0, basedir)

if 'flask' not in sys.modules:
    try:
        import flask
    except ImportError:
        try:
            import compat
        except ImportError:
            from app import compat

from flask import Flask, render_template
try:
    from config import config_by_name, Config
except ImportError:
    from app.config import config_by_name, Config

from app.extensions import db, login_manager, bcrypt, csrf

def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_CONFIG', 'default')

    app = Flask(__name__, static_folder='static', template_folder='templates')
    cfg = config_by_name.get(config_name, Config)
    if isinstance(cfg, type): app.config.from_object(cfg)
    else: app.config.update(cfg)

    db.init_app(app)
    login_manager.init_app(app)
    bcrypt.init_app(app)
    csrf.init_app(app)

    from app.auth.routes import auth_bp
    from app.staff.routes import staff_bp
    from app.public.routes import public_bp
    from app.api.routes import api_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(staff_bp)
    app.register_blueprint(api_bp)

    @app.errorhandler(400)
    def err_400(e): return render_template('errors/400.html'), 400
    @app.errorhandler(404)
    def err_404(e): return render_template('errors/404.html'), 404
    @app.errorhandler(429)
    def err_429(e): return render_template('errors/429.html'), 429
    @app.errorhandler(500)
    def err_500(e): return render_template('errors/500.html'), 500

    @app.context_processor
    def inject_globals():
        return {
            'brand_name': 'Tshienda',
            'tagline': 'Sneaker care with real time order tracking.',
            'campus_name': app.config.get('CAMPUS_NAME', 'University of the Western Cape (UWC)'),
            'location_note': app.config.get('LOCATION_NOTE', 'Student Centre Kiosk, Bellville, Cape Town'),
            'current_year': 2026,
            'cloud_api_enabled': app.config.get('WHATSAPP_CLOUD_API_ENABLED', False)
        }

    with app.app_context():
        try: db.create_all()
        except Exception: pass

    return app
