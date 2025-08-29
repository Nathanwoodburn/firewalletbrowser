import os
import sys
import platform
from main import app
from waitress import serve


threads = 4

def gunicornServer():
    from gunicorn.app.base import BaseApplication
    class GunicornApp(BaseApplication):
        def __init__(self, app, options=None):
            self.options = options or {}
            self.application = app
            super().__init__()

        def load_config(self):
            for key, value in self.options.items():
                if key in self.cfg.settings and value is not None: # type: ignore
                    self.cfg.set(key.lower(), value) # type: ignore

        def load(self):
            return self.application
    options = {
        'bind': '0.0.0.0:5000',
        'workers': 2,
        'threads': threads,
    }
    gunicorn_app = GunicornApp(app, options)
    print(f'Starting server with Gunicorn on {platform.system()} with {threads} threads...', flush=True)
    gunicorn_app.run()
    

if __name__ == '__main__':
    # Check if --gunicorn is in the command line arguments
    if "--gunicorn" in sys.argv:
        gunicornServer()
        sys.exit()

    print(f'Starting server with Waitress on {platform.system()} with {threads} threads...', flush=True)
    print(f'Press Ctrl+C to stop the server', flush=True)
    print(f'Serving on http://0.0.0.0:5000/', flush=True)
    serve(app, host="0.0.0.0", port=5000, threads=threads)
