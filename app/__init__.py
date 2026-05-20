from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_login import current_user
from datetime import datetime

db = SQLAlchemy()
login_manager = LoginManager()

def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    from app.models import User, Product
    from app import routes

    app.register_blueprint(routes.auth_bp)
    app.register_blueprint(routes.main_bp)

    @app.context_processor
    def inject_nav_expiry_warning():
        if not current_user.is_authenticated:
            return {
                'nav_notifications': [],
                'nav_unread_count': 0,
            }
        from app.models import Product, ExpiryWarningRead, ExpiryWarningDismissed, ForumNotification, TopicSubscription, ForumReply, ForumTopic

        products = Product.query.filter_by(user_id=current_user.id).all()
        notifications = []
        unread_count = 0

        # expiry notifications
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

        # forum notifications
        forum_notifs = ForumNotification.query.filter_by(user_id=current_user.id).order_by(ForumNotification.created_at.desc()).all()
        for fn in forum_notifs:
            # include topic and reply snippet
            topic = ForumTopic.query.get(fn.topic_id)
            reply = ForumReply.query.get(fn.reply_id) if fn.reply_id else None
            text = (reply.body[:160] + ('...' if reply and len(reply.body) > 160 else '')) if reply else (topic.title if topic else 'Nieuw forumbericht')
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

        # sort: unread first, then by created time roughly (expiry near first by days)
        notifications.sort(key=lambda item: (item.get('is_read', True), item.get('days', 9999)))

        return {
            'nav_notifications': notifications,
            'nav_unread_count': unread_count,
        }

    with app.app_context():
        db.create_all()

    return app
