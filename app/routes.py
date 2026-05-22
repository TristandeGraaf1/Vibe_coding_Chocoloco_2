from flask import Blueprint, render_template, redirect, url_for, request, jsonify, session
from flask_login import login_user, logout_user, current_user, login_required
from app import db
from app.models import User, Product, ExpiryWarningRead, ExpiryWarningDismissed, ForumTopic, ForumReply, TopicSubscription, ForumNotification, ReplyLike
from app.forms import LoginForm, RegisterForm, ProductForm, ProductRegisterForm, TopicForm, ReplyForm, CheckoutForm, ComplaintForm
from datetime import datetime, timedelta
from flask import current_app, flash
import html
import json
import re
import uuid
import xmlrpc.client
import urllib.parse
import urllib.request

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
        try:
            product_qty = int(item.get('qty', 1) or 1)
        except Exception:
            product_qty = 1
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
            'product_uom_qty': product_qty,
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


def _odoo_credentials():
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
    return odoo_db, uid, models, odoo_password


def _resolve_helpdesk_ticket_model(models, odoo_db, uid, odoo_password):
    fields = models.execute_kw(
        odoo_db,
        uid,
        odoo_password,
        'helpdesk.ticket',
        'fields_get',
        [],
        {'attributes': ['type']},
    )
    return 'helpdesk.ticket', fields or {}


def _resolve_helpdesk_team(models, odoo_db, uid, odoo_password):
    team_id_config = current_app.config.get('ODOO_HELPDESK_TEAM_ID', '').strip()
    if team_id_config:
        try:
            return int(team_id_config)
        except ValueError:
            current_app.logger.warning('ODOO_HELPDESK_TEAM_ID is not a valid number.')

    team_name = current_app.config.get('ODOO_HELPDESK_TEAM_NAME', '').strip()
    try:
        models.execute_kw(
            odoo_db,
            uid,
            odoo_password,
            'helpdesk.team',
            'fields_get',
            [],
            {'attributes': ['type']},
        )
    except Exception:
        return None

    search_domain = []
    if team_name:
        search_domain = [('name', '=', team_name)]

    if search_domain:
        team_search = models.execute_kw(
            odoo_db,
            uid,
            odoo_password,
            'helpdesk.team',
            'search',
            [search_domain],
            {'limit': 1},
        )
        if team_search:
            return team_search[0]

    fallback_search = models.execute_kw(
        odoo_db,
        uid,
        odoo_password,
        'helpdesk.team',
        'search',
        [[]],
        {'limit': 1},
    )
    if fallback_search:
        return fallback_search[0]

    return None


def _build_helpdesk_complaint(product, title, description):
    clean_title = (title or '').strip() or f'Klacht over {product.name}'
    complaint_lines = [
        f'Klant: {current_user.username} <{current_user.email}>',
        f'Product: {product.name} (ID {product.id})',
    ]
    if product.flavor:
        complaint_lines.append(f'Smaak: {product.flavor}')
    if product.expiry_date:
        complaint_lines.append(f'Vervaldatum: {product.expiry_date.strftime("%d-%m-%Y")}')
    if product.description:
        complaint_lines.append(f'Productnotitie: {product.description}')
    complaint_lines.extend(['', 'Klachtomschrijving:', description])
    return clean_title, '\n'.join(complaint_lines)


def _submit_helpdesk_complaint_via_website_form(product, title, description):
    odoo_url = current_app.config.get('ODOO_URL', '').strip().rstrip('/')
    if not odoo_url:
        return None

    clean_title, complaint_text = _build_helpdesk_complaint(product, title, description)
    payload = {
        'name': clean_title,
        'subject': clean_title,
        'description': complaint_text,
        'email_from': current_user.email,
        'partner_name': current_user.username,
    }

    try:
        odoo_db, uid, models, odoo_password = _odoo_credentials()
        team_id = _resolve_helpdesk_team(models, odoo_db, uid, odoo_password)
        if team_id:
            payload['team_id'] = str(team_id)
    except Exception:
        pass

    current_app.logger.debug('Submitting helpdesk website form payload: %s', json.dumps(payload, ensure_ascii=False))
    request_obj = urllib.request.Request(
        f'{odoo_url}/website/form/helpdesk.ticket',
        data=urllib.parse.urlencode(payload).encode('utf-8'),
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        method='POST',
    )

    with urllib.request.urlopen(request_obj, timeout=20) as response:
        raw_response = response.read().decode('utf-8', errors='replace')
        current_app.logger.debug('Helpdesk website form raw response: %s', raw_response)

    try:
        parsed_response = json.loads(raw_response)
    except Exception:
        return None

    if isinstance(parsed_response, dict) and parsed_response.get('id'):
        return parsed_response['id']
    return None


def _create_helpdesk_complaint_ticket_via_xmlrpc(product, title, description):
    odoo_db, uid, models, odoo_password = _odoo_credentials()
    ticket_model, ticket_fields = _resolve_helpdesk_ticket_model(models, odoo_db, uid, odoo_password)

    partner_search = models.execute_kw(
        odoo_db,
        uid,
        odoo_password,
        'res.partner',
        'search',
        [[('email', '=', current_user.email)]],
        {'limit': 1},
    )
    if partner_search:
        partner_id = partner_search[0]
    elif current_user.email:
        partner_id = models.execute_kw(
            odoo_db,
            uid,
            odoo_password,
            'res.partner',
            'create',
            [{
                'name': current_user.username,
                'email': current_user.email,
            }],
        )
    else:
        partner_id = None

    clean_title, complaint_text = _build_helpdesk_complaint(product, title, description)
    ticket_vals = {
        'name': clean_title,
        'description': complaint_text,
    }

    team_id = _resolve_helpdesk_team(models, odoo_db, uid, odoo_password)
    if team_id and 'team_id' in ticket_fields:
        ticket_vals['team_id'] = team_id
    if partner_id and 'partner_id' in ticket_fields:
        ticket_vals['partner_id'] = partner_id
    if 'priority' in ticket_fields:
        ticket_vals['priority'] = '0'

    current_app.logger.debug('Creating helpdesk ticket directly with values: %s', ticket_vals)
    return models.execute_kw(
        odoo_db,
        uid,
        odoo_password,
        ticket_model,
        'create',
        [ticket_vals],
    )


def _create_helpdesk_complaint_ticket(product, title, description):
    try:
        website_ticket_id = _submit_helpdesk_complaint_via_website_form(product, title, description)
        if website_ticket_id:
            return website_ticket_id
    except Exception as error:
        current_app.logger.warning('Helpdesk website form submit failed, falling back to XML-RPC: %s', error)

    return _create_helpdesk_complaint_ticket_via_xmlrpc(product, title, description)


def _split_csv(value):
    return [item.strip() for item in (value or '').split(',') if item.strip()]


def _odoo_html_to_text(value):
    cleaned = re.sub(r'<[^>]+>', '', value or '')
    return html.unescape(cleaned).strip()


def _find_or_create_partner(models, odoo_db, uid, odoo_password, name, email):
    partner_id = None
    if email:
        partner_search = models.execute_kw(
            odoo_db,
            uid,
            odoo_password,
            'res.partner',
            'search',
            [[('email', '=', email)]],
            {'limit': 1},
        )
        if partner_search:
            partner_id = partner_search[0]

    if not partner_id:
        partner_id = models.execute_kw(
            odoo_db,
            uid,
            odoo_password,
            'res.partner',
            'create',
            [{
                'name': name,
                'email': email,
            }],
        )

    return partner_id


def _resolve_livechat_model(models, odoo_db, uid, odoo_password):
    candidate_models = (
        'discuss.channel',
        'mail.channel',
        'im_livechat.channel',
    )

    for model_name in candidate_models:
        try:
            fields = models.execute_kw(
                odoo_db,
                uid,
                odoo_password,
                model_name,
                'fields_get',
                [],
                {'attributes': ['type']},
            )
            return model_name, fields or {}
        except Exception as error:
            error_text = str(error).lower()
            if "doesn't exist" in error_text or 'does not exist' in error_text or 'unknown model' in error_text:
                continue
            continue

    raise RuntimeError(
        'Geen geschikt Odoo chatmodel gevonden. Controleer of Discuss in Odoo is geïnstalleerd '
        'en of je Odoo-gebruiker toegang heeft tot de chat-app.'
    )


def _get_channel_membership_field(fields):
    for field_name in ('channel_partner_ids', 'channel_member_ids', 'member_ids', 'partner_ids', 'channel_ids'):
        if field_name in fields:
            return field_name
    return None


def _membership_commands_for_partners(membership_field, partner_ids):
    # Use add-only commands so Odoo does not try to unlink existing members.
    if membership_field in ('channel_partner_ids', 'partner_ids'):
        return [(4, partner_id) for partner_id in partner_ids]
    return None


def _get_livechat_session_key():
    session_key = session.get('livechat_session_key')
    if not session_key:
        session_key = uuid.uuid4().hex
        session['livechat_session_key'] = session_key
    return session_key


def _get_livechat_thread():
    odoo_db, uid, models, odoo_password = _odoo_credentials()
    support_emails = _split_csv(current_app.config.get('ODOO_LIVECHAT_SUPPORT_EMAILS', ''))
    if not support_emails:
        raise RuntimeError('Stel ODOO_LIVECHAT_SUPPORT_EMAILS in zodat live chat naar een Odoo-medewerker wordt doorgestuurd.')

    livechat_session_key = _get_livechat_session_key()

    user_partner_id = _find_or_create_partner(
        models,
        odoo_db,
        uid,
        odoo_password,
        current_user.username,
        current_user.email,
    )

    support_partner_ids = []
    for email in support_emails:
        partner_search = models.execute_kw(
            odoo_db,
            uid,
            odoo_password,
            'res.partner',
            'search',
            [[('email', '=', email)]],
            {'limit': 1},
        )
        if partner_search:
            support_partner_ids.append(partner_search[0])

    support_partner_ids = sorted(set(support_partner_ids))
    if not support_partner_ids:
        raise RuntimeError('Geen Odoo-medewerker gevonden voor live chat. Controleer ODOO_LIVECHAT_SUPPORT_EMAILS.')

    livechat_model, livechat_fields = _resolve_livechat_model(models, odoo_db, uid, odoo_password)
    membership_field = _get_channel_membership_field(livechat_fields)
    channel_name = f'Chocoloco livechat - {current_user.id} - {livechat_session_key}'
    search_domain = [('name', '=', channel_name)]
    if 'channel_type' in livechat_fields:
        search_domain.append(('channel_type', '=', 'channel'))
    channel_search = models.execute_kw(
        odoo_db,
        uid,
        odoo_password,
        livechat_model,
        'search',
        [search_domain],
        {'limit': 1},
    )

    partner_ids = sorted(set([user_partner_id] + support_partner_ids))
    membership_commands = _membership_commands_for_partners(membership_field, partner_ids)
    if channel_search:
        channel_id = channel_search[0]
        if membership_field and membership_commands:
            try:
                models.execute_kw(
                    odoo_db,
                    uid,
                    odoo_password,
                    livechat_model,
                    'write',
                    [[channel_id], {membership_field: membership_commands}],
                )
            except Exception:
                current_app.logger.warning('Livechat kanaalleden konden niet worden bijgewerkt door Odoo-rechten.')
    else:
        create_vals = {'name': channel_name}
        if 'channel_type' in livechat_fields:
            create_vals['channel_type'] = 'channel'
        if membership_field and membership_commands:
            create_vals[membership_field] = membership_commands

        try:
            channel_id = models.execute_kw(
                odoo_db,
                uid,
                odoo_password,
                livechat_model,
                'create',
                [create_vals],
            )
        except Exception:
            channel_id = models.execute_kw(
                odoo_db,
                uid,
                odoo_password,
                livechat_model,
                'create',
                [{
                    'name': channel_name,
                }],
            )
            if membership_field and membership_commands:
                try:
                    models.execute_kw(
                        odoo_db,
                        uid,
                        odoo_password,
                        livechat_model,
                        'write',
                        [[channel_id], {membership_field: membership_commands}],
                    )
                except Exception:
                    current_app.logger.warning('Livechat kanaalleden konden niet worden gekoppeld door Odoo-rechten.')

    session['livechat_channel_id'] = channel_id
    session['livechat_model'] = livechat_model
    session['livechat_user_partner_id'] = user_partner_id
    session['livechat_channel_name'] = channel_name
    session['livechat_channel_key'] = livechat_session_key
    return odoo_db, uid, models, odoo_password, livechat_model, channel_id, user_partner_id


def _fetch_livechat_messages(models, odoo_db, uid, odoo_password, livechat_model, channel_id, user_partner_id):
    messages = models.execute_kw(
        odoo_db,
        uid,
        odoo_password,
        'mail.message',
        'search_read',
        [[('model', '=', livechat_model), ('res_id', '=', channel_id)]],
        {
            'fields': ['id', 'author_id', 'body', 'date', 'create_date', 'message_type'],
            'order': 'id asc',
        },
    )

    formatted = []
    for message in messages:
        author = message.get('author_id') or []
        author_id = author[0] if isinstance(author, list) and author else None
        author_name = author[1] if isinstance(author, list) and len(author) > 1 and author[1] else 'Odoo'
        body = _odoo_html_to_text(message.get('body'))
        if not body:
            continue

        formatted.append({
            'id': message.get('id'),
            'author_name': author_name,
            'body': body,
            'timestamp': message.get('date') or message.get('create_date'),
            'is_user': author_id == user_partner_id,
        })

    return formatted

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

    # normalize items and compute a reliable total
    normalized = []
    try:
        for it in cart_items:
            if not isinstance(it, dict):
                continue
            name = it.get('name')
            price = float(it.get('price', 0) or 0)
            try:
                qty = int(it.get('qty', 1) or 1)
            except Exception:
                qty = 1
            if not name:
                continue
            normalized.append({'name': name, 'price': price, 'qty': qty})
    except Exception:
        normalized = []

    computed_total = round(sum(it['price'] * it['qty'] for it in normalized), 2) if normalized else 0.0

    try:
        cart_total = round(float(cart_total or computed_total or 0), 2)
    except (TypeError, ValueError):
        cart_total = computed_total

    session['shop_cart'] = normalized
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
            try:
                cart_total = round(sum(float(item.get('price', 0)) * int(item.get('qty', 1) or 1) for item in cart_items), 2)
            except Exception:
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


@main_bp.route('/chocobot')
@login_required
def chocobot():
    return render_template('chocobot.html')


@main_bp.route('/chocobot/message', methods=['POST'])
@login_required
def chocobot_message():
    payload = request.get_json(silent=True) or {}
    text = (payload.get('text') or '').strip()
    if not text:
        return jsonify({'error': 'No text provided'}), 400

    t = text.lower()

    # Very small set of canned answers for common UI questions
    if 'uitlog' in t or 'uitloggen' in t or 'logout' in t:
        reply = "De knop 'Uitloggen' vind je rechtsboven in het hoofdmenu. Klik op je profielfoto of naam en kies 'Uitloggen'."
    elif 'bestel' in t or 'status' in t or 'tracking' in t or 'volg' in t:
        reply = "Bekijk 'Dashboard' → 'Bestellingen' om de status van je bestellingen en eventuele track & trace-nummers te zien."
    elif 'betaal' in t or 'ideal' in t or 'credit' in t or 'demo' in t:
        reply = "Bij afrekenen kun je iDEAL, creditcard of demo-betalingen kiezen. Kies een methode en volg de instructies op het scherm."
    elif 'wachtwoord' in t or 'inloggen' in t or 'account' in t:
        reply = "Ga naar 'Inloggen' om in te loggen. Als je je wachtwoord bent vergeten, gebruik dan de wachtwoord-reset op het inlogscherm."
    elif 'contact' in t or 'klantenservice' in t:
        reply = "Onze klantenservice is te vinden via de Klantenservice-pagina; daar staat het contactformulier en telefoonnummer."
    else:
        reply = f"Chocobot: Ik begrijp '{text}' niet helemaal. Probeer vragen zoals 'Waar is de knop uitloggen?' of 'Hoe betaal ik?'."

    return jsonify({'reply': reply})


@main_bp.route('/livechat')
@login_required
def livechat():
    livechat_error = None
    messages = []

    try:
        odoo_db, uid, models, odoo_password, livechat_model, channel_id, user_partner_id = _get_livechat_thread()
        messages = _fetch_livechat_messages(models, odoo_db, uid, odoo_password, livechat_model, channel_id, user_partner_id)
    except Exception as error:
        livechat_error = str(error)

    return render_template('livechat.html', livechat_error=livechat_error, messages=messages)


@main_bp.route('/livechat/history')
@login_required
def livechat_history():
    try:
        odoo_db, uid, models, odoo_password, livechat_model, channel_id, user_partner_id = _get_livechat_thread()
        messages = _fetch_livechat_messages(models, odoo_db, uid, odoo_password, livechat_model, channel_id, user_partner_id)
        return jsonify({'messages': messages})
    except Exception as error:
        return jsonify({'error': str(error)}), 400


@main_bp.route('/livechat/message', methods=['POST'])
@login_required
def livechat_message():
    payload = request.get_json(silent=True) or {}
    text = (payload.get('text') or '').strip()
    if not text:
        return jsonify({'error': 'No text provided'}), 400

    try:
        odoo_db, uid, models, odoo_password, livechat_model, channel_id, user_partner_id = _get_livechat_thread()
        models.execute_kw(
            odoo_db,
            uid,
            odoo_password,
            livechat_model,
            'message_post',
            [[channel_id]],
            {
                'body': html.escape(text),
                'message_type': 'comment',
                'subtype_xmlid': 'mail.mt_comment',
                'author_id': user_partner_id,
                'email_from': current_user.email,
            },
        )

        messages = _fetch_livechat_messages(models, odoo_db, uid, odoo_password, livechat_model, channel_id, user_partner_id)
        return jsonify({'messages': messages})
    except Exception as error:
        current_app.logger.exception('Livechat message send failed')
        return jsonify({'error': str(error)}), 400

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


@main_bp.route('/complaints', methods=['GET', 'POST'])
@main_bp.route('/complaints/<int:product_id>', methods=['GET', 'POST'])
@login_required
def complaints(product_id=None):
    products = Product.query.filter_by(user_id=current_user.id).order_by(Product.added_at.desc()).all()
    if not products:
        flash('Registreer eerst een product voordat je een klacht indient.', 'warning')
        return redirect(url_for('main.all_products'))

    form = ComplaintForm()
    form.product_id.choices = [(product.id, product.name) for product in products]

    selected_product_id = product_id if product_id is not None else products[0].id
    if request.method == 'GET':
        form.product_id.data = selected_product_id

    if form.validate_on_submit():
        selected_product = Product.query.filter_by(id=form.product_id.data, user_id=current_user.id).first_or_404()
        try:
            ticket_id = _create_helpdesk_complaint_ticket(
                selected_product,
                form.title.data.strip(),
                form.description.data.strip(),
            )
            flash(f'Je klacht is verzonden naar Odoo Helpdesk als ticket #{ticket_id}.', 'success')
            return redirect(url_for('main.complaints', product_id=selected_product.id))
        except Exception as error:
            current_app.logger.exception('Helpdesk complaint submission failed')
            flash(f'Je klacht kon niet worden verzonden naar Odoo Helpdesk: {error}', 'danger')

    selected_product = Product.query.filter_by(id=form.product_id.data or selected_product_id, user_id=current_user.id).first()
    return render_template('complaints.html', form=form, products=products, selected_product=selected_product)

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
