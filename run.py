import os
import sys
from pathlib import Path


def _reexec_into_local_venv():
    if sys.prefix != sys.base_prefix:
        return

    project_root = Path(__file__).resolve().parent

    if os.name == 'nt':
        candidate = project_root / '.venv' / 'Scripts' / 'python.exe'
    else:
        candidate = project_root / '.venv' / 'bin' / 'python'

    if candidate.exists():
        os.execv(str(candidate), [str(candidate), str(Path(__file__).resolve())] + sys.argv[1:])


_reexec_into_local_venv()

from dotenv import load_dotenv
from app import create_app

# Load environment variables from .env for local development
load_dotenv()

app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

