from flask import Blueprint, render_template, redirect, url_for, request, jsonify, session
from flask_login import login_user, logout_user, current_user, login_required
from app import db
from app.models import User, Product, ExpiryWarningRead, ExpiryWarningDismissed
from app.forms import LoginForm, RegisterForm, ProductForm, ProductRegisterForm
from datetime import datetime, timedelta

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')
main_bp = Blueprint('main', __name__)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    form = RegisterForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html', form=form)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            return redirect(url_for('main.dashboard'))

    return render_template('auth/login.html', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

@main_bp.route('/')
@login_required
def dashboard():
    products = Product.query.filter_by(user_id=current_user.id).order_by(Product.added_at.desc()).all()

    expiry_warnings = []
    for product in products:
        if product.expiry_date:
            days_until_expiry = (product.expiry_date - datetime.now().date()).days
            if 0 <= days_until_expiry <= 7:
                expiry_warnings.append({
                    'product': product.name,
                    'days': days_until_expiry
                })

    return render_template('dashboard.html', products=products, warnings=expiry_warnings)

@main_bp.route('/product')
@login_required
def product_hub():
    return render_template('product/index.html')

@main_bp.route('/products')
@login_required
def all_products():
    products = Product.query.filter_by(user_id=current_user.id).order_by(Product.added_at.desc()).all()
    return render_template('product/list.html', products=products)

@main_bp.route('/product/register', methods=['GET', 'POST'])
@main_bp.route('/product/add', methods=['GET', 'POST'])
@login_required
def add_product():
    form = ProductRegisterForm()
    if form.validate_on_submit():
        product = Product(
            user_id=current_user.id,
            name=form.name.data,
            expiry_date=form.expiry_date.data,
            description=f'Productcode: {form.product_code.data} | Geregistreerd via dummy QR-scan'
        )
        db.session.add(product)
        db.session.commit()
        return redirect(url_for('main.all_products'))

    return render_template('product/register.html', form=form)

@main_bp.route('/notifications/expiry-warning/<int:product_id>/read', methods=['POST'])
@login_required
def mark_expiry_warning_read(product_id):
    product = Product.query.filter_by(id=product_id, user_id=current_user.id).first_or_404()

    if product.expiry_date:
        days_until_expiry = (product.expiry_date - datetime.now().date()).days
        if 0 <= days_until_expiry <= 7:
            existing_read = ExpiryWarningRead.query.filter_by(
                user_id=current_user.id,
                product_id=product.id
            ).first()

            if not existing_read:
                db.session.add(ExpiryWarningRead(user_id=current_user.id, product_id=product.id))

    db.session.commit()
    unread_count = 0
    products = Product.query.filter_by(user_id=current_user.id).all()
    for item in products:
        if not item.expiry_date:
            continue

        days_until_expiry = (item.expiry_date - datetime.now().date()).days
        if 0 <= days_until_expiry <= 7:
            dismissed_entry = ExpiryWarningDismissed.query.filter_by(
                user_id=current_user.id,
                product_id=item.id
            ).first()
            if dismissed_entry:
                continue

            read_entry = ExpiryWarningRead.query.filter_by(
                user_id=current_user.id,
                product_id=item.id
            ).first()
            if not read_entry:
                unread_count += 1

    return jsonify({'status': 'success', 'unread_count': unread_count})

@main_bp.route('/notifications/expiry-warning/<int:product_id>/dismiss', methods=['POST'])
@login_required
def dismiss_expiry_warning(product_id):
    product = Product.query.filter_by(id=product_id, user_id=current_user.id).first_or_404()

    if product.expiry_date:
        days_until_expiry = (product.expiry_date - datetime.now().date()).days
        if 0 <= days_until_expiry <= 7:
            existing_dismissed = ExpiryWarningDismissed.query.filter_by(
                user_id=current_user.id,
                product_id=product.id
            ).first()

            if not existing_dismissed:
                db.session.add(ExpiryWarningDismissed(user_id=current_user.id, product_id=product.id))
                db.session.commit()

    active_count = 0
    unread_count = 0
    products = Product.query.filter_by(user_id=current_user.id).all()
    for item in products:
        if not item.expiry_date:
            continue

        days_until_expiry = (item.expiry_date - datetime.now().date()).days
        if 0 <= days_until_expiry <= 7:
            dismissed_entry = ExpiryWarningDismissed.query.filter_by(
                user_id=current_user.id,
                product_id=item.id
            ).first()
            if dismissed_entry:
                continue

            active_count += 1
            read_entry = ExpiryWarningRead.query.filter_by(
                user_id=current_user.id,
                product_id=item.id
            ).first()
            if not read_entry:
                unread_count += 1

    return jsonify({'status': 'success', 'active_count': active_count, 'unread_count': unread_count})

@main_bp.route('/product/<int:product_id>')
@login_required
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    if product.user_id != current_user.id:
        return redirect(url_for('main.dashboard'))

    return render_template('product/detail.html', product=product)

@main_bp.route('/product/<int:product_id>/delete', methods=['POST'])
@login_required
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    if product.user_id != current_user.id:
        return redirect(url_for('main.dashboard'))

    db.session.delete(product)
    db.session.commit()
    return redirect(url_for('main.dashboard'))

@main_bp.route('/product/<int:product_id>/favorite', methods=['POST'])
@login_required
def toggle_favorite(product_id):
    product = Product.query.get_or_404(product_id)
    if product.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    if product in current_user.favorites:
        current_user.favorites.remove(product)
    else:
        current_user.favorites.append(product)

    db.session.commit()
    return jsonify({'status': 'success', 'is_favorite': product in current_user.favorites})

@main_bp.route('/theme/<theme>', methods=['POST'])
@login_required
def set_theme(theme):
    if theme in ['light', 'dark']:
        current_user.theme = theme
        session['theme'] = theme
        db.session.commit()
        return jsonify({'status': 'success'})
    return jsonify({'error': 'Invalid theme'}), 400

@main_bp.route('/settings')
@login_required
def settings():
    return render_template('settings.html')

@main_bp.route('/customer-service')
@login_required
def customer_service():
    return render_template('customer_service.html')

@main_bp.route('/faq')
@login_required
def faq():
    return render_template('faq.html')
