#!/usr/bin/env bash
# ===========================
# Script d'installation et de lancement de l'application Flask
# Environnement : Linux / macOS (bash/zsh)
# ===========================

# 1. Stopper le script si une commande échoue
set -e

# 2. Crée un environnement virtuel Python local dans le dossier .venv
python -m venv .venv

# 3. Active l'environnement virtuel
source .venv/bin/activate

# 4. Installe toutes les dépendances listées dans requirements.txt
pip install -r requirements.txt

# 5. Copie le fichier .env.example vers .env si .env n'existe pas déjà
cp -n .env.example .env || true

# 6. Définit les variables d'environnement nécessaires au projet
export CLUSTER=devnet
export API_KEY_DEVNET=dev-secret
export DATA_DIR=./data

# 7. Lance l'application Flask
python app.py

# 8. (Optionnel) Vérifie que l'API est bien accessible avec curl
# curl http://localhost:8000/health
