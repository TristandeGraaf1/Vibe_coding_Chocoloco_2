import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///chocoloco.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ODOO_URL = os.environ.get('ODOO_URL', '')
    ODOO_DB = os.environ.get('ODOO_DB', '')
    ODOO_USERNAME = os.environ.get('ODOO_USERNAME', '')
    ODOO_PASSWORD = os.environ.get('ODOO_PASSWORD', '')
    ODOO_LIVECHAT_SUPPORT_EMAILS = os.environ.get('ODOO_LIVECHAT_SUPPORT_EMAILS') or os.environ.get('ODOO_USERNAME', '')
