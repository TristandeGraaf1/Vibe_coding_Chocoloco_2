from dotenv import load_dotenv
from app import create_app

# Load environment variables from .env for local development
load_dotenv()

app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

