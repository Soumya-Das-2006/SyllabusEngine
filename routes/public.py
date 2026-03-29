import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import current_user
from extensions import db
from database.models import News, Testimonial, ContactMessage

public_bp = Blueprint('public', __name__)


@public_bp.route('/')
def index():
    latest_news = (News.query
                   .filter_by(is_deleted=False)
                   .filter(~News.title.like('[ARCHIVED] %'))
                   .order_by(News.created_at.desc())
                   .limit(3).all())
    testimonials = (Testimonial.query
                    .filter_by(is_deleted=False)
                    .filter(~Testimonial.name.like('[ARCHIVED] %'))
                    .order_by(Testimonial.created_at.desc())
                    .limit(3).all())
    return render_template('public/index.html', latest_news=latest_news, testimonials=testimonials)


@public_bp.route('/about')
def about():
    return render_template('public/about.html')


@public_bp.route('/services')
def services():
    return render_template('public/services.html')


@public_bp.route('/testimonials')
def testimonials_page():
    testimonials = (Testimonial.query
                    .filter_by(is_deleted=False)
                    .filter(~Testimonial.name.like('[ARCHIVED] %'))
                    .order_by(Testimonial.created_at.desc())
                    .limit(12).all())
    return render_template('public/testimonials.html', testimonials=testimonials)


@public_bp.route('/news')
def news_list():
    page = request.args.get('page', 1, type=int)
    pagination = (News.query
                  .filter_by(is_deleted=False)
                  .filter(~News.title.like('[ARCHIVED] %'))
                  .order_by(News.created_at.desc())
                  .paginate(page=page, per_page=6, error_out=False))
    return render_template('public/news.html', pagination=pagination, news_items=pagination.items)


@public_bp.route('/news/<int:news_id>')
def news_detail(news_id):
    item = News.query.filter(News.id == news_id, News.is_deleted.is_(False), ~News.title.like('[ARCHIVED] %')).first_or_404()
    return render_template('public/news_detail.html', item=item)


def _is_valid_email(value: str) -> bool:
    return bool(value) and '@' in value and '.' in value


@public_bp.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        message = request.form.get('message', '').strip()

        errors = []
        if not name:
            errors.append('Name is required.')
        if not email or not _is_valid_email(email):
            errors.append('A valid email is required.')
        if not message or len(message) < 10:
            errors.append('Message must be at least 10 characters long.')

        if errors:
            for e in errors:
                flash(e, 'error')
            return redirect(url_for('public.contact'))

        cm = ContactMessage(name=name, email=email, message=message)
        db.session.add(cm)
        db.session.commit()
        flash('Thanks for reaching out! We will get back to you soon.', 'success')
        return redirect(url_for('public.contact'))

    return render_template('public/contact.html')
