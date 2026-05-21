#!/usr/bin/env python3
"""
Quick script to validate Odoo XML-RPC connectivity using values from .env
Run: python scripts/test_odoo_connection.py
"""
import os
import traceback
from dotenv import load_dotenv
import xmlrpc.client

load_dotenv()

ODOO_URL = os.environ.get('ODOO_URL')
ODOO_DB = os.environ.get('ODOO_DB')
ODOO_USERNAME = os.environ.get('ODOO_USERNAME')
ODOO_PASSWORD = os.environ.get('ODOO_PASSWORD')

print('Using ODOO_URL:', ODOO_URL)
print('Using ODOO_DB:', ODOO_DB)
print('Using ODOO_USERNAME:', ODOO_USERNAME)

if not all([ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD]):
    print('Missing one or more ODOO_* environment variables. Check your .env')
    raise SystemExit(1)

try:
    common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")
    uid = common.authenticate(ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD, {})
    print('Authenticated uid:', uid)
    if not uid:
        print('Authentication failed: uid is falsy')
        raise SystemExit(2)

    models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object")
    # simple read: current user
    user = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'res.users', 'search_read', [[['login', '=', ODOO_USERNAME]]], {'limit': 1})
    print('res.users search_read result:', user)

    # quick product search to test object calls
    try:
        prods = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, 'product.product', 'search', [[['id', '>', 0]]], {'limit': 1})
        print('product.product sample id:', prods[0] if prods else 'none')
    except Exception as e:
        print('product.product call failed:', e)

    print('Odoo connectivity test succeeded')
except Exception:
    print('Odoo connectivity test failed:')
    traceback.print_exc()
