from dotenv import load_dotenv
load_dotenv()
from app import create_app
import app.routes as routes
app = create_app()
with app.app_context():
    try:
        res = routes._lookup_odoo_product_by_barcode('0000000000000')
        print('RESULT:', res)
    except Exception as e:
        print('EXCEPTION:', repr(e))
