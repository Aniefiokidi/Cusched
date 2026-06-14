import sys
import os
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Declared at top level so Vercel's static scanner can find it
app = None
_import_error = None

try:
    from app import app
except Exception:
    _import_error = traceback.format_exc()

    from flask import Flask
    app = Flask(__name__)

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def _startup_error_page(path):
        return (
            "<html><body style='font-family:monospace;padding:24px;'>"
            "<h2 style='color:#c62828;'>App failed to start</h2>"
            "<pre style='background:#fafafa;padding:16px;border-radius:6px;"
            "border:1px solid #e2e8f0;white-space:pre-wrap;word-break:break-all;'>"
            + _import_error.replace("<", "&lt;").replace(">", "&gt;")
            + "</pre></body></html>"
        ), 500
