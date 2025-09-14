
# -*- coding: utf-8 -*-
import os, sys
from flask import Flask, jsonify
from datetime import datetime
from dotenv import load_dotenv
from flask_swagger_ui import get_swaggerui_blueprint
from flask import send_from_directory
import os

load_dotenv()
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(CURRENT_DIR)
from config import load_settings

def create_app() -> Flask:
    app = Flask(__name__)
    app.config.update(load_settings())
    from blueprints.projects import bp as projects_bp
    from blueprints.wallets import bp as wallets_bp
    from blueprints.transfers import bp as transfers_bp
    from blueprints.utils import bp as utils_bp
    app.register_blueprint(projects_bp)
    app.register_blueprint(wallets_bp)
    app.register_blueprint(transfers_bp)
    app.register_blueprint(utils_bp)


        # --- Swagger UI ---
    SWAGGER_URL = "/docs"                     # URL où la doc sera servie
    API_SPEC_PATH = "/static/openapi.yaml"    # où se trouve le openapi.yaml

    swaggerui_bp = get_swaggerui_blueprint(
        SWAGGER_URL,
        API_SPEC_PATH,
        config={"app_name": "Rug API (Solana)"}  # titre dans l'UI
    )
    app.register_blueprint(swaggerui_bp, url_prefix=SWAGGER_URL)

        # Servir les fichiers statiques (openapi.yaml)
    @app.route("/static/<path:filename>")
    def static_files(filename):
        # 'static' est un dossier au même niveau que app.py
        static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
        return send_from_directory(static_dir, filename)

    
    @app.get("/health")
    def health():
        return jsonify({
            "ok": True,
            "service": "solana-api",
            "time": datetime.utcnow().isoformat() + "Z",
            "data_dir": app.config["DATA_DIR"],
            "default_rpc": app.config["DEFAULT_RPC"],
            "cluster": app.config.get("CLUSTER", ""),
            "api_key_set": bool(app.config.get("API_KEY")),
        })
    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")), debug=True)
