"""Authentication routes with rate limiting and lockout protection."""
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from app.models import User
from app.auth.forms import LoginForm
from app.utils.rate_limiter import rate_limit

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login', methods=['GET', 'POST'])
@rate_limit(max_requests=5, window_seconds=60)
def login():
    if current_user.is_authenticated:
        return redirect(url_for('staff.dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        password = form.password.data
        user = User.query.filter_by(email=email).first()

        if user:
            if user.is_locked():
                remaining_minutes = max(1, int((user.lockout_until - datetime.utcnow()).total_seconds() // 60) + 1)
                flash(
                    f"Account temporarily locked due to multiple failed login attempts. "
                    f"Please try again in {remaining_minutes} minute(s) or contact the owner.",
                    "danger"
                )
                return render_template('staff/login.html', form=form)

            if user.check_password(password):
                user.reset_failed_logins()
                login_user(user, remember=form.remember.data)
                flash(f"Welcome back, {user.name}! Signed in as {user.role.capitalize()}.", "success")
                next_page = request.args.get('next')
                if next_page and next_page.startswith('/'):
                    return redirect(next_page)
                return redirect(url_for('staff.dashboard'))
            else:
                user.record_failed_login(
                    max_attempts=current_app.config.get('MAX_FAILED_LOGINS', 5),
                    lockout_minutes=current_app.config.get('LOCKOUT_DURATION_MINUTES', 15)
                )
                attempts_left = max(0, current_app.config.get('MAX_FAILED_LOGINS', 5) - user.failed_login_attempts)
                if attempts_left > 0:
                    flash(f"Invalid credentials. {attempts_left} attempt(s) remaining before temporary lockout.", "danger")
                else:
                    flash("Account locked for 15 minutes due to too many failed attempts.", "danger")
        else:
            flash("Invalid email or password.", "danger")

    return render_template('staff/login.html', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have been securely signed out.", "info")
    return redirect(url_for('auth.login'))
