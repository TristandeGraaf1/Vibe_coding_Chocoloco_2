from flask import Flask, current_app
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_login import current_user
from flask_babel import Babel, gettext as _
from datetime import datetime
from sqlalchemy import inspect, text

db = SQLAlchemy()
login_manager = LoginManager()

def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')
    app.config['BABEL_DEFAULT_LOCALE'] = 'nl'
    app.config['BABEL_DEFAULT_TIMEZONE'] = 'UTC'

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    from flask_babel import lazy_gettext, gettext as babel_gettext, ngettext as babel_ngettext

    def get_locale():
        if current_user.is_authenticated:
            return current_user.language or 'nl'
        from flask import request
        return request.accept_languages.best_match(['nl', 'de', 'en', 'fr']) or 'nl'

    babel = Babel(app, locale_selector=get_locale)

    app.jinja_env.globals.update({
        '_': babel_gettext,
        'ngettext': babel_ngettext,
    })

    from app.models import User, Product, RewardTransaction
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
        from app.models import Product, ExpiryWarningRead, ExpiryWarningDismissed, ForumNotification, ComplaintStatusNotification, ComplaintTicketWatch, TopicSubscription, ForumReply, ForumTopic, RewardTransaction
        from app.routes import _sync_complaint_status_notifications

        products = Product.query.filter_by(user_id=current_user.id).all()
        notifications = []
        unread_count = 0

        try:
            _sync_complaint_status_notifications()
        except Exception:
            current_app.logger.exception('Complaint status notifications konden niet worden gesynchroniseerd.')

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

        complaint_notifs = ComplaintStatusNotification.query.filter_by(user_id=current_user.id).order_by(ComplaintStatusNotification.created_at.desc()).all()
        for cn in complaint_notifs:
            notifications.append({
                'kind': 'complaint_status',
                'notification_id': cn.id,
                'ticket_id': cn.ticket_id,
                'ticket_name': cn.ticket_name,
                'old_status': cn.old_status,
                'new_status': cn.new_status,
                'text': f'Klachtstatus gewijzigd van {cn.old_status or "onbekend"} naar {cn.new_status}',
                'is_read': cn.is_read,
                'created_at': cn.created_at,
            })
            if not cn.is_read:
                unread_count += 1

        # sort: unread first, then by created time roughly (expiry near first by days)
        notifications.sort(key=lambda item: (item.get('is_read', True), item.get('days', 9999), item.get('created_at') or datetime.min))

        return {
            'nav_notifications': notifications,
            'nav_unread_count': unread_count,
        }

    @app.context_processor
    def inject_community_helpers():
        from app.models import ForumTopic, ForumReply
        import re
        from html import escape as html_escape
        from html.parser import HTMLParser
        from markupsafe import Markup, escape

        def contribution_count(user_id):
            topic_count = ForumTopic.query.filter_by(user_id=user_id).count()
            reply_count = ForumReply.query.filter_by(user_id=user_id).count()
            return topic_count + reply_count

        def contribution_badge(user_id):
            score = contribution_count(user_id)
            if score >= 30:
                return {'label': 'Cacao Master', 'class': 'badge-master', 'score': score}
            if score >= 15:
                return {'label': 'Cacao Expert', 'class': 'badge-expert', 'score': score}
            if score >= 5:
                return {'label': 'Cacao Beginner', 'class': 'badge-beginner', 'score': score}
            return {'label': 'Cacao Newbie', 'class': 'badge-newbie', 'score': score}

        class RichTextSanitizer(HTMLParser):
            allowed_tags = {'strong', 'em', 'b', 'i', 'u', 'br', 'p', 'div', 'span', 'h1', 'h2', 'h3', 'a'}
            allowed_attrs = {'a': {'href', 'target', 'rel'}}

            def __init__(self):
                super().__init__()
                self.parts = []

            def handle_starttag(self, tag, attrs):
                if tag not in self.allowed_tags:
                    return
                clean_attrs = []
                allowed = self.allowed_attrs.get(tag, set())
                for key, value in attrs:
                    if key in allowed:
                        if key == 'href' and value and not value.startswith(('http://', 'https://', '/')):
                            continue
                        clean_attrs.append(f'{key}="{html_escape(value, quote=True)}"')
                suffix = f' {" ".join(clean_attrs)}' if clean_attrs else ''
                self.parts.append(f'<{tag}{suffix}>')

            def handle_endtag(self, tag):
                if tag in self.allowed_tags and tag != 'br':
                    self.parts.append(f'</{tag}>')

            def handle_data(self, data):
                self.parts.append(html_escape(data))

            def handle_entityref(self, name):
                from html import unescape as html_unescape
                self.parts.append(html_escape(html_unescape(f'&{name};')))

            def handle_charref(self, name):
                from html import unescape as html_unescape
                self.parts.append(html_escape(html_unescape(f'&#{name};')))

            def get_html(self):
                return ''.join(self.parts)

        def render_markdown(md):
            if not md:
                return ''

            raw = md.strip()
            if '<' in raw and '>' in raw:
                sanitizer = RichTextSanitizer()
                sanitizer.feed(raw)
                sanitizer.close()
                return Markup(sanitizer.get_html().replace('\n', '<br>'))

            out = escape(md)
            out = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', out, flags=re.S)
            out = re.sub(r'\*(.*?)\*', r'<em>\1</em>', out, flags=re.S)
            out = re.sub(r'^### (.*)$', r'<h3>\1</h3>', out, flags=re.M)
            out = re.sub(r'^## (.*)$', r'<h2>\1</h2>', out, flags=re.M)
            out = re.sub(r'^# (.*)$', r'<h1>\1</h1>', out, flags=re.M)
            out = re.sub(r'\[([^\]]+)\]\((https?://[^)]+)\)', r'<a href="\2" target="_blank" rel="noopener noreferrer">\1</a>', out)
            out = out.replace('\n', '<br>')
            return Markup(out)

        return {
            'contribution_count': contribution_count,
            'contribution_badge': contribution_badge,
            'render_markdown': render_markdown,
        }

    with app.app_context():
        db.create_all()
        _ensure_product_barcode_column()
        _ensure_reward_transaction_table()

    return app


def _ensure_product_barcode_column():
    inspector = inspect(db.engine)
    product_columns = {column['name'] for column in inspector.get_columns('product')}
    if 'barcode' in product_columns:
        return

    with db.engine.begin() as connection:
        connection.execute(text('ALTER TABLE product ADD COLUMN barcode VARCHAR(120)'))


def _ensure_reward_transaction_table():
    inspector = inspect(db.engine)
    if 'reward_transaction' in inspector.get_table_names():
        return

    RewardTransaction.__table__.create(bind=db.engine, checkfirst=True)
