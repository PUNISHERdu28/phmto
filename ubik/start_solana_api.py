#!/usr/bin/env python3
"""
⚔️ UBIK - The Facilitator Oracle
"""
import sys
import os

# Ajouter le chemin vers les modules
root_dir = os.path.dirname(os.path.dirname(__file__))
sys.path.append(root_dir)
sys.path.append(os.path.join(root_dir, 'conrad'))
sys.path.append(os.path.join(root_dir, 'femto'))

# Lancer l'application Flask
if __name__ == "__main__":
    # Importer depuis le nouveau chemin
    import importlib.util
    flask_app_path = os.path.join(root_dir, 'femto', 'flask_app.py')
    spec = importlib.util.spec_from_file_location("flask_app", flask_app_path)
    flask_app = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(flask_app)
    
    app = flask_app.create_app()
    print("⚔️ FEMTO - The Fallen Angel awakens...")
    print("🗡️ Swagger UI: http://0.0.0.0:8000/docs")
    
    app.run(
        host="0.0.0.0", 
        port=8000,
        debug=True
    )