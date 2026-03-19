from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user, fresh_login_required
from werkzeug.security import check_password_hash
from database.models import User, db
from datetime import datetime
from utils.email import send_password_reset_email, send_verification_email
from utils.tokens import verify_token

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/app')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    return render_template('home.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        remember = 'remember' in request.form
        
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password) and user.is_active:
            login_user(user, remember=remember)
            next_page = request.args.get('next')
            if user.role == 'admin':
                flash('Admin Dashboard Access Granted!', 'success')
                return redirect(next_page or url_for('admin.index'))
            elif user.role == 'student':
                flash('Welcome to Student Dashboard!', 'success')
                return redirect(next_page or url_for('dashboard.index'))
            else:
                logout_user()
                flash('Invalid user role. Contact admin.', 'error')
                return redirect(url_for('auth.login'))
        flash('Invalid email or password.', 'error')
    return render_template('auth/login.html')

@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    # Do not allow already-authenticated users to sign up again
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        email = request.form['email']
        name = request.form['name']
        password = request.form['password']
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'error')
            return render_template('auth/signup.html')
        
        user = User(
            email=email,
            name=name,
            role='student',
            is_admin=False,
            # New accounts require email verification before login
            is_active=False
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        # Send verification email from noreply sender
        send_verification_email(user)
        flash(f'Account created! We sent a verification link to {email}. Please check your inbox (and spam) before logging in.', 'info')
        return redirect(url_for('auth.login'))
    return render_template('auth/signup.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('auth.home'))

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        user = User.query.filter_by(email=email).first()
        if user:
            # Send password reset email with a signed, time-limited token.
            sent = send_password_reset_email(user)
            if not sent:
                current_app.logger.warning('Password reset email could not be sent for %s', email)
        # Always show a generic message to avoid leaking whether the email exists.
        flash('If that email exists, check your inbox shortly.', 'info')
        return redirect(url_for('auth.forgot_password'))
    return render_template('auth/forgot_password.html')

@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    # Validate the signed reset token (24 hour validity)
    data = verify_token(token, 'reset-password', max_age=60 * 60 * 24)
    if not data:
        flash('Invalid or expired reset link.', 'error')
        return redirect(url_for('auth.login'))

    user_id = data.get('uid')
    user = User.query.get(user_id) if user_id is not None else None
    if not user or user.email != data.get('email'):
        flash('Invalid or expired reset link.', 'error')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        password = request.form['password']
        confirm = request.form['confirm_password']
        if password != confirm:
            flash('Passwords do not match.', 'error')
            return render_template('auth/reset_password.html', token=token)
        if len(password) < 8:
            flash('Password must be at least 8 characters.', 'error')
            return render_template('auth/reset_password.html', token=token)
        user.set_password(password)
        db.session.commit()
        flash('Password reset successful! You can now log in.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('auth/reset_password.html', token=token)


@auth_bp.route('/verify-email/<token>')
def verify_email(token):
    """Handle email verification links sent to new users."""
    if current_user.is_authenticated and current_user.is_active:
        return redirect(url_for('dashboard.index'))

    data = verify_token(token, 'verify-email', max_age=60 * 60 * 24)
    if not data:
        flash('Invalid or expired verification link.', 'error')
        return redirect(url_for('auth.login'))

    user_id = data.get('uid')
    user = User.query.get(user_id) if user_id is not None else None
    if not user or user.email != data.get('email'):
        flash('Invalid or expired verification link.', 'error')
        return redirect(url_for('auth.login'))

    if user.is_active:
        flash('Your email is already verified. You can log in.', 'info')
        return redirect(url_for('auth.login'))

    user.is_active = True
    db.session.commit()
    flash('Your email has been verified. You can now log in.', 'success')
    return redirect(url_for('auth.login'))


@auth_bp.route('/resend-verification', methods=['POST'])
def resend_verification():
    """Resend verification email without revealing whether an account exists."""
    email = request.form.get('email')
    if not email:
        flash('Please provide an email address.', 'error')
        return redirect(url_for('auth.login'))

    user = User.query.filter_by(email=email).first()
    if user and not user.is_active:
        send_verification_email(user)

    flash('If an unverified account exists for that email, a new verification link has been sent.', 'info')
    return redirect(url_for('auth.login'))
