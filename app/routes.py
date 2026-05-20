from flask import Blueprint, render_template, redirect, url_for, request, jsonify, session
from flask_login import login_user, logout_user, current_user, login_required
from app import db
from app.models import User, Product, ExpiryWarningRead, ExpiryWarningDismissed, ForumTopic, ForumReply, TopicSubscription, ForumNotification, ReplyLike
from app.forms import LoginForm, RegisterForm, ProductForm, ProductRegisterForm, TopicForm, ReplyForm
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
