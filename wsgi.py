"""WSGI entrypoint for production hosting (PythonAnywhere, Render, Gunicorn)."""
import os, sys
basedir = os.path.abspath(os.path.dirname(__file__))
if basedir not in sys.path:
    sys.path.insert(0, basedir)

from app import create_app
env_config = os.environ.get('FLASK_CONFIG', 'production')
application = create_app(env_config)
app = application

if __name__ == '__main__':
    application.run()
