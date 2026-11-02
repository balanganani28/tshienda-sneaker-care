"""Database models for Tshienda Sneaker Care."""
from datetime import datetime, timedelta
import secrets
from app.extensions import db, login_manager, bcrypt
from flask_login import UserMixin

ORDER_STAGES = [
    ('dropped_off', 'Dropped off'),
    ('washing', 'Washing'),
    ('drying', 'Drying'),
    ('ready', 'Ready'),
    ('collected', 'Collected')
]
STAGE_KEYS = [s[0] for s in ORDER_STAGES]
STAGE_MAP = dict(ORDER_STAGES)

SERVICE_CHOICES = [
    ('standard', 'Standard clean (from R100)'),
    ('deep', 'Deep clean (from R150)'),
    ('suede_leather', 'Suede & leather care (from R200)')
]
SERVICE_MAP = {
    'standard': 'Standard Clean',
    'deep': 'Deep Clean',
    'suede_leather': 'Suede & Leather Care'
}

REFERRAL_SOURCES = [
    ('walk_in', 'Walk-in / Campus Centre'),
    ('friend', 'Friend / Word of mouth'),
    ('instagram', 'Instagram (@tshienda)'),
    ('campus_poster', 'Campus poster / Flyer'),
    ('src_event', 'SRC / Campus Event'),
    ('other', 'Other')
]
REFERRAL_MAP = dict(REFERRAL_SOURCES)

@login_manager.user_loader
def load_user(user_id):
    try: return User.query.get(int(user_id))
    except Exception: return None

class User(UserMixin, db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), default='staff', nullable=False)
    failed_login_attempts = db.Column(db.Integer, default=0, nullable=False)
    lockout_until = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def set_password(self, password: str):
        h = bcrypt.generate_password_hash(password)
        self.password_hash = h.decode('utf-8') if isinstance(h, bytes) else str(h)

    def check_password(self, password: str) -> bool:
        if not self.password_hash: return False
        return bcrypt.check_password_hash(self.password_hash, password)

    def is_locked(self) -> bool:
        return bool(self.lockout_until and datetime.utcnow() < self.lockout_until)

    def record_failed_login(self, max_attempts=5, lockout_minutes=15):
        self.failed_login_attempts = (self.failed_login_attempts or 0) + 1
        if self.failed_login_attempts >= max_attempts:
            self.lockout_until = datetime.utcnow() + timedelta(minutes=lockout_minutes)
        db.session.commit()

    def reset_failed_logins(self):
        self.failed_login_attempts = 0
        self.lockout_until = None
        db.session.commit()

    @property
    def is_owner(self) -> bool: return self.role == 'owner'
    def __repr__(self): return f"<User {self.email} ({self.role})>"

class Customer(db.Model):
    __tablename__ = 'customer'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, index=True)
    phone = db.Column(db.String(30), nullable=True)
    phone_anonymized = db.Column(db.Boolean, default=False, nullable=False)
    consent_flag = db.Column(db.Boolean, default=False, nullable=False)
    consent_timestamp = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    orders = db.relationship('Order', backref='customer', lazy='dynamic')

    def anonymize_phone(self):
        self.phone = None
        self.phone_anonymized = True
        db.session.commit()
    def __repr__(self): return f"<Customer {self.name} (ID: {self.id})>"

class Order(db.Model):
    __tablename__ = 'order'
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    service = db.Column(db.String(50), nullable=False)
    pairs = db.Column(db.Integer, default=1, nullable=False)
    price = db.Column(db.Float, nullable=False)
    stage = db.Column(db.String(30), default='dropped_off', nullable=False)
    notes = db.Column(db.Text, nullable=True)
    source = db.Column(db.String(50), default='walk_in', nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    stage_logs = db.relationship('StageLog', backref='order', lazy='dynamic', cascade='all, delete-orphan')

    @property
    def customer(self):
        return Customer.query.get(self.customer_id)

    @classmethod
    def generate_order_number(cls) -> str:
        charset = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        while True:
            code = "TSH-" + "".join(secrets.choice(charset) for _ in range(5))
            if not cls.query.filter_by(order_number=code).first():
                return code

    @property
    def stage_display(self) -> str:
        return STAGE_MAP.get(self.stage, self.stage.replace('_', ' ').title())

    @property
    def stage_index(self) -> int:
        try: return STAGE_KEYS.index(self.stage)
        except ValueError: return 0

    @property
    def service_display(self) -> str:
        return SERVICE_MAP.get(self.service, self.service.replace('_', ' ').title())

    @property
    def source_display(self) -> str:
        return REFERRAL_MAP.get(self.source, (self.source or 'Walk-in').replace('_', ' ').title())

    @property
    def next_stage(self) -> str | None:
        idx = self.stage_index
        return STAGE_KEYS[idx + 1] if idx < len(STAGE_KEYS) - 1 else None

    @property
    def next_stage_display(self) -> str | None:
        nxt = self.next_stage
        return STAGE_MAP.get(nxt) if nxt else None

    @property
    def can_advance(self) -> bool: return self.next_stage is not None

    def advance_stage(self, staff_user=None, notes=None):
        nxt = self.next_stage
        if not nxt: return False, "Order has already reached final stage (Collected)."
        self.stage = nxt
        self.updated_at = datetime.utcnow()
        log = StageLog(
            order_id=self.id,
            stage=nxt,
            user_id=staff_user.id if staff_user else None,
            timestamp=datetime.utcnow(),
            notes=notes or f"Advanced to {STAGE_MAP.get(nxt)}"
        )
        db.session.add(log)
        db.session.commit()
        return True, nxt

    def __repr__(self): return f"<Order {self.order_number} ({self.stage})>"

class StageLog(db.Model):
    __tablename__ = 'stagelog'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    stage = db.Column(db.String(30), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    notes = db.Column(db.String(255), nullable=True)
    staff_user = db.relationship('User', foreign_keys=[user_id])

    @property
    def stage_display(self) -> str:
        return STAGE_MAP.get(self.stage, self.stage.replace('_', ' ').title())

class Setting(db.Model):
    __tablename__ = 'setting'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False, index=True)
    value = db.Column(db.Text, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    @classmethod
    def get(cls, key: str, default: str = "") -> str:
        s = cls.query.filter_by(key=key).first()
        return s.value if s else default

    @classmethod
    def set(cls, key: str, value: str):
        s = cls.query.filter_by(key=key).first()
        if not s:
            s = cls(key=key, value=str(value), updated_at=datetime.utcnow())
            db.session.add(s)
        else:
            s.value = str(value)
            s.updated_at = datetime.utcnow()
        db.session.commit()
        return s
