# 🚀 Rug API v3.6 - Solana Wallet Management

![Version](https://img.shields.io/badge/version-3.6.0-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)
![Flask](https://img.shields.io/badge/Flask-3.0%2B-red.svg)
![Solana](https://img.shields.io/badge/Solana-devnet%20%7C%20testnet%20%7C%20mainnet-blueviolet.svg)

**API Flask pour gérer des projets et wallets Solana sur devnet/mainnet/testnet.**

## 🎯 Fonctionnalités Principales

### 💼 Gestion de Projets
- ✅ Création, modification et suppression de projets
- ✅ Système de sauvegarde automatique et d'import/export  
- ✅ Organisation hiérarchique des wallets par projet

### 🔐 Gestion de Wallets
- ✅ Génération automatique de wallets Solana
- ✅ Import de wallets existants via clé privée
- ✅ Consultation des soldes en temps réel
- ✅ Sauvegarde locale des wallets
- ✅ Holdings SPL Token avec métadonnées

### 💸 Système de Transferts
- ✅ Airdrop SOL sur devnet (faucet intégré)
- ✅ Transferts SOL entre wallets avec gestion des frais
- ✅ Mixing automatique (stratégies random/roundrobin) 
- ✅ Consolidation intelligente des soldes

### 🪙 Gestion de Tokens
- ✅ Configuration des métadonnées de tokens
- ⚠️ Intégration Pump.fun (nécessite API key)
- ✅ Support complet des standards SPL Token
- ⚠️ Achat/vente de tokens (simulation, Jupiter API requis)
- ⚠️ Prix tokens (simulation, CoinGecko/Jupiter API requis)

### 🛡️ Sécurité & Limitations
- ✅ Authentification par clé API (header `Authorization`)
- ⚠️ Clés privées stockées localement (non chiffrées)
- ✅ Logs d'activité
- ✅ Support multi-cluster (devnet/testnet/mainnet)
- ✅ Interface Swagger UI avec thème sombre

---

## ⚡ Installation & Configuration

### 📋 Prérequis

- **Python 3.11+** (recommandé 3.11 pour compatibilité Solana)
- **Git** pour cloner le repository

### 📦 Installation

```bash
# Cloner le repository
git clone https://github.com/votre-repo/rug-api-v3.6.git
cd rug-api-v3.6

# Créer un environnement virtuel Python
python3.11 -m venv venv
source venv/bin/activate  # Linux/macOS
# ou
venv\Scripts\activate     # Windows

# Installer les dépendances
pip install -r requirements.txt
```

### ⚙️ Variables d'Environnement

Créez un fichier `.env` à la racine du projet :

```bash
# === Configuration Core ===
DATA_DIR=./data
PORT=8000
REQUIRE_AUTH=false

# === Configuration Solana ===
DEFAULT_RPC=https://api.devnet.solana.com
CLUSTER=devnet

# === Authentification ===
API_KEY=your-secret-api-key-here

# === Intégrations Tierces (Optionnelles) ===
# Pump.fun (création de tokens)
PUMPFUN_API_KEY=your-pumpfun-api-key

# Jupiter (DEX swaps) - Simulation si absent
JUPITER_API_KEY=your-jupiter-api-key
ENABLE_TOKEN_SIMULATION=true

# CoinGecko (prix tokens) - Simulation si absent
COINGECKO_API_KEY=your-coingecko-api-key
ENABLE_PRICE_SIMULATION=true

# === Développement & Debug ===
FLASK_ENV=development
FLASK_DEBUG=true
```

### 🚀 Démarrage

```bash
# Mode développement (recommandé pour commencer)
export REQUIRE_AUTH=false
export CLUSTER=devnet
python app.py

# Ou avec toutes les variables
DATA_DIR=./data DEFAULT_RPC=https://api.devnet.solana.com CLUSTER=devnet REQUIRE_AUTH=false API_KEY="" PORT=8000 python app.py
```

L'API sera accessible sur **http://localhost:8000**

### 🎨 Interface Swagger UI

Documentation interactive disponible sur : **http://localhost:8000/docs**

---

## 🔧 Endpoints Documentation

### 🩺 Health Check

**`GET /health`** - Vérification de l'état de santé de l'API

```bash
curl http://localhost:8000/health
```

**Réponse :**
```json
{
  "ok": true,
  "service": "solana-api",
  "time": "2025-09-14T17:30:00.000Z",
  "data_dir": "./data",
  "default_rpc": "https://api.devnet.solana.com",
  "cluster": "devnet",
  "api_key_set": false
}
```

---

### 📂 Gestion des Projets

#### Lister tous les projets
**`GET /api/v1/projects`**

```bash
curl -H "Authorization: Bearer your-api-key" \
     http://localhost:8000/api/v1/projects
```

#### Créer un nouveau projet
**`POST /api/v1/projects`**

```bash
curl -X POST \
     -H "Authorization: Bearer your-api-key" \
     -H "Content-Type: application/json" \
     -d '{"name": "Mon Nouveau Memecoin"}' \
     http://localhost:8000/api/v1/projects
```

#### Détail d'un projet
**`GET /api/v1/projects/{project_id}`**

#### Renommer un projet
**`PATCH /api/v1/projects/{project_id}`**

#### Supprimer un projet (avec backup)
**`DELETE /api/v1/projects/{project_id}`**

#### Export/Import de projets
**Export :** `GET /api/v1/projects/{project_id}/export`
**Import :** `POST /api/v1/projects/import`

---

### 🔐 Gestion des Wallets

#### Générer des wallets pour un projet
**`POST /api/v1/projects/{project_id}/wallets`**

```bash
curl -X POST \
     -H "Authorization: Bearer your-api-key" \
     -H "Content-Type: application/json" \
     -d '{"n": 10}' \
     http://localhost:8000/api/v1/projects/c3a1d93e/wallets
```

#### Lister les wallets d'un projet
**`GET /api/v1/projects/{project_id}/wallets`**

```bash
# Sans les soldes
curl -H "Authorization: Bearer your-api-key" \
     http://localhost:8000/api/v1/projects/c3a1d93e/wallets

# Avec les soldes (plus lent)
curl -H "Authorization: Bearer your-api-key" \
     "http://localhost:8000/api/v1/projects/c3a1d93e/wallets?with_balance=true"
```

#### Détail d'un wallet
**`GET /api/v1/wallets/{wallet_id}`**

#### Solde d'une adresse
**`GET /api/v1/wallets/{address}/balance`**

#### Holdings SPL Token d'un wallet
**`GET /api/v1/wallets/{wallet_id}/tokens`**

---

### 💸 Transferts & Airdrop

#### Airdrop SOL (Devnet uniquement)
**`POST /api/v1/airdrop`**

```bash
curl -X POST \
     -H "Content-Type: application/json" \
     -d '{
       "address": "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM",
       "sol": 1.0
     }' \
     http://localhost:8000/api/v1/airdrop
```

#### Transfert SOL depuis un wallet
**`POST /api/v1/wallets/{wallet_id}/transfer`**

```bash
curl -X POST \
     -H "Authorization: Bearer your-api-key" \
     -H "Content-Type: application/json" \
     -d '{
       "recipient_pubkey": "DjVE6JNiYqPL2QXyCUUh8rNjHrbz9hXHNYt99MQ59qw1",
       "amount_sol": 0.5
     }' \
     http://localhost:8000/api/v1/wallets/9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM/transfer
```

#### Mixing de wallets (mélange automatique)
**`POST /api/v1/wallets/mix`**

#### Consolidation vers un wallet cible
**`POST /api/v1/wallets/consolidate/{target_wallet_id}`**

---

### 🪙 Gestion des Tokens

#### Éditer les métadonnées du token d'un projet
**`PATCH /api/v1/projects/{project_id}/token`**

```bash
curl -X PATCH \
     -H "Authorization: Bearer your-api-key" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "SuperMeme Token",
       "symbol": "SMEME", 
       "description": "Le memecoin le plus fou de Solana !",
       "image_uri": "https://example.com/image.png",
       "website": "https://supermeme.fun",
       "twitter": "https://twitter.com/supermeme",
       "telegram": "https://t.me/supermeme"
     }' \
     http://localhost:8000/api/v1/projects/c3a1d93e/token
```

#### Créer le token via Pump.fun
**`POST /api/v1/projects/{project_id}/token/create`** ⚠️ **Nécessite PUMPFUN_API_KEY**

```bash
# ⚠️ Requiert une clé API Pump.fun valide
curl -X POST \
     -H "Authorization: Bearer your-api-key" \
     http://localhost:8000/api/v1/projects/c3a1d93e/token/create
```

**Réponse sans API key :**
```json
{
  "ok": false,
  "error": "PUMPFUN_API_KEY missing"
}
```

#### Acheter des tokens via DEX (SIMULATION)
**`POST /api/v1/tokens/purchase`** ⚠️ **SIMULATION UNIQUEMENT**

```bash
# ⚠️ Nécessite JUPITER_API_KEY ou ENABLE_TOKEN_SIMULATION=true
curl -X POST \
     -H "Authorization: Bearer your-api-key" \
     -H "Content-Type: application/json" \
     -d '{
       "wallet_id": "wallet-id",
       "token_address": "TokenAddressHere...",
       "amount_sol": 0.1,
       "slippage_percent": 1.0,
       "project_id": "c3a1d93e"
     }' \
     http://localhost:8000/api/v1/tokens/purchase
```

**Réponse simulation :**
```json
{
  "ok": false,
  "simulation": true,
  "purchase": {
    "wallet_id": "wallet-id",
    "amount_sol_spent": 0.1,
    "estimated_tokens_received": 5000,
    "status": "SIMULATION_ONLY"
  },
  "warning": "This is a SIMULATION - no real transaction occurred"
}
```

#### Obtenir le prix d'un token (SIMULATION)
**`GET /api/v1/tokens/{token_address}/price`** ⚠️ **SIMULATION UNIQUEMENT**

**Réponse simulation :**
```json
{
  "ok": false,
  "simulation": true,
  "token_address": "TokenAddressHere...",
  "price": {
    "usd": 0.00123,
    "sol": 0.0000082,
    "market_cap_usd": 150000,
    "change_24h_percent": 25.5
  },
  "data_source": "SIMULATION_ONLY",
  "warning": "This is SIMULATED price data - not real market data"
}
```

---

## 🔒 Sécurité & Authentification

### 🛡️ Configuration de Sécurité

#### Mode Développement (Authentification Désactivée)
```bash
export REQUIRE_AUTH=false
export API_KEY=""
```

#### Mode Production (Authentification Activée)
```bash
export REQUIRE_AUTH=true
export API_KEY="votre-cle-api-super-secrete-ici"
```

### 🔑 Authentification par API Key

L'API utilise l'authentification par **Bearer Token** dans le header `Authorization` :

```bash
# Format correct
curl -H "Authorization: Bearer votre-cle-api" \
     http://localhost:8000/api/v1/projects

# Alternative (header x-api-key également supporté)
curl -H "x-api-key: votre-cle-api" \
     http://localhost:8000/api/v1/projects
```

### ⚠️ Limitations de Sécurité Importantes

#### 1. Stockage des Clés Privées
- ⚠️ Les clés privées sont stockées **en clair** dans les fichiers JSON locaux
- ✅ **Aucune** clé privée n'est loggée
- ✅ Export des clés privées **désactivé** par défaut via API
- ⚠️ Backups automatiques **sans chiffrement** (protéger le répertoire data/)

#### 2. Airdrop (Devnet Uniquement)
```bash
# ✅ Autorisé sur devnet
export CLUSTER=devnet
curl -d '{"address": "..."}' http://localhost:8000/api/v1/airdrop

# ❌ Bloqué sur mainnet
export CLUSTER=mainnet  
curl -d '{"address": "..."}' http://localhost:8000/api/v1/airdrop
# Retourne: 400 Bad Request - airdrop allowed only on devnet
```

#### 3. Rate Limiting
```bash
# ⚠️ LIMITATION : L'API n'implémente pas encore de rate limiting
# En production, implémenter rate limiting externe (nginx, reverse proxy)
# ou middleware Flask-Limiter
```

---

## 🐛 Troubleshooting

### ❓ Problèmes Courants

#### 1. Erreur d'Authentification
```bash
# Problème
curl http://localhost:8000/api/v1/projects
# {"ok": false, "error": "unauthorized"}

# Solution
export API_KEY="your-api-key"
curl -H "Authorization: Bearer $API_KEY" http://localhost:8000/api/v1/projects

# Ou désactiver l'auth pour le développement
export REQUIRE_AUTH=false
```

#### 2. Airdrop Échoue sur Mainnet
```bash
# Problème
curl -d '{"address": "..."}' http://localhost:8000/api/v1/airdrop
# {"ok": false, "error": "airdrop allowed only on devnet"}

# Solution
export CLUSTER=devnet
export DEFAULT_RPC=https://api.devnet.solana.com
python app.py
```

#### 3. Token Purchase/Price Failed
```bash
# Problème
curl -X POST ... /api/v1/tokens/purchase
# {"ok": false, "error": "Token purchase not implemented"}

# Solution: Activer la simulation
export ENABLE_TOKEN_SIMULATION=true
# Ou obtenir une vraie clé Jupiter API
export JUPITER_API_KEY=your-real-api-key
```

---

## 📞 Contact & Support

- 📧 **Email :** support@rug-api.com

---

## 📄 License

MIT License

---

## ⚠️ Avertissement Important

Cette documentation décrit l'état actuel de l'API. Certaines fonctionnalités avancées comme l'intégration Jupiter DEX et les prix en temps réel nécessitent des clés API tierces et peuvent être en mode simulation uniquement.

---

**Documentation complète et interactive disponible sur [http://localhost:8000/docs](http://localhost:8000/docs)**

**⚡ Rug API v3.6 - Solana Wallet Management Platform 🚀**