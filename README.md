# Solana Wallet API (Flask) — v2.1

API Flask pour gérer des projets “wallet factory” sur Solana (devnet/testnet/mainnet), avec séparation **UI** / **métier**.  
## Nouveaux endpoints (devnet, transactions réelles via `solders`)

> Prérequis: définir l’URL RPC (devnet) dans la config:
> `DEFAULT_RPC=https://api.devnet.solana.com` et `CLUSTER=devnet`.

### 1) Transférer des SOL (A → B)
`POST /api/v1/wallets/{wallet_id}/transfer`

```bash
curl -s -X POST "http://localhost:8000/api/v1/wallets/wlt_123/transfer" \
  -H "Content-Type: application/json" -H "x-api-key: $API_KEY" \
  -d '{"recipient_pubkey":"DEST_BASE58","amount_sol":0.5}'

## ✨ Fonctionnalités
- Démarrage par **cluster** (`CLUSTER=devnet|testnet|mainnet`) + override par **requête** (`cluster` ou `rpc_url`).
- **Clés API par cluster** (`API_KEY_DEVNET`, `API_KEY_TESTNET`, `API_KEY_MAINNET`).
- **Projets** (création, listing, détail) et **wallets** rattachés au projet.
- **Wallets nommés** automatiquement (`Wallet 1..N`) + meta persistée.
- **Soldes** en temps réel via RPC.
- **Airdrop devnet** avec **retries + polling** jusqu’à 60s max.
- **Transfert SOL** avec pré-check du solde.
- Endpoints prêts pour intégration **UI** ou **bot Telegram**.

---

## 🚀 Installation

### Windows PowerShell
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
$env:CLUSTER="devnet"; $env:API_KEY_DEVNET="dev-secret"; $env:DATA_DIR="./data"
python app.py
```

### Linux / macOS (bash/zsh)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
export CLUSTER=devnet API_KEY_DEVNET=dev-secret DATA_DIR=./data
python app.py
```

Vérifier :
```bash
curl http://localhost:8000/health
```

---

## ⚙️ Variables d’environnement

- `CLUSTER` : `devnet` | `testnet` | `mainnet` (par défaut : mainnet).
- `API_KEY` : clé par défaut si tu n’utilises pas les clés par cluster.
- `API_KEY_DEVNET`, `API_KEY_TESTNET`, `API_KEY_MAINNET` : clés API par réseau.
- `DATA_DIR` : dossier de données (`./data` par défaut).
- RPC optionnels (sinon presets) :
  - `SOLANA_DEVNET_RPC=https://api.devnet.solana.com`
  - `SOLANA_TESTNET_RPC=https://api.testnet.solana.com`
  - `SOLANA_MAINNET_RPC=https://api.mainnet-beta.solana.com`
- `DEFAULT_RPC` : override global.

> Priorité RPC : `rpc_url` (requête) > `cluster` (requête/ENV) > `DEFAULT_RPC`.

---

## 🔐 Authentification

Tous les endpoints (sauf `/health`) sont protégés.  
Entête HTTP :
```
Authorization: Bearer <votre_clé_api>
```

---

## 📚 Endpoints

### Santé
- `GET /health`  
  Retourne l’état, `cluster`, `default_rpc`.

### Projets
- `POST /api/v1/projects`  
  Body : `{ "name": "Mon projet" }`
- `GET /api/v1/projects`  
  Liste les projets existants.
- `GET /api/v1/projects/<project_id>`  
  Détails d’un projet.

### Wallets d’un projet
- `POST /api/v1/projects/<project_id>/wallets`  
  Crée N wallets dans le projet, nommés automatiquement (`Wallet 1..N`).  
  Exemple Body :
  ```json
  {
    "n": 3,
    "with_balance": true,
    "cluster": "devnet"
  }
  ```
- `GET /api/v1/projects/<project_id>/wallets?with_balance=true&cluster=devnet`  
  Liste tous les wallets d’un projet avec `address`, `name`, et `balance_sol`.

### Wallet isolé
- `GET /api/v1/wallets/<address>?cluster=devnet`  
  Infos d’un wallet (adresse, nom, solde, projet parent).

### Solde d’un wallet
- `GET /api/v1/wallets/<address>/balance?cluster=devnet`  
  Retourne `{ ok, address, balance_sol }`.

### Airdrop (DEVNET uniquement)
- `POST /api/v1/airdrop`  
  Exemple Body :
  ```json
  {
    "address": "<pubkey>",
    "sol": 0.2,
    "cluster": "devnet",
    "confirm_seconds": 60,
    "confirm_interval": 1,
    "retries": 3,
    "backoff_seconds": 1.5
  }
  ```
  Réponses possibles :
  - `201` avec `"confirmation":"balance_delta"` (sol crédité)
  - `201` avec `"confirmation":"signature"` (signature reçue mais pas de delta)
  - `202` avec `"confirmation":"none"` (pending)
  - `429` si rate-limit

### Transfert SOL
- `POST /api/v1/transfer/sol`  
  Body :
  ```json
  {
    "sender_private_key": "<clé privée base58>",
    "recipient_pubkey_b58": "<pubkey>",
    "amount_sol": 0.001,
    "cluster": "devnet"
  }
  ```

---

## 🧪 Exemples PowerShell

```powershell
$API="http://localhost:8000"
$H=@{ "Content-Type"="application/json"; "Authorization"="Bearer dev-secret" }

# Health
Invoke-RestMethod -Uri "$API/health" | ConvertTo-Json -Depth 6

# Créer projet
$Body=@{ name="projet-X" } | ConvertTo-Json
$proj=Invoke-RestMethod -Method POST -Uri "$API/api/v1/projects" -Headers $H -Body $Body
$PROJECT_ID=$proj.project.project_id

# Générer 6 wallets
$Body=@{ n=6; with_balance=$true; cluster="devnet" } | ConvertTo-Json
Invoke-RestMethod -Method POST -Uri "$API/api/v1/projects/$PROJECT_ID/wallets" -Headers $H -Body $Body | ConvertTo-Json -Depth 6

# Lister wallets
Invoke-RestMethod -Method GET -Uri "$API/api/v1/projects/$PROJECT_ID/wallets?with_balance=true&cluster=devnet" -Headers $H | ConvertTo-Json -Depth 6

# Infos d’un wallet
$ADDR="<adresse_wallet>"
Invoke-RestMethod -Method GET -Uri "$API/api/v1/wallets/$ADDR?cluster=devnet" -Headers $H | ConvertTo-Json -Depth 6

# Airdrop
$Body=@{ address=$ADDR; sol=0.2; cluster="devnet"; confirm_seconds=60 } | ConvertTo-Json
Invoke-RestMethod -Method POST -Uri "$API/api/v1/airdrop" -Headers $H -Body $Body | ConvertTo-Json -Depth 8
```

---

## 🐳 Docker

```bash
docker build -t solana-api:v2 .
docker run -e CLUSTER=devnet -e API_KEY_DEVNET=dev-secret -e DATA_DIR=/data \
  -p 8000:8000 -v $PWD/data:/data solana-api:v2
```

---

## 🛠 Roadmap (améliorations futures)

1. **Renommer un wallet**  
   `PATCH /api/v1/projects/<project_id>/wallets/<address>` → `{ "name": "Trading Bot #1" }`.

2. **Suppression**  
   - `DELETE /api/v1/projects/<project_id>`  
   - `DELETE /api/v1/projects/<project_id>/wallets/<address>`

3. **OpenAPI/Swagger**  
   Spécification `openapi.yaml` + Swagger UI pour front/bot.

4. **Pagination & filtres**  
   Sur `/projects` et `/wallets`.

5. **Sécurité & Ops**  
   - Rate limiting par IP/clé.  
   - Logs JSON + observabilité (Prometheus, Grafana).  
   - Intégration Sentry.

6. **SPL Tokens**  
   - `GET /wallets/<address>/spl-balances`  
   - `POST /transfer/spl`  
   - Endpoint pour créer/mint un token SPL.

7. **Webhooks / Callbacks**  
   Pour notifier l’UI quand une tx est confirmée.

8. **Intégration Telegram**  
   Bot connecté à l’API (création projets, wallets, soldes, transferts).

9. **CI/CD & Tests**  
   - Tests unitaires (pytest).  
   - GitHub Actions.  
   - Déploiement Docker multi-env (`dev`, `stage`, `prod`).

---

## 📄 Licence
DProtDB Tout droit réservé **Solana**.


---

## 🆕 Mises à jour (2025-09-02)
- ✅ Endpoint **DELETE /api/v1/projects/{project_id}** : sauvegarde complète (JSON) puis déplacement du projet dans `data/.trash/`.
- ✅ Endpoint **DELETE /api/v1/projects/{project_id}/wallets/{address}** : sauvegarde JSON du wallet puis retrait de la liste.
- ✅ **Swagger UI** mis à jour (`/docs`) + **openapi.yaml** enrichi.
- ✅ Docstrings et commentaires ajoutés sur toutes les routes principales.
- ✅ Guide **PowerShell** pour tester l'API avec ou sans API_KEY.

### Endpoints récapitulés
- `GET  /health`
- `GET  /api/v1/projects`
- `POST /api/v1/projects` { "name": "Mon projet" }
- `GET  /api/v1/projects/{project_id}`
- `DELETE /api/v1/projects/{project_id}`  ← *avec sauvegarde + corbeille*
- `POST /api/v1/projects/{project_id}/wallets` { "n": 3 }
- `GET  /api/v1/wallets/{address}/balance?cluster=devnet`
- `POST /api/v1/transfer/sol` { "sender_private_key": [...], "recipient_pubkey_b58": "...", "amount_sol": 0.001, "cluster": "devnet" }
- `DELETE /api/v1/projects/{project_id}/wallets/{address}` ← *backup individuel*

### PowerShell – exemples
```powershell
# API ouverte (pas d'auth)
Remove-Item Env:API_KEY -ErrorAction SilentlyContinue
$env:REQUIRE_AUTH = "false"
python .\app.py

# API protégée (Bearer)
$env:API_KEY = "mon_secret_ultra_long"
$env:REQUIRE_AUTH = "true"
python .\app.py

# Appels
$h = @{ Authorization = "Bearer $env:API_KEY" }
Invoke-RestMethod "http://localhost:8000/health"
Invoke-RestMethod "http://localhost:8000/api/v1/projects" -Headers $h
Invoke-RestMethod "http://localhost:8000/api/v1/projects" -Headers $h -Method POST -ContentType "application/json" -Body (@{name="Test"}|ConvertTo-Json)
Invoke-RestMethod "http://localhost:8000/api/v1/projects/<PID>/wallets" -Headers $h -Method POST -ContentType "application/json" -Body (@{n=2}|ConvertTo-Json)
Invoke-RestMethod "http://localhost:8000/api/v1/wallets/<ADDR>/balance?cluster=devnet" -Headers $h
Invoke-RestMethod "http://localhost:8000/api/v1/projects/<PID>/wallets/<ADDR>" -Headers $h -Method DELETE
Invoke-RestMethod "http://localhost:8000/api/v1/projects/<PID>" -Headers $h -Method DELETE
```


## 🚀 Phmto v3.1 — Nouveaux endpoints (transactions réelles via solders)

> Prérequis: `DEFAULT_RPC=https://api.devnet.solana.com`, `CLUSTER=devnet`

### 1) Transférer des SOL (A → B) par `wallet_id`
`POST /api/v1/wallets/{wallet_id}/transfer`

```bash
curl -s -X POST "http://localhost:8000/api/v1/wallets/WID12345/transfer"   -H "Content-Type: application/json" -H "x-api-key: $API_KEY"   -d '{"recipient_pubkey":"DEST_BASE58","amount_sol":0.1}'
```

### 2) Mixer des SOL entre wallets (historique détaillé)
`POST /api/v1/wallets/mix`

```bash
curl -s -X POST "http://localhost:8000/api/v1/wallets/mix"   -H "Content-Type: application/json" -H "x-api-key: $API_KEY"   -d '{"wallet_ids":["WID_A","WID_B","WID_C"],"strategy":"random"}' | jq
```

### 3) Consolider vers un wallet cible (skip self-send)
`POST /api/v1/wallets/consolidate/{target_wallet_id}`

```bash
curl -s -X POST "http://localhost:8000/api/v1/wallets/consolidate/WID_TARGET"   -H "Content-Type: application/json" -H "x-api-key: $API_KEY"   -d '{"min_reserve_sol":0.00001}'
```


## 🚀 v3.5 — Changements majeurs

- Endpoints projets: create/list/rename/delete, import/export JSON
- Endpoints wallets: create/list/rename/detail/delete, import/export
- Airdrop devnet, transfert A→B (wallet_id→pubkey), mix, consolidate
- Token: edit/reset + création via Pump.fun (clé API requise)
- Rendus JSON uniformisés pour les wallets (id, name, address, balance_sol, created_at, private_key)
