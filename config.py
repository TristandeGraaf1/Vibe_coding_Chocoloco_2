import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    INSTANCE_DIR = os.path.join(BASE_DIR, 'instance')
    os.makedirs(INSTANCE_DIR, exist_ok=True)

    database_url = os.environ.get('DATABASE_URL')
    if database_url:
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        SQLALCHEMY_DATABASE_URI = database_url
    else:
        SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(INSTANCE_DIR, 'chocoloco.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ODOO_URL = os.environ.get('ODOO_URL', '')
    ODOO_DB = os.environ.get('ODOO_DB', '')
    ODOO_USERNAME = os.environ.get('ODOO_USERNAME', '')
    ODOO_PASSWORD = os.environ.get('ODOO_PASSWORD', '')
    ODOO_LIVECHAT_SUPPORT_EMAILS = os.environ.get('ODOO_LIVECHAT_SUPPORT_EMAILS') or os.environ.get('ODOO_USERNAME', '')
    ODOO_HELPDESK_TEAM_NAME = os.environ.get('ODOO_HELPDESK_TEAM_NAME', 'Klantenservice')
    ODOO_HELPDESK_TEAM_ID = os.environ.get('ODOO_HELPDESK_TEAM_ID', '')
