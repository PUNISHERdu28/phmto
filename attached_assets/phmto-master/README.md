# ⚡ Solana Wallet API (Flask) — v3.5

API Flask pour gérer des projets “wallet factory” sur Solana (**devnet/testnet/mainnet**), avec séparation **UI** / **métier**.  
Compatible avec **bots Telegram 🤖**, **front-end UI 💻**, et intégrations externes.

---

## ✨ Nouveautés (v3.5)

- 🌐 **Multi-cluster** : `CLUSTER=devnet|testnet|mainnet` + override possible par requête (`cluster`, `rpc_url`).
- 🔑 **Clés API par cluster** : `API_KEY_DEVNET`, `API_KEY_TESTNET`, `API_KEY_MAINNET`.
- 📂 **Projets** : création, listing, détail, suppression, import/export JSON.
- 👛 **Wallets nommés automatiquement** (`Wallet 1..N`) avec persistance des métadonnées.
- 💰 **Soldes en temps réel** via RPC.
- 🎁 **Airdrop (devnet uniquement)** avec retries + polling (60s max).
- 🔄 **Transfert SOL** entre wallets avec pré-check du solde.
- 🌀 **Mix & Consolidation** de SOL entre wallets.
- 📜 **Swagger / OpenAPI 3.0** accessible via `/doc`.
- 🧪 **Tests unitaires intégrés** → stabilité renforcée.

---

## 📖 Documentation interactive

Une documentation interactive est disponible via **Swagger UI** :  
👉 [http://localhost:8000/doc](http://localhost:8000/doc)

> Permet de tester les endpoints directement depuis le navigateur, sans Postman ni cURL.  

---

## ⚙️ Variables d’environnement

- `CLUSTER` : `devnet` | `testnet` | `mainnet` (par défaut : mainnet).
- `API_KEY` : clé par défaut si les clés par cluster ne sont pas utilisées.
- `API_KEY_DEVNET`, `API_KEY_TESTNET`, `API_KEY_MAINNET` : clés API par réseau.
- `DATA_DIR` : dossier de données (`./data` par défaut).
- RPC custom :
  - `SOLANA_DEVNET_RPC=https://api.devnet.solana.com`
  - `SOLANA_TESTNET_RPC=https://api.testnet.solana.com`
  - `SOLANA_MAINNET_RPC=https://api.mainnet-beta.solana.com`
- `DEFAULT_RPC` : override global.

> 📌 Priorité RPC : `rpc_url` (requête) > `cluster` (requête/ENV) > `DEFAULT_RPC`.

---

## 🔐 Authentification

Tous les endpoints (sauf `/health`) sont protégés.  
🛡️ En-tête HTTP attendu :  
Authorization: Bearer <votre_clé_api>

---

## 📚 Endpoints principaux (OpenAPI v3.5)

### 🩺 Santé
- `GET /health`  
  ➝ Vérifie que l’API fonctionne.  
  **Réponse :**
  ```json
  { "status": "ok", "cluster": "devnet", "rpc_url": "https://api.devnet.solana.com" }
  ```
📂 Projets
POST /api/v1/projects → Crée un projet
Body :

```json

{ "name": "Mon projet" }
```
Réponse :

```json

{ "ok": true, "project": { "project_id": "pid_123", "name": "Mon projet", "created_at": "..." } }
```
GET /api/v1/projects → Liste tous les projets

GET /api/v1/projects/{project_id} → Détails d’un projet

DELETE /api/v1/projects/{project_id} → Sauvegarde JSON + suppression

👛 Wallets d’un projet
POST /api/v1/projects/{project_id}/wallets → Crée N wallets
Body :

```json

{ "n": 3, "with_balance": true, "cluster": "devnet" }
```
Réponse :

```json

{ "ok": true, "wallets": [ { "name": "Wallet 1", "address": "...", "balance_sol": 0 } ] }
```
GET /api/v1/projects/{project_id}/wallets?with_balance=true&cluster=devnet → Liste tous les wallets d’un projet

🔍 Wallet isolé
GET /api/v1/wallets/{address}?cluster=devnet → Infos détaillées

GET /api/v1/wallets/{address}/balance?cluster=devnet → Solde en temps réel

🎁 Airdrop (devnet)
POST /api/v1/airdrop
Body :

```json

{ "address": "<pubkey>", "sol": 0.2, "cluster": "devnet" }
```
Réponse :

```json

{ "ok": true, "confirmation": "balance_delta", "balance_after": 1.2 }
```
💸 Transfert SOL
POST /api/v1/transfer/sol
Body :

```json

{
  "sender_private_key": "<clé privée base58>",
  "recipient_pubkey_b58": "<pubkey>",
  "amount_sol": 0.001,
  "cluster": "devnet"
}
```
Réponse :

```json

{ "ok": true, "tx_signature": "5ABc...xyz" }
```
🌀 Mix & Consolidation
POST /api/v1/wallets/mix
Redistribue du SOL.
Body :
```json

{ "wallet_ids": ["W1","W2","W3"], "strategy": "random" }
```
POST /api/v1/wallets/consolidate/{target_wallet_id}
Consolide vers un wallet cible.

🐳 Docker — Tutoriel complet
🔨 Build
```bash

docker build -t solana-wallet-api:v3.5 .
```
▶️ Run (mode devnet)
```bash

docker run -d \
  -e CLUSTER=devnet \
  -e API_KEY_DEVNET=dev-secret \
  -e DATA_DIR=/data \
  -p 8000:8000 \
  -v $PWD/data:/data \
  solana-wallet-api:v3.5
```
✅ Vérifier
```bash

curl http://localhost:8000/health
```
🧪 Exemples d’utilisation
Créer un projet
```bash

curl -s -X POST "http://localhost:8000/api/v1/projects" \
  -H "Authorization: Bearer dev-secret" \
  -H "Content-Type: application/json" \
  -d '{"name":"projet-X"}'
```
Générer 3 wallets
```bash

curl -s -X POST "http://localhost:8000/api/v1/projects/pid_123/wallets" \
  -H "Authorization: Bearer dev-secret" \
  -H "Content-Type: application/json" \
  -d '{"n":3,"with_balance":true,"cluster":"devnet"}'
```
Lister les wallets
```bash

curl -s "http://localhost:8000/api/v1/projects/pid_123/wallets?with_balance=true&cluster=devnet" \
  -H "Authorization: Bearer dev-secret"
```
🛠 Roadmap (prochaines évolutions)
🪙 Support complet des SPL Tokens (create/mint/transfer).

✏️ Renommage & suppression de wallets.

📊 Monitoring & observabilité (Prometheus, Grafana).

🔔 Webhooks / Callbacks pour confirmations TX.

🤖 Intégration Telegram (commandes temps réel).

⚙️ CI/CD GitHub Actions + tests auto.

📄 Licence
🄯 DProtDB — Tous droits réservés Solana.



---
**MX Tout droit réservé
---
