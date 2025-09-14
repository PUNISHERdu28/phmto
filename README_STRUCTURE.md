# 📁 Structure du Projet Restructuré

## 🏗️ Architecture Modulaire

```
📦 Projet Root
├── 🚀 solana-api/              # API Solana Wallet Management
│   ├── blueprints/             # Routes API Flask
│   ├── rug/                    # Logique métier Solana
│   ├── middleware/             # Authentification
│   ├── services/               # Services transversaux
│   ├── static/                 # Swagger UI & Assets
│   ├── templates/              # Templates web
│   └── flask_app.py            # Application Flask principale
│
├── 📊 analytics/               # Module Analyse IA (Séparé)
│   ├── ai_analyzer.py          # Moteur IA (Claude/GPT)
│   ├── data_processor.py       # Traitement données
│   ├── visualization.py        # Graphiques Plotly
│   ├── export_handler.py       # Export analyses
│   └── main_analytics.py       # Application Streamlit
│
├── ⚙️ shared/                  # Configuration partagée
│   ├── config.py               # Config globale
│   └── api_utils.py            # Utilitaires communs
│
├── 🚀 launchers/               # Scripts de démarrage
│   ├── start_solana_api.py     # Démarre API Solana (port 8000)
│   └── start_analytics.py      # Démarre Analytics (port 5000)
│
└── 📋 Root files               # Config projet
    ├── requirements.txt
    ├── README.md
    └── pyproject.toml
```

## 🎯 Applications Séparées

### 🔗 API Solana (Port 8000)
- Gestion wallets Solana
- Transactions & transferts
- Intégration Pump.fun
- Swagger UI: http://localhost:8000/docs

### 📊 Analytics IA (Port 5000)  
- Interface Streamlit
- Upload & analyse de données
- Visualisations interactives
- IA: Claude Sonnet 4 + GPT-5

## 🚀 Comment lancer

**API Solana uniquement:**
```bash
python launchers/start_solana_api.py
```

**Analytics IA uniquement:**
```bash
python launchers/start_analytics.py
```

**Les deux en parallèle:**
```bash
# Terminal 1
python launchers/start_solana_api.py

# Terminal 2  
python launchers/start_analytics.py
```

## 💡 Avantages de cette structure

✅ **Séparation claire** des responsabilités
✅ **Modules indépendants** mais connectables  
✅ **Démarrage sélectif** des applications
✅ **Architecture scalable** et maintenable
✅ **Réutilisabilité** des composants