from flask import Blueprint, render_template, redirect, url_for, request, jsonify, session
from flask_login import login_user, logout_user, current_user, login_required
from app import db
from app.models import User, Product, ExpiryWarningRead, ExpiryWarningDismissed, ForumTopic, ForumReply, TopicSubscription, ForumNotification, ReplyLike
from app.forms import LoginForm, RegisterForm, ProductForm, ProductRegisterForm, TopicForm, ReplyForm, CheckoutForm
from datetime import datetime, timedelta
from flask import current_app, flash
import json
import xmlrpc.client

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')
main_bp = Blueprint('main', __name__)


def send_order_to_odoo(payment_data):
    odoo_url = current_app.config.get('ODOO_URL', '').strip()
    odoo_db = current_app.config.get('ODOO_DB', '').strip()
    odoo_username = current_app.config.get('ODOO_USERNAME', '').strip()
    odoo_password = current_app.config.get('ODOO_PASSWORD', '').strip()

    if not all([odoo_url, odoo_db, odoo_username, odoo_password]):
        raise RuntimeError('Odoo configuratie ontbreekt. Stel ODOO_URL, ODOO_DB, ODOO_USERNAME en ODOO_PASSWORD in.')

    common = xmlrpc.client.ServerProxy(f'{odoo_url}/xmlrpc/2/common')
    uid = common.authenticate(odoo_db, odoo_username, odoo_password, {})
    if not uid:
        raise RuntimeError('Odoo authenticatie mislukt.')

    models = xmlrpc.client.ServerProxy(f'{odoo_url}/xmlrpc/2/object')
    partner_search = models.execute_kw(
        odoo_db,
        uid,
        odoo_password,
        'res.partner',
        'search',
        [[('email', '=', payment_data['email'])]],
        {'limit': 1},
    )

    if partner_search:
        partner_id = partner_search[0]
    else:
        partner_id = models.execute_kw(
            odoo_db,
            uid,
            odoo_password,
            'res.partner',
            'create',
            [{
                'name': payment_data['name'],
                'email': payment_data['email'],
            }],
        )

    order_lines = []
    for item in payment_data.get('cart_items', []):
        product_name = item.get('name', 'Chocoloco bestelling')
        product_price = float(item.get('price', 0) or 0)
        product_lookup = models.execute_kw(
            odoo_db,
            uid,
            odoo_password,
            'product.product',
            'search',
            [[('name', '=', product_name)]],
            {'limit': 1},
        )

        line_values = {
            'name': product_name,
            'product_uom_qty': 1,
            'price_unit': product_price,
        }

        if product_lookup:
            line_values['product_id'] = product_lookup[0]
        else:
            # Attempt to create a full product template + product in Odoo with a valid UoM
            try:
                # try to find a reasonable unit of measure
                uom_search = models.execute_kw(
                    odoo_db,
                    uid,
                    odoo_password,
                    'uom.uom',
                    'search',
                    [[('name', 'ilike', 'Unit')]],
                    {'limit': 1},
                )
                uom_id = uom_search[0] if uom_search else None

                if not uom_id:
                    # fallback to any available uom
                    any_uom = models.execute_kw(
                        odoo_db,
                        uid,
                        odoo_password,
                        'uom.uom',
                        'search',
                        [[('category_id', '!=', False)]],
                        {'limit': 1},
                    )
                    uom_id = any_uom[0] if any_uom else None

                template_vals = {
                    'name': product_name,
                    'list_price': product_price,
                    'sale_ok': True,
                }
                if uom_id:
                    template_vals['uom_id'] = uom_id

                tmpl_id = models.execute_kw(
                    odoo_db,
                    uid,
                    odoo_password,
                    'product.template',
                    'create',
                    [template_vals],
                )

                # create a product variant for the template (some Odoo versions auto-create; handle both)
                try:
                    prod_id = models.execute_kw(
                        odoo_db,
                        uid,
                        odoo_password,
                        'product.product',
                        'create',
                        [{
                            'product_tmpl_id': tmpl_id,
                            'name': product_name,
                        }],
                    )
                except Exception:
                    # find existing product variant for the template
                    variants = models.execute_kw(
                        odoo_db,
                        uid,
                        odoo_password,
                        'product.product',
                        'search',
                        [[('product_tmpl_id', '=', tmpl_id)]],
                        {'limit': 1},
                    )
                    prod_id = variants[0] if variants else None

                if prod_id:
                    line_values['product_id'] = prod_id
            except Exception:
                # if anything fails, leave product_id unset and allow the upstream error to surface
                current_app.logger.exception('Failed to create fallback product in Odoo')

        order_lines.append((0, 0, line_values))

    if not order_lines:
        order_lines.append((0, 0, {
            'name': 'Demo Chocoloco bestelling',
            'product_uom_qty': 1,
            'price_unit': float(payment_data.get('cart_total', 0) or 0),
        }))

    # Ensure every order line has a product_id; create a fallback product when missing
    for idx, line in enumerate(order_lines):
        try:
            _, _, vals = line
        except Exception:
            continue
        if not vals.get('product_id'):
            try:
                fallback_id = models.execute_kw(
                    odoo_db,
                    uid,
                    odoo_password,
                    'product.product',
                    'create',
                    [{
                        'name': vals.get('name', 'Chocoloco fallback product'),
                        'type': 'product',
                        'list_price': vals.get('price_unit', 0),
                        'sale_ok': True,
                    }],
                )
                vals['product_id'] = fallback_id
                order_lines[idx] = (0, 0, vals)
            except Exception:
                # if fallback creation fails, leave as-is and let Odoo return the fault
                pass

    order_name = f"CHOC-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    order_vals = {
        'partner_id': partner_id,
        'client_order_ref': payment_data.get('payment_ref', order_name),
        'origin': 'Chocoloco webshop',
        'order_line': order_lines,
    }

    order_id = models.execute_kw(
        odoo_db,
        uid,
        odoo_password,
        'sale.order',
        'create',
        [order_vals],
    )

    models.execute_kw(
        odoo_db,
        uid,
        odoo_password,
        'sale.order',
        'action_confirm',
        [[order_id]],
    )

    return order_id, order_name

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


@main_bp.route('/shop')
@login_required
def shop():
    shop_products = [
        {
            'name': 'Grand Cru 72%',
            'category': 'Pure chocolade',
            'price': 6.95,
            'rating': 4.9,
            'badge': 'Bestseller',
            'description': 'Intense cacaotonen, fluweelzachte finish en een lang aanhoudende nasmaak.',
            'origin': 'Ecuador',
            'weight': '120 g',
            'emoji': '🍫',
        },
        {
            'name': 'Caramel Sea Salt Bar',
            'category': 'Gevuld',
            'price': 5.50,
            'rating': 4.8,
            'badge': 'Nieuw',
            'description': 'Romige melkchocolade met boterzachte karamel en een snuf zeezout.',
            'origin': 'België',
            'weight': '110 g',
            'emoji': '✨',
        },
        {
            'name': 'Hazelnoot Praliné Trio',
            'category': 'Pralines',
            'price': 8.25,
            'rating': 5.0,
            'badge': 'Chef choice',
            'description': 'Drie lagen praliné, geroosterde hazelnoten en een zachte crunch.',
            'origin': 'Nederland',
            'weight': '150 g',
            'emoji': '🌰',
        },
        {
            'name': 'Ruby Berry Tablet',
            'category': 'Fruitig',
            'price': 6.20,
            'rating': 4.7,
            'badge': 'Limited',
            'description': 'Frisse bessentonen, elegante ruby-kleur en een speelse zuurzoete bite.',
            'origin': 'Zwitsers assortiment',
            'weight': '100 g',
            'emoji': '🍓',
        },
        {
            'name': 'Mint Noir Collection',
            'category': 'Seizoensspecial',
            'price': 7.40,
            'rating': 4.8,
            'badge': 'Favoriet',
            'description': 'Donkere chocolade met koele munt, ideaal als frisse afsluiter bij koffie.',
            'origin': 'Frankrijk',
            'weight': '125 g',
            'emoji': '🌿',
        },
        {
            'name': 'Orange Gianduja Slice',
            'category': 'Gianduja',
            'price': 5.95,
            'rating': 4.6,
            'badge': 'Ambacht',
            'description': 'Sinaasappelzest, zachte gianduja en een glanzende chocolade-afwerking.',
            'origin': 'Italië',
            'weight': '115 g',
            'emoji': '🍊',
        },
    ]

    shop_categories = ['Alles', 'Pure chocolade', 'Gevuld', 'Pralines', 'Fruitig', 'Seizoensspecial', 'Gianduja']
    featured_highlights = [
        {'label': 'Vandaag verzonden', 'value': 'Voor 17:00 besteld'},
        {'label': 'Cacao selecties', 'value': 'Van mild tot intens'},
        {'label': 'Luxe verpakking', 'value': 'Perfect als cadeau'},
    ]

    return render_template(
        'shop.html',
        shop_products=shop_products,
        shop_categories=shop_categories,
        featured_highlights=featured_highlights,
    )


@main_bp.route('/cart/save', methods=['POST'])
@login_required
def save_cart():
    payload = request.get_json(silent=True) or {}
    cart_items = payload.get('items', [])
    cart_total = payload.get('total', 0)

    if not isinstance(cart_items, list):
        cart_items = []

    try:
        cart_total = round(float(cart_total or 0), 2)
    except (TypeError, ValueError):
        cart_total = 0.0

    session['shop_cart'] = cart_items
    session['shop_cart_total'] = cart_total

    return jsonify({'status': 'success', 'items': len(cart_items), 'total': cart_total})


@main_bp.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    form = CheckoutForm()
    form.full_name.data = form.full_name.data or current_user.username
    form.email.data = form.email.data or current_user.email
    if request.method == 'GET' and not form.payment_method.data:
        form.payment_method.data = 'demo'

    if form.validate_on_submit():
        try:
            cart_items = json.loads(form.cart_payload.data)
        except (TypeError, json.JSONDecodeError):
            cart_items = []

        if not cart_items:
            cart_items = session.get('shop_cart', []) or []

        try:
            cart_total = round(float(form.cart_total.data or 0), 2)
        except (TypeError, ValueError):
            cart_total = 0.0

        if not cart_total:
            try:
                cart_total = round(float(session.get('shop_cart_total', 0) or 0), 2)
            except (TypeError, ValueError):
                cart_total = 0.0

        is_demo_payment = form.payment_method.data == 'demo'

        if is_demo_payment and not cart_items and cart_total > 0:
            cart_items = [
                {
                    'name': 'Demo Chocoloco Selection',
                    'price': cart_total,
                }
            ]

        if not cart_items:
            return render_template('checkout.html', form=form, cart_items=[], cart_total=0, cart_empty=True)

        if not cart_total:
            cart_total = round(sum(float(item.get('price', 0)) for item in cart_items), 2)
        payment_ref = f"DEMO-{datetime.now().strftime('%Y%m%d%H%M%S')}" if is_demo_payment else f"CC-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        payment_labels = dict(form.payment_method.choices)

        session['last_payment'] = {
            'name': form.full_name.data,
            'email': form.email.data,
            'payment_method': form.payment_method.data,
            'payment_method_label': 'Demo betaling - automatisch geslaagd' if is_demo_payment else payment_labels.get(form.payment_method.data, form.payment_method.data),
            'payment_status': 'geslaagd',
            'payment_ref': payment_ref,
            'cart_items': cart_items,
            'cart_total': cart_total,
        }

        try:
            odoo_order_id, odoo_order_name = send_order_to_odoo(session['last_payment'])
            session['last_payment']['odoo_order_id'] = odoo_order_id
            session['last_payment']['odoo_order_name'] = odoo_order_name
        except Exception as error:
            current_app.logger.exception('Odoo order creation failed')
            flash(f'Betaling geslaagd, maar Odoo kon de order niet opslaan: {error}', 'warning')
            return render_template('checkout.html', form=form, cart_items=cart_items, cart_total=cart_total, cart_empty=False)

        return redirect(url_for('main.checkout_success'))

    return render_template('checkout.html', form=form, cart_items=[], cart_total=0, cart_empty=False)


@main_bp.route('/checkout/success')
@login_required
def checkout_success():
    payment = session.get('last_payment')
    if not payment:
        return redirect(url_for('main.shop'))

    return render_template('checkout_success.html', payment=payment)

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


# Community forum
@main_bp.route('/community')
@login_required
def community():
    q = request.args.get('q', '').strip()
    if q:
        # basic search on title or body
        topics = ForumTopic.query.filter(
            db.or_(
                ForumTopic.title.ilike(f"%{q}%"),
                ForumTopic.body.ilike(f"%{q}%")
            )
        ).order_by(ForumTopic.created_at.desc()).all()
    else:
        topics = ForumTopic.query.order_by(ForumTopic.created_at.desc()).all()

    # compute contributor leaderboard (topics + replies)
    from sqlalchemy import func
    topic_counts = db.session.query(ForumTopic.user_id, func.count(ForumTopic.id).label('tcount')).group_by(ForumTopic.user_id).all()
    reply_counts = db.session.query(ForumReply.user_id, func.count(ForumReply.id).label('rcount')).group_by(ForumReply.user_id).all()

    counts = {}
    for uid, tc in topic_counts:
        counts[uid] = counts.get(uid, 0) + tc
    for uid, rc in reply_counts:
        counts[uid] = counts.get(uid, 0) + rc

    # build list of users with totals
    contributors = []
    if counts:
        user_ids = list(counts.keys())
        users = User.query.filter(User.id.in_(user_ids)).all()
        user_map = {u.id: u for u in users}
        for uid, total in counts.items():
            u = user_map.get(uid)
            if u:
                contributors.append({'user': u, 'count': total})

    contributors.sort(key=lambda x: x['count'], reverse=True)
    top_contributors = contributors[:8]

    return render_template('community/list.html', topics=topics, top_contributors=top_contributors, q=q)


@main_bp.route('/community/new', methods=['GET', 'POST'])
@login_required
def community_new():
    form = TopicForm()
    if form.validate_on_submit():
        topic = ForumTopic(user_id=current_user.id, title=form.title.data, body=form.body.data)
        db.session.add(topic)
        db.session.commit()
        return redirect(url_for('main.community'))
    return render_template('community/new.html', form=form)


@main_bp.route('/community/topic/<int:topic_id>/edit', methods=['GET', 'POST'])
@login_required
def community_edit(topic_id):
    topic = ForumTopic.query.get_or_404(topic_id)
    if topic.user_id != current_user.id:
        return redirect(url_for('main.community_topic', topic_id=topic.id))
    form = TopicForm()
    if form.validate_on_submit():
        topic.title = form.title.data
        topic.body = form.body.data
        topic.updated_at = datetime.utcnow()
        db.session.commit()
        return redirect(url_for('main.community_topic', topic_id=topic.id))

    # prefill
    if request.method == 'GET':
        form.title.data = topic.title
        form.body.data = topic.body

    return render_template('community/new.html', form=form, editing=True, topic=topic)


@main_bp.route('/community/topic/<int:topic_id>/delete', methods=['POST'])
@login_required
def community_delete(topic_id):
    topic = ForumTopic.query.get_or_404(topic_id)
    if topic.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    # delete associated replies and subscriptions and notifications
    ForumReply.query.filter_by(topic_id=topic.id).delete()
    TopicSubscription.query.filter_by(topic_id=topic.id).delete()
    ForumNotification.query.filter_by(topic_id=topic.id).delete()
    db.session.delete(topic)
    db.session.commit()
    return redirect(url_for('main.community'))


@main_bp.route('/community/topic/<int:topic_id>', methods=['GET', 'POST'])
@login_required
def community_topic(topic_id):
    topic = ForumTopic.query.get_or_404(topic_id)
    form = ReplyForm()
    if form.validate_on_submit():
        reply = ForumReply(topic_id=topic.id, user_id=current_user.id, body=form.body.data)
        db.session.add(reply)
        db.session.commit()
        # create notifications for subscribers (except the replier)
        subs = TopicSubscription.query.filter_by(topic_id=topic.id).all()
        for s in subs:
            if s.user_id == current_user.id:
                continue
            notif = ForumNotification(user_id=s.user_id, topic_id=topic.id, reply_id=reply.id)
            db.session.add(notif)
        db.session.commit()
        return redirect(url_for('main.community_topic', topic_id=topic.id))

    replies = ForumReply.query.filter_by(topic_id=topic.id).order_by(ForumReply.created_at.asc()).all()

    # subscription and likes
    subscribed = TopicSubscription.query.filter_by(user_id=current_user.id, topic_id=topic.id).first() is not None
    like_info = {}
    for r in replies:
        like_info[r.id] = {
            'count': ReplyLike.query.filter_by(reply_id=r.id).count(),
            'liked': ReplyLike.query.filter_by(reply_id=r.id, user_id=current_user.id).first() is not None
        }

    return render_template('community/topic.html', topic=topic, replies=replies, form=form, subscribed=subscribed, like_info=like_info)


@main_bp.route('/community/topic/<int:topic_id>/subscribe', methods=['POST'])
@login_required
def community_subscribe(topic_id):
    topic = ForumTopic.query.get_or_404(topic_id)
    existing = TopicSubscription.query.filter_by(user_id=current_user.id, topic_id=topic.id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({'status': 'unsubscribed'})
    sub = TopicSubscription(user_id=current_user.id, topic_id=topic.id)
    db.session.add(sub)
    db.session.commit()
    return jsonify({'status': 'subscribed'})


@main_bp.route('/reply/<int:reply_id>/like', methods=['POST'])
@login_required
def like_reply(reply_id):
    reply = ForumReply.query.get_or_404(reply_id)
    existing = ReplyLike.query.filter_by(user_id=current_user.id, reply_id=reply.id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        liked = False
    else:
        db.session.add(ReplyLike(user_id=current_user.id, reply_id=reply.id))
        db.session.commit()
        liked = True

    like_count = ReplyLike.query.filter_by(reply_id=reply.id).count()
    return jsonify({'status': 'success', 'liked': liked, 'like_count': like_count})


@main_bp.route('/notifications/forum/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_forum_notification_read(notification_id):
    notif = ForumNotification.query.get_or_404(notification_id)
    if notif.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    notif.is_read = True
    db.session.commit()
    # return combined unread count
    from app.models import ForumNotification as FN
    unread = FN.query.filter_by(user_id=current_user.id, is_read=False).count()
    return jsonify({'status': 'success', 'unread_count': unread})


@main_bp.route('/notifications/forum/<int:notification_id>/dismiss', methods=['POST'])
@login_required
def dismiss_forum_notification(notification_id):
    notif = ForumNotification.query.get_or_404(notification_id)
    if notif.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    db.session.delete(notif)
    db.session.commit()
    from app.models import ForumNotification as FN
    unread = FN.query.filter_by(user_id=current_user.id, is_read=False).count()
    return jsonify({'status': 'success', 'unread_count': unread})


@main_bp.route('/notifications/poll')
@login_required
def notifications_poll():
    from app.models import Product, ExpiryWarningRead, ExpiryWarningDismissed, ForumNotification, ForumTopic, ForumReply

    products = Product.query.filter_by(user_id=current_user.id).all()
    notifications = []
    unread_count = 0

    for product in products:
        if product.expiry_date:
            days_until_expiry = (product.expiry_date - datetime.now().date()).days
            if 0 <= days_until_expiry <= 7:
                dismissed_entry = ExpiryWarningDismissed.query.filter_by(
                    user_id=current_user.id,
                    product_id=product.id
                ).first()

                if dismissed_entry:
                    continue

                is_read = ExpiryWarningRead.query.filter_by(
                    user_id=current_user.id,
                    product_id=product.id
                ).first() is not None

                notifications.append({
                    'kind': 'expiry',
                    'product_id': product.id,
                    'name': product.name,
                    'days': days_until_expiry,
                    'is_read': is_read,
                })

                if not is_read:
                    unread_count += 1

    forum_notifs = ForumNotification.query.filter_by(user_id=current_user.id).order_by(ForumNotification.created_at.desc()).all()
    for fn in forum_notifs:
        topic = ForumTopic.query.get(fn.topic_id)
        reply = ForumReply.query.get(fn.reply_id) if fn.reply_id else None
        text = ''
        if reply:
            text = (reply.body[:160] + ('...' if len(reply.body) > 160 else ''))
        else:
            text = topic.title if topic else 'Nieuw forumbericht'

        notifications.append({
            'kind': 'forum',
            'notification_id': fn.id,
            'topic_id': fn.topic_id,
            'topic_title': topic.title if topic else 'Onderwerp',
            'text': text,
            'is_read': fn.is_read,
        })
        if not fn.is_read:
            unread_count += 1

    # simple sort: unread first
    notifications.sort(key=lambda item: (item.get('is_read', True),))

    return jsonify({'notifications': notifications, 'unread_count': unread_count})
