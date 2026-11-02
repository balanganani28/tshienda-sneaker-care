"""Development runner for Tshienda Sneaker Care."""
import os, sys
basedir = os.path.abspath(os.path.dirname(__file__))
if basedir not in sys.path:
    sys.path.insert(0, basedir)

from app import create_app
app = create_app('development')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting Tshienda server on http://127.0.0.1:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)
