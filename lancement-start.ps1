
# ===========================
# Script d'installation et de lancement de l'application Flask
# Environnement : Windows PowerShell
# ===========================

# 1. Crée un environnement virtuel Python local dans le dossier .venv
python -m venv .venv

# 2. Active l'environnement virtuel
.venv\Scripts\Activate.ps1

# 3. Installe toutes les dépendances listées dans requirements.txt
pip install -r requirements.txt

# 4. Copie le fichier .env.example vers .env si .env n'existe pas déjà
# -Force permet d'écraser si besoin
Copy-Item .env.example .env -Force

# 5. Définit les variables d'environnement nécessaires au projet
# Ici on configure le cluster en "devnet", une API_KEY et le dossier data
$env:CLUSTER="devnet"
$env:API_KEY_DEVNET="dev-secret"
$env:DATA_DIR="./data"

# 6. Lance l'application Flask (app.py doit exister à la racine)
python -m flask run --port=8000

# 7. (Optionnel) Vérifie que l'API est bien accessible avec curl
# curl http://localhost:8000/health
