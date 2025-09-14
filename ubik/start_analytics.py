#!/usr/bin/env python3
"""
⚔️ UBIK - The Analytics Oracle
"""
import sys
import os
import subprocess

# Ajouter le chemin vers les modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Lancer l'application Streamlit Analytics
if __name__ == "__main__":
    analytics_path = os.path.join(os.path.dirname(__file__), '..', 'void', 'main_analytics.py')
    
    cmd = [
        "streamlit", "run", analytics_path,
        "--server.port", "5000",
        "--server.address", "0.0.0.0"
    ]
    
    print("⚔️ VOID - The All-Seeing awakens...")
    print(f"👁️ Interface disponible sur: http://0.0.0.0:5000")
    
    subprocess.run(cmd)