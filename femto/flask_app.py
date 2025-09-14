
# -*- coding: utf-8 -*-
import os, sys
from flask import Flask, jsonify, redirect
from datetime import datetime
from dotenv import load_dotenv
from flask import send_from_directory
import os

load_dotenv()
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(CURRENT_DIR)
from conrad.config import load_settings

def create_app() -> Flask:
    app = Flask(__name__)
    app.config.update(load_settings())
    from blueprints.projects import bp as projects_bp
    from blueprints.wallets import bp as wallets_bp
    from blueprints.transfers import bp as transfers_bp
    from blueprints.utils import bp as utils_bp
    from blueprints.tokens import bp_tokens as tokens_bp
    from blueprints.tokens import bp_tokens_general as tokens_general_bp
    app.register_blueprint(projects_bp)
    app.register_blueprint(wallets_bp)
    app.register_blueprint(transfers_bp)
    app.register_blueprint(utils_bp)
    app.register_blueprint(tokens_bp)
    app.register_blueprint(tokens_general_bp)


    # --- Swagger UI ---

    # Route simple pour Swagger UI par défaut
    @app.route('/docs')
    def swagger_ui():
        from flask import render_template_string
        template = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>Rug API v3.6 (Solana Wallet Management)</title>
  <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist/swagger-ui.css" />
  <link rel="icon" type="image/png" href="https://unpkg.com/swagger-ui-dist/favicon-32x32.png" sizes="32x32" />
  <link rel="icon" type="image/png" href="https://unpkg.com/swagger-ui-dist/favicon-16x16.png" sizes="16x16" />
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://unpkg.com/swagger-ui-dist/swagger-ui-bundle.js"></script>
  <script src="https://unpkg.com/swagger-ui-dist/swagger-ui-standalone-preset.js"></script>
  <script>
    window.onload = function() {
      const ui = SwaggerUIBundle({
        url: "/static/openapi.yaml",
        dom_id: '#swagger-ui',
        deepLinking: true,
        presets: [
          SwaggerUIBundle.presets.apis,
          SwaggerUIStandalonePreset
        ],
        plugins: [
          SwaggerUIBundle.plugins.DownloadUrl
        ],
        layout: "StandaloneLayout"
      });
    };
  </script>
</body>
</html>
        """
        return render_template_string(template)

        # Servir les fichiers statiques (openapi.yaml)
    @app.route("/static/<path:filename>")
    def static_files(filename):
        # 'static' est un dossier au même niveau que app.py
        static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
        return send_from_directory(static_dir, filename)

    # Route racine qui redirige vers la documentation Swagger
    @app.get("/")
    def root():
        return redirect("/docs", code=302)
    
    # Route favicon pour éliminer les erreurs 404
    @app.get("/favicon.ico")
    def favicon():
        return redirect("https://unpkg.com/swagger-ui-dist/favicon-32x32.png", code=302)
    
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
