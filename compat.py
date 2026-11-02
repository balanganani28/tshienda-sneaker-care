"""
Compatibility module for Tshienda Sneaker Care.
Auto-injects standard-library + Jinja2 + sqlite3 implementations of Flask,
SQLAlchemy, Flask-Login, Flask-Bcrypt, Flask-WTF, and WTForms if missing.
"""
import sys, os, re, io, json, time, hmac, hashlib, secrets, sqlite3, datetime, urllib.parse
from functools import wraps
from jinja2 import Environment, FileSystemLoader, select_autoescape

class Bcrypt:
    def __init__(self, app=None):
        self.app = app
        if app: self.init_app(app)
    def init_app(self, app):
        self.app = app
        app.extensions = getattr(app, 'extensions', {})
        app.extensions['bcrypt'] = self
    def generate_password_hash(self, password: str, rounds: int = 12) -> bytes:
        if isinstance(password, str): password = password.encode('utf-8')
        salt = os.urandom(16)
        dk = hashlib.pbkdf2_hmac('sha256', password, salt, 100000)
        return ("$pbkdf2-sha256$" + salt.hex() + "$" + dk.hex()).encode('utf-8')
    def check_password_hash(self, pw_hash: str | bytes, password: str | bytes) -> bool:
        if isinstance(pw_hash, bytes): pw_hash = pw_hash.decode('utf-8')
        if isinstance(password, str): password = password.encode('utf-8')
        parts = pw_hash.split('$')
        if len(parts) == 4 and parts[1] == 'pbkdf2-sha256':
            salt = bytes.fromhex(parts[2])
            expected = parts[3]
            dk = hashlib.pbkdf2_hmac('sha256', password, salt, 100000)
            return hmac.compare_digest(dk.hex(), expected)
        try:
            import bcrypt as _real_bcrypt
            return _real_bcrypt.checkpw(password, pw_hash.encode('utf-8'))
        except Exception:
            return False

class UserMixin:
    @property
    def is_active(self): return True
    @property
    def is_authenticated(self): return True
    @property
    def is_anonymous(self): return False
    def get_id(self): return str(getattr(self, 'id', ''))

class AnonymousUser(UserMixin):
    @property
    def is_authenticated(self): return False
    @property
    def is_anonymous(self): return True
    def get_id(self): return None

_anon_user = AnonymousUser()

class CurrentUserProxy:
    def __getattr__(self, name):
        flk = sys.modules.get('flask')
        if flk and hasattr(flk, 'g') and hasattr(flk.g, '_login_user'):
            return getattr(flk.g._login_user, name)
        return getattr(_anon_user, name)
    def __bool__(self): return self.is_authenticated

current_user = CurrentUserProxy()

class LoginManager:
    def __init__(self, app=None):
        self.app = app
        self._user_callback = None
        self.login_view = 'auth.login'
        self.login_message = 'Please log in to continue.'
        self.login_message_category = 'warning'
        if app: self.init_app(app)
    def init_app(self, app):
        self.app = app
        app.login_manager = self
    def user_loader(self, cb):
        self._user_callback = cb
        return cb
    def load_user(self, uid):
        return self._user_callback(uid) if self._user_callback else None

def login_user(user, remember=False, duration=None, force=False, fresh=True):
    flk = sys.modules.get('flask')
    if flk:
        flk.session['_user_id'] = str(user.get_id())
        if hasattr(flk, 'g'): flk.g._login_user = user
    return True

def logout_user():
    flk = sys.modules.get('flask')
    if flk:
        flk.session.pop('_user_id', None)
        if hasattr(flk, 'g'): flk.g._login_user = AnonymousUser()
    return True

def login_required(func):
    @wraps(func)
    def decorated_view(*args, **kwargs):
        flk = sys.modules.get('flask')
        if not current_user.is_authenticated:
            if flk:
                flk.flash('Please log in with your staff account to continue.', 'warning')
                nxt = flk.request.url if hasattr(flk, 'request') else ''
                return flk.redirect(flk.url_for('auth.login', next=nxt))
            return "Unauthorized", 401
        return func(*args, **kwargs)
    return decorated_view


class Label:
    def __init__(self, text, field_id=""):
        self.text = text
        self.field_id = field_id
    def __str__(self): return self.text
    def __call__(self, **attrs):
        c = attrs.get('class_', attrs.get('class', ''))
        cs = f' class="{c}"' if c else ''
        return f'<label for="{self.field_id}"{cs}>{self.text}</label>'

class ValidationError(Exception): pass
class DataRequired:
    def __init__(self, message=None): self.message = message or 'This field is required.'
    def __call__(self, form, field):
        if field.data is None or (isinstance(field.data, str) and not field.data.strip()):
            raise ValidationError(self.message)
class Optional:
    def __init__(self, strip_whitespace=True): self.strip_whitespace = strip_whitespace
    def __call__(self, form, field): pass
class Length:
    def __init__(self, min=-1, max=-1, message=None):
        self.min = min; self.max = max; self.message = message
    def __call__(self, form, field):
        l = len(field.data or '')
        if (self.min >= 0 and l < self.min) or (self.max >= 0 and l > self.max):
            raise ValidationError(self.message or f"Length must be between {self.min} and {self.max}.")
class Email:
    def __init__(self, message=None): self.message = message or 'Invalid email address.'
    def __call__(self, form, field):
        v = str(field.data or '').strip()
        if v and ('@' not in v or '.' not in v.split('@')[-1]): raise ValidationError(self.message)
class NumberRange:
    def __init__(self, min=None, max=None, message=None):
        self.min = min; self.max = max; self.message = message
    def __call__(self, form, field):
        d = field.data
        if d is not None:
            if self.min is not None and d < self.min: raise ValidationError(self.message or f"Min {self.min}")
            if self.max is not None and d > self.max: raise ValidationError(self.message or f"Max {self.max}")

class Field:
    def __init__(self, label='', validators=None, default=None, **kwargs):
        self.name = ''; self.label = Label(label, self.name); self.validators = validators or []; self.default = default
        self.data = default; self.raw_data = None; self.errors = []; self.kwargs = kwargs
    def process(self, formdata=None, data=None):
        if data is not None: self.data = data
        elif formdata is not None and self.name in formdata:
            self.raw_data = formdata.get(self.name)
            self.data = self._coerce(self.raw_data)
        else: self.data = self.default
    def _coerce(self, val): return val
    def validate(self, form):
        self.errors = []
        for v in self.validators:
            try: v(form, self)
            except ValidationError as e: self.errors.append(str(e))
        meth = getattr(form, f"validate_{self.name}", None)
        if meth:
            try: meth(self)
            except ValidationError as e: self.errors.append(str(e))
        return len(self.errors) == 0
    def __call__(self, **html_attrs):
        attrs = [f'{("class" if k=="class_" else k)}="{v}"' for k,v in {**self.kwargs, **html_attrs}.items()]
        attr_s = (' ' + ' '.join(attrs)) if attrs else ''
        val = '' if self.data is None else str(self.data)
        itype = getattr(self, '_input_type', 'text')
        return f'<input type="{itype}" name="{self.name}" id="{self.name}" value="{val}"{attr_s}>'

class StringField(Field): _input_type = 'text'
class PasswordField(Field):
    _input_type = 'password'
    def __call__(self, **html_attrs):
        attrs = [f'{("class" if k=="class_" else k)}="{v}"' for k,v in {**self.kwargs, **html_attrs}.items()]
        attr_s = (' ' + ' '.join(attrs)) if attrs else ''
        return f'<input type="password" name="{self.name}" id="{self.name}"{attr_s}>'
class IntegerField(Field):
    _input_type = 'number'
    def _coerce(self, val):
        try: return int(val)
        except Exception: return None
class BooleanField(Field):
    _input_type = 'checkbox'
    def _coerce(self, val): return bool(val and val not in ('0', 'false', 'False'))
    def __call__(self, **html_attrs):
        chk = ' checked' if self.data else ''
        attrs = [f'{("class" if k=="class_" else k)}="{v}"' for k,v in {**self.kwargs, **html_attrs}.items()]
        attr_s = (' ' + ' '.join(attrs)) if attrs else ''
        return f'<input type="checkbox" name="{self.name}" id="{self.name}" value="y"{chk}{attr_s}>'
class TextAreaField(Field):
    def __call__(self, **html_attrs):
        attrs = [f'{("class" if k=="class_" else k)}="{v}"' for k,v in {**self.kwargs, **html_attrs}.items()]
        attr_s = (' ' + ' '.join(attrs)) if attrs else ''
        val = '' if self.data is None else str(self.data)
        return f'<textarea name="{self.name}" id="{self.name}"{attr_s}>{val}</textarea>'
class SelectField(Field):
    def __init__(self, label='', validators=None, choices=None, default=None, **kwargs):
        super().__init__(label, validators, default, **kwargs)
        self.choices = choices or []
    def __call__(self, **html_attrs):
        attrs = [f'{("class" if k=="class_" else k)}="{v}"' for k,v in {**self.kwargs, **html_attrs}.items()]
        attr_s = (' ' + ' '.join(attrs)) if attrs else ''
        opts = [f'<option value="{val}"{" selected" if str(self.data)==str(val) else ""}>{lbl}</option>' for val, lbl in self.choices]
        return f'<select name="{self.name}" id="{self.name}"{attr_s}>{"".join(opts)}</select>'
class SubmitField(Field):
    _input_type = 'submit'
    def __call__(self, **html_attrs):
        v = self.label or 'Submit'
        attrs = [f'{("class" if k=="class_" else k)}="{v}"' for k,v in {**self.kwargs, **html_attrs}.items()]
        attr_s = (' ' + ' '.join(attrs)) if attrs else ''
        return f'<button type="submit" name="{self.name}" id="{self.name}"{attr_s}>{v}</button>'

class CSRFProtect:
    def __init__(self, app=None):
        if app: self.init_app(app)
    def init_app(self, app): pass

class FlaskForm:
    def __init__(self, formdata=None, obj=None, data=None, **kwargs):
        flk = sys.modules.get('flask')
        if formdata is None and flk and hasattr(flk, 'request') and flk.request.method in ('POST', 'PUT', 'PATCH'):
            formdata = flk.request.form
        self._fields = {}; self.errors = {}; self.formdata = formdata
        for name in dir(self.__class__):
            attr = getattr(self.__class__, name)
            if isinstance(attr, Field):
                fc = attr.__class__(label=attr.label, validators=attr.validators, default=attr.default, **getattr(attr, 'kwargs', {}))
                if hasattr(attr, 'choices'): fc.choices = attr.choices
                fc.name = name
                setattr(self, name, fc)
                self._fields[name] = fc
        for name, fld in self._fields.items():
            fd = getattr(obj, name, None) if (obj and hasattr(obj, name)) else kwargs.get(name)
            fld.process(formdata, fd)
    def hidden_tag(self):
        flk = sys.modules.get('flask')
        token = ''
        if flk and hasattr(flk, 'session'):
            if '_csrf_token' not in flk.session: flk.session['_csrf_token'] = secrets.token_hex(16)
            token = flk.session['_csrf_token']
        return f'<input type="hidden" name="csrf_token" value="{token}">'
    def validate(self):
        valid = True
        self.errors = {}
        for name, fld in self._fields.items():
            if not fld.validate(self):
                self.errors[name] = fld.errors
                valid = False
        return valid
    def validate_on_submit(self):
        flk = sys.modules.get('flask')
        if flk and hasattr(flk, 'request') and flk.request.method in ('POST', 'PUT', 'PATCH'):
            return self.validate()
        return False

class Column:
    def __init__(self, col_type, *args, primary_key=False, unique=False, nullable=True, default=None, index=False):
        self.type = col_type; self.primary_key = primary_key; self.unique = unique
        self.nullable = nullable; self.default = default; self.index = index; self.name = None; self.foreign_key = None
        for a in args:
            if isinstance(a, ForeignKey): self.foreign_key = a
class Integer: pass
class String:
    def __init__(self, length=255, *args, **kwargs): self.length = length
class Text: pass
class Boolean: pass
class DateTime: pass
class Float: pass
class ForeignKey:
    def __init__(self, target): self.target = target

class Relationship:
    def __init__(self, target, backref=None, lazy='dynamic', cascade=None, order_by=None, **kwargs):
        self.target = target
        self.backref = backref
        self.lazy = lazy
        self.cascade = cascade
        self.order_by = order_by
        self.kwargs = kwargs

    def __get__(self, instance, owner):
        if instance is None: return self
        target_cls = ModelMeta._registry.get(self.target)
        if not target_cls: return []
        my_table = instance.__tablename__
        fk_col = None
        for c_name, c_obj in target_cls._columns.items():
            if c_obj.foreign_key and c_obj.foreign_key.target.startswith(my_table + '.'):
                fk_col = c_name
                break
        if fk_col:
            my_id = getattr(instance, 'id', None)
            q = target_cls.query.filter_by(**{fk_col: my_id})
            if self.order_by: q = q.order_by(self.order_by)
            return q if self.lazy == 'dynamic' else q.all()
        return []

def relationship(target, **kwargs): return Relationship(target, **kwargs)

class ModelMeta(type):
    _registry = {}
    def __new__(cls, name, bases, attrs):
        if name == 'Model': return super().__new__(cls, name, bases, attrs)
        t_name = attrs.get('__tablename__', name.lower())
        cols = {k: v for k, v in attrs.items() if isinstance(v, Column)}
        rels = {k: v for k, v in attrs.items() if isinstance(v, Relationship)}
        for k, v in cols.items(): v.name = k
        attrs['__tablename__'] = t_name; attrs['_columns'] = cols; attrs['_relationships'] = rels
        new_cls = super().__new__(cls, name, bases, attrs)
        new_cls.query = QueryProperty(new_cls)
        cls._registry[t_name] = new_cls; cls._registry[name] = new_cls
        return new_cls

class QueryProperty:
    def __init__(self, m): self.m = m
    def __get__(self, ins, owner): return BaseQuery(owner)

class BaseQuery:
    def __init__(self, model_cls, criteria=None, orderings=None, limit_val=None):
        self.model_cls = model_cls; self.criteria = list(criteria or []); self.orderings = list(orderings or []); self.limit_val = limit_val
    def filter_by(self, **kwargs):
        c = list(self.criteria)
        for k, v in kwargs.items(): c.append((k, '=', v))
        return BaseQuery(self.model_cls, c, self.orderings, self.limit_val)
    def filter(self, *exprs):
        c = list(self.criteria)
        for e in exprs: c.append(e)
        return BaseQuery(self.model_cls, c, self.orderings, self.limit_val)
    def order_by(self, *ords):
        o = list(self.orderings)
        for ord_spec in ords: o.append(str(ord_spec))
        return BaseQuery(self.model_cls, self.criteria, o, self.limit_val)
    def limit(self, n): return BaseQuery(self.model_cls, self.criteria, self.orderings, n)
    def _execute(self):
        db = self.model_cls._db; conn = db.get_connection(); t = self.model_cls.__tablename__
        sql = f'SELECT * FROM "{t}"'; params = []; wheres = []
        for crit in self.criteria:
            if isinstance(crit, tuple) and len(crit) == 3:
                col, op, val = crit
                if val is None and op == '=': wheres.append(f"{col} IS NULL")
                elif val is None and op == '!=': wheres.append(f"{col} IS NOT NULL")
                else: wheres.append(f"{col} {op} ?"); params.append(db._adapt(val))
        if wheres: sql += " WHERE " + " AND ".join(wheres)
        if self.orderings: sql += " ORDER BY " + ", ".join(self.orderings)
        if self.limit_val is not None: sql += f" LIMIT {int(self.limit_val)}"
        cur = conn.cursor(); cur.execute(sql, params); rows = cur.fetchall()
        c_names = [d[0] for d in cur.description] if cur.description else []
        objs = []
        for r in rows:
            obj = self.model_cls(); rd = dict(zip(c_names, r))
            for k, c in self.model_cls._columns.items():
                setattr(obj, k, db._restore(c.type, rd.get(k)))
            obj._persisted = True
            if obj not in db._active_objects: db._active_objects.append(obj)
            objs.append(obj)
        for crit in self.criteria:
            if callable(crit): objs = [o for o in objs if crit(o)]
        return objs
    def all(self): return self._execute()
    def first(self):
        r = self.limit(1)._execute()
        return r[0] if r else None
    def get(self, ident):
        return self.filter_by(id=ident).first() if ident is not None else None
    def get_or_404(self, ident):
        res = self.get(ident)
        if res is None: abort(404)
        return res
    def count(self): return len(self._execute())
    def __iter__(self): return iter(self._execute())

class Model(metaclass=ModelMeta):
    _db = None; _persisted = False
    def __init__(self, **kwargs):
        for k, c in getattr(self, '_columns', {}).items():
            if k in kwargs: setattr(self, k, kwargs[k])
            elif c.default is not None: setattr(self, k, c.default() if callable(c.default) else c.default)
            else: setattr(self, k, None)
        for k, v in kwargs.items():
            if k not in getattr(self, '_columns', {}): setattr(self, k, v)
    def __getattr__(self, item):
        rels = getattr(self, '_relationships', {})
        if item in rels:
            rel = rels[item]; target_cls = ModelMeta._registry.get(rel.target)
            if target_cls:
                my_table = self.__tablename__; fk_col = None
                for c_name, c_obj in target_cls._columns.items():
                    if c_obj.foreign_key and c_obj.foreign_key.target.startswith(my_table + '.'):
                        fk_col = c_name; break
                if fk_col:
                    my_id = getattr(self, 'id', None)
                    q = target_cls.query.filter_by(**{fk_col: my_id})
                    if rel.order_by: q = q.order_by(rel.order_by)
                    return q if rel.lazy == 'dynamic' else q.all()
        fk_attr = f"{item}_id"
        if fk_attr in getattr(self, '_columns', {}):
            fk_val = getattr(self, fk_attr, None)
            if fk_val is not None:
                t_cls = ModelMeta._registry.get(item) or ModelMeta._registry.get(item.capitalize())
                if t_cls: return t_cls.query.get(fk_val)
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{item}'")

class Session:
    def __init__(self, db): self.db = db; self._new = []; self._deleted = []
    def add(self, obj):
        if obj not in self._new and not getattr(obj, '_persisted', False): self._new.append(obj)
    def delete(self, obj):
        if obj in self._new: self._new.remove(obj)
        elif getattr(obj, '_persisted', False): self._deleted.append(obj)
    def commit(self):
        conn = self.db.get_connection(); cur = conn.cursor()
        for obj in list(self._new):
            t = obj.__tablename__; cols, vals, params = [], [], []
            for col_name, c in obj._columns.items():
                val = getattr(obj, col_name, None)
                if col_name == 'id' and val is None: continue
                cols.append(col_name); vals.append('?'); params.append(self.db._adapt(val))
            cols_s = ",".join(cols)
            vals_s = ",".join(vals)
            sql = f'INSERT INTO "{t}" ({cols_s}) VALUES ({vals_s})'
            cur.execute(sql, params); obj.id = cur.lastrowid; obj._persisted = True
            if obj not in self.db._active_objects: self.db._active_objects.append(obj)
        self._new.clear()
        for obj in list(self.db._active_objects):
            if getattr(obj, '_persisted', False) and getattr(obj, 'id', None):
                t = obj.__tablename__; set_c, params = [], []
                for col_name, c in obj._columns.items():
                    if col_name == 'id': continue
                    set_c.append(f"{col_name} = ?"); params.append(self.db._adapt(getattr(obj, col_name, None)))
                params.append(obj.id)
                set_s = ",".join(set_c)
                cur.execute(f'UPDATE "{t}" SET {set_s} WHERE id = ?', params)
        for obj in self._deleted:
            if getattr(obj, 'id', None):
                cur.execute(f'DELETE FROM "{obj.__tablename__}" WHERE id = ?', (obj.id,))
                if obj in self.db._active_objects: self.db._active_objects.remove(obj)
        self._deleted.clear(); conn.commit()
    def rollback(self):
        self.db.get_connection().rollback(); self._new.clear(); self._deleted.clear()

class SQLAlchemy:
    def __init__(self, app=None):
        self.app = app; self._conn = None; self.Model = Model; self.Model._db = self
        self.Column = Column; self.Integer = Integer; self.String = String; self.Text = Text
        self.Boolean = Boolean; self.DateTime = DateTime; self.Float = Float
        self.ForeignKey = ForeignKey; self.relationship = relationship
        self._active_objects = []; self.session = Session(self)
        if app: self.init_app(app)
    def init_app(self, app):
        self.app = app
        app.extensions = getattr(app, 'extensions', {})
        app.extensions['sqlalchemy'] = self
    def _get_db_path(self):
        uri = 'tshienda.db'
        if self.app and 'SQLALCHEMY_DATABASE_URI' in self.app.config:
            uri = self.app.config['SQLALCHEMY_DATABASE_URI']
        if uri.startswith('sqlite:///'): uri = uri[len('sqlite:///'):]
        # On 9p virtual filesystem mounts, route SQLite to /tmp to avoid kernel locking error
        if os.path.isabs(uri) and uri.startswith('/working_dir'):
            return os.path.join('/tmp', os.path.basename(uri))
        return uri
    def get_connection(self):
        if self._conn is None:
            p = self._get_db_path()
            d = os.path.dirname(p)
            if d: os.makedirs(d, exist_ok=True)
            self._conn = sqlite3.connect(p, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn
    def _adapt(self, val):
        if isinstance(val, (datetime.datetime, datetime.date)): return val.isoformat()
        if isinstance(val, bool): return 1 if val else 0
        return val
    def _restore(self, col_t, val):
        if val is None: return None
        if isinstance(col_t, DateTime) or col_t == DateTime:
            if isinstance(val, str):
                try: return datetime.datetime.fromisoformat(val)
                except Exception: pass
        elif isinstance(col_t, Boolean) or col_t == Boolean: return bool(val)
        elif isinstance(col_t, Float) or col_t == Float: return float(val)
        elif isinstance(col_t, Integer) or col_t == Integer: return int(val)
        return val
    def create_all(self):
        conn = self.get_connection(); cur = conn.cursor()
        for name, cls in ModelMeta._registry.items():
            if name != cls.__tablename__: continue
            t = cls.__tablename__; c_defs = ["id INTEGER PRIMARY KEY AUTOINCREMENT"]
            for col_name, c in cls._columns.items():
                if col_name == 'id': continue
                ts = "TEXT"
                if isinstance(c.type, Integer) or c.type == Integer: ts = "INTEGER"
                elif isinstance(c.type, Float) or c.type == Float: ts = "REAL"
                elif isinstance(c.type, Boolean) or c.type == Boolean: ts = "INTEGER"
                u = " UNIQUE" if c.unique else ""
                c_defs.append(f"{col_name} {ts}{u}")
            c_str = ", ".join(c_defs)
            cur.execute(f'CREATE TABLE IF NOT EXISTS "{t}" ({c_str})')
        conn.commit()
    def drop_all(self):
        conn = self.get_connection(); cur = conn.cursor()
        for name, cls in ModelMeta._registry.items():
            if name == cls.__tablename__: cur.execute(f'DROP TABLE IF EXISTS "{cls.__tablename__}"')
        conn.commit()

class Request:
    def __init__(self, environ=None, method='GET', path='/', args=None, form=None, json_data=None, headers=None, remote_addr='127.0.0.1'):
        self.environ = environ or {}; self.method = method.upper(); self.path = path; self.args = args or {}
        self.form = form or {}; self._json = json_data; self.headers = headers or {}; self.cookies = {}
        self.remote_addr = remote_addr; self.endpoint = None; self.referrer = self.headers.get('Referer')
    @property
    def is_json(self): return 'application/json' in self.headers.get('Content-Type', '')
    def get_json(self, force=False, silent=False): return self._json
    @property
    def host_url(self): return "http://127.0.0.1:5000/"
    @property
    def url(self):
        q = urllib.parse.urlencode(self.args)
        return self.path + (('?' + q) if q else '')

class Response:
    def __init__(self, response=b'', status=200, headers=None, mimetype='text/html'):
        self.status_code = status; self.headers = headers or {}; self.mimetype = mimetype
        if isinstance(response, str): self.data = response.encode('utf-8')
        elif isinstance(response, bytes): self.data = response
        else: self.data = b''.join(r.encode('utf-8') if isinstance(r, str) else r for r in response)
        if 'Content-Type' not in self.headers: self.headers['Content-Type'] = f"{self.mimetype}; charset=utf-8"
    def set_cookie(self, k, v='', max_age=None, path='/', secure=False, httponly=False, samesite=None):
        c = f"{k}={v}; Path={path}"
        if max_age: c += f"; Max-Age={max_age}"
        if secure: c += "; Secure"
        if httponly: c += "; HttpOnly"
        if samesite: c += f"; SameSite={samesite}"
        self.headers['Set-Cookie'] = c

class Blueprint:
    def __init__(self, name, import_name, url_prefix='', template_folder=None, static_folder=None):
        self.name = name; self.import_name = import_name; self.url_prefix = url_prefix.rstrip('/')
        self.routes = []; self._before_request_funcs = []
    def before_request(self, f):
        self._before_request_funcs.append(f)
        return f
    def route(self, rule, methods=None, **options):
        def dec(f):
            self.routes.append((rule, methods or ['GET'], f, options))
            return f
        return dec

class G: pass
class FlaskSession(dict): pass

request = Request()
session = FlaskSession()
g = G()
_current_app_obj = None

class CurrentAppProxy:
    def __getattr__(self, item):
        if _current_app_obj: return getattr(_current_app_obj, item)
        raise RuntimeError("Working outside of application context.")

current_app = CurrentAppProxy()

class AppContext:
    def __init__(self, app): self.app = app
    def __enter__(self):
        global _current_app_obj
        _current_app_obj = self.app
        return self
    def __exit__(self, a, b, c):
        global _current_app_obj
        _current_app_obj = None
    def push(self): return self.__enter__()
    def pop(self): return self.__exit__(None, None, None)


class ConfigDict(dict):
    def from_object(self, obj):
        for k in dir(obj):
            if k.isupper():
                self[k] = getattr(obj, k)

class Flask:
    def __init__(self, import_name, static_folder='static', template_folder='templates'):
        self.import_name = import_name; self.static_folder = static_folder; self.template_folder = template_folder
        self.root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'app'))
        self.config = ConfigDict({

            'SECRET_KEY': 'dev-key', 'DEBUG': True, 'SESSION_COOKIE_HTTPONLY': True, 'SESSION_COOKIE_SAMESITE': 'Lax',
            'CAMPUS_NAME': 'University of the Western Cape (UWC)', 'LOCATION_NOTE': 'Student Centre Kiosk, Bellville, Cape Town'
        })
        self.blueprints = {}; self.url_map = {}; self.route_handlers = []; self.extensions = {}
        self._before_request_funcs = []; self._error_handlers = {}; self._context_processors = []
        self._init_jinja()

    def _init_jinja(self):
        tdirs = [os.path.join(self.root_path, 'templates'), os.path.join(os.path.dirname(__file__), 'app', 'templates')]
        loader = FileSystemLoader([d for d in tdirs if os.path.exists(d)] or self.root_path)
        self.jinja_env = Environment(loader=loader, autoescape=select_autoescape(['html', 'xml']))
        self.jinja_env.globals.update({
            'url_for': url_for, 'get_flashed_messages': get_flashed_messages, 'session': session, 'request': request,
            'current_app': self, 'min': min, 'max': max, 'len': len, 'sum': sum, 'round': round
        })

    def context_processor(self, f):
        self._context_processors.append(f)
        return f

    def app_context(self): return AppContext(self)

    def register_blueprint(self, bp, url_prefix=None):
        prefix = (url_prefix or bp.url_prefix).rstrip('/')
        self.blueprints[bp.name] = bp
        for rule, methods, handler, opts in bp.routes:
            full_rule = prefix + ('/' + rule.lstrip('/') if rule else '')
            if not full_rule: full_rule = '/'
            endpoint = f"{bp.name}.{handler.__name__}"
            self._add_url_rule(full_rule, endpoint, handler, methods, bp_before=bp._before_request_funcs)

    def route(self, rule, methods=None, **options):
        def dec(f):
            endpoint = options.get('endpoint', f.__name__)
            self._add_url_rule(rule, endpoint, f, methods or ['GET'])
            return f
        return dec

    def _add_url_rule(self, rule, endpoint, handler, methods, bp_before=None):
        self.url_map[endpoint] = rule
        rparts, pnames = [], []
        for seg in rule.split('/'):
            if not seg: continue
            if seg.startswith('<') and seg.endswith('>'):
                spec = seg[1:-1]
                pname = spec.split(':', 1)[1] if ':' in spec else spec
                rparts.append(r'(\d+)' if spec.startswith('int:') else r'([^/]+)')
                pnames.append(pname)
            else: rparts.append(re.escape(seg))
        regex = '^/' + '/'.join(rparts) + ('/?$' if rparts else '$')
        self.route_handlers.append((re.compile(regex), [m.upper() for m in methods], endpoint, handler, pnames, bp_before or []))

    def before_request(self, f): self._before_request_funcs.append(f); return f
    def errorhandler(self, code):
        def dec(f): self._error_handlers[code] = f; return f
        return dec

    def test_client(self): return TestClient(self)

    def dispatch_request(self, req):
        global request, session, g
        request = req; req.endpoint = None
        if hasattr(self, 'login_manager'):
            uid = session.get('_user_id')
            g._login_user = self.login_manager.load_user(uid) if uid else AnonymousUser()

        for b_fn in self._before_request_funcs:
            rv = b_fn()
            if rv is not None: return self._make_res(rv)

        if req.path.startswith('/static/'):
            sp = req.path[len('/static/'):]
            sfile = os.path.join(self.root_path, 'static', sp)
            if os.path.exists(sfile) and os.path.isfile(sfile):
                ext = os.path.splitext(sfile)[1].lower()
                mimes = {'.css': 'text/css', '.js': 'application/javascript', '.png': 'image/png', '.jpg': 'image/jpeg', '.ico': 'image/x-icon', '.svg': 'image/svg+xml'}
                with open(sfile, 'rb') as f: return Response(f.read(), 200, mimetype=mimes.get(ext, 'application/octet-stream'))

        for pat, meths, ep, handler, pnames, bp_befores in self.route_handlers:
            m = pat.match(req.path)
            if m:
                req.endpoint = ep
                if req.method not in meths: return Response('Method Not Allowed', 405)
                for bp_bf in bp_befores:
                    rv = bp_bf()
                    if rv is not None: return self._make_res(rv)
                kwargs = dict(zip(pnames, m.groups()))
                try:
                    rv = handler(**kwargs)
                    return self._make_res(rv)
                except Exception as e:
                    if hasattr(e, 'code') and e.code in self._error_handlers:
                        return self._make_res(self._error_handlers[e.code](e))
                    raise e

        if 404 in self._error_handlers:
            return self._make_res(self._error_handlers[404](None))
        return Response('Not Found', 404)

    def _make_res(self, rv):
        if isinstance(rv, Response): return rv
        if isinstance(rv, tuple):
            body, code = rv[0], rv[1]
            hdrs = rv[2] if len(rv) > 2 else {}
            if isinstance(body, Response): body.status_code = code; return body
            return Response(body, code, hdrs)
        if isinstance(rv, (dict, list)): return Response(json.dumps(rv), 200, mimetype='application/json')
        return Response(rv, 200)

    def __call__(self, environ, start_response):
        with self.app_context():
            path = environ.get('PATH_INFO', '/')
            method = environ.get('REQUEST_METHOD', 'GET')
            remote_addr = environ.get('REMOTE_ADDR', '127.0.0.1')
            qs = environ.get('QUERY_STRING', '')
            args = {k: v[0] if len(v) == 1 else v for k, v in urllib.parse.parse_qs(qs).items()}
            form = {}
            json_d = None
            ctype = environ.get('CONTENT_TYPE', '')
            clen = int(environ.get('CONTENT_LENGTH', 0) or 0)
            if clen > 0:
                body = environ['wsgi.input'].read(clen).decode('utf-8', errors='ignore')
                if 'application/json' in ctype:
                    try: json_d = json.loads(body)
                    except Exception: pass
                elif 'application/x-www-form-urlencoded' in ctype:
                    form = {k: v[0] if len(v) == 1 else v for k, v in urllib.parse.parse_qs(body).items()}
            hdrs = {k[5:].replace('_', '-').title(): v for k, v in environ.items() if k.startswith('HTTP_')}
            hdrs['Content-Type'] = ctype
            req = Request(environ, method, path, args, form, json_d, hdrs, remote_addr)
            res = self.dispatch_request(req)
            start_response(f"{res.status_code} OK", list(res.headers.items()))
            return [res.data]

class TestClient:
    def __init__(self, app): self.app = app
    def get(self, path, query_string=None, headers=None):
        req = Request(method='GET', path=path, args=query_string or {}, headers=headers or {})
        with self.app.app_context(): return self.app.dispatch_request(req)
    def post(self, path, data=None, json=None, headers=None):
        h = headers or {}
        if json is not None: h['Content-Type'] = 'application/json'
        req = Request(method='POST', path=path, form=data or {}, json_data=json, headers=h)
        with self.app.app_context(): return self.app.dispatch_request(req)

_flashed = []
def flash(msg, cat='message'): _flashed.append((cat, msg))
def get_flashed_messages(with_categories=False):
    global _flashed
    res = list(_flashed)
    _flashed.clear()
    return res if with_categories else [m for c, m in res]

def render_template(tmpl_name, **context):
    app = _current_app_obj
    if not app: raise RuntimeError("No app context.")
    ctx = dict(context)
    for cp in app._context_processors: ctx.update(cp())
    ctx['current_user'] = current_user
    tmpl = app.jinja_env.get_template(tmpl_name)
    return tmpl.render(**ctx)

def redirect(location, code=302):
    return Response(f'Redirecting to {location}', code, headers={'Location': location})

def url_for(endpoint, **values):
    app = _current_app_obj
    external = values.pop('_external', False)
    prefix = app.config.get('BASE_URL', 'http://127.0.0.1:5000').rstrip('/') if external else ''
    if endpoint == 'static':
        fn = values.get('filename', '')
        return f"{prefix}/static/{fn.lstrip('/')}"
    rule = app.url_map.get(endpoint) if app else None
    if not rule:
        parts = endpoint.split('.')
        action = parts[-1]
        bp = parts[0] if len(parts) > 1 else ''
        if action == 'index': path = '/'
        elif bp == 'public': path = f"/{action}"
        elif bp == 'staff': path = f"/staff/{action}"
        elif bp == 'auth': path = f"/auth/{action}"
        else: path = f"/{endpoint}"
        return prefix + path
    url = rule
    qparams = {}
    for k, v in values.items():
        if f"<{k}>" in url: url = url.replace(f"<{k}>", str(v))
        elif f"<int:{k}>" in url: url = url.replace(f"<int:{k}>", str(v))
        elif f"<string:{k}>" in url: url = url.replace(f"<string:{k}>", str(v))
        else: qparams[k] = v
    if qparams: url += '?' + urllib.parse.urlencode(qparams)
    return prefix + url

def abort(code, desc=''):
    class HTTPExc(Exception):
        def __init__(self, c, d): self.code = c; self.description = d
    raise HTTPExc(code, desc)

def jsonify(*args, **kwargs):
    d = args[0] if args else kwargs
    return Response(json.dumps(d), 200, mimetype='application/json')

def make_response(*args):
    if len(args) == 1:
        rv = args[0]
        return rv if isinstance(rv, Response) else Response(rv)
    return Response(args[0], args[1], args[2] if len(args) > 2 else {})

def inject_shims():
    this_mod = sys.modules.get(__name__) or sys.modules.get('compat')
    if not this_mod: return
    for pkg in ['flask', 'flask_sqlalchemy', 'flask_login', 'flask_bcrypt', 'flask_wtf', 'wtforms', 'wtforms.validators']:
        if pkg not in sys.modules:
            sys.modules[pkg] = this_mod

inject_shims()
