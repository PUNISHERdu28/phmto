# -*- coding: utf-8 -*-
"""
Client CLI Synthwave — PHEMTO_cliv2
-----------------------------------
Objectifs :
- Interface stable (un seul redraw par cycle), rapide (Session HTTP + timeouts), lisible (Rich).
- Respect strict du README + Swagger fournis pour les endpoints effectifs.
- UX fidèlement inspirée de la maquette PPTX :
  - Bannière PHEMTO + sous-titre "⚡ PHEMTO_cliv2 ⚡"
  - Panel "Projet sélectionné" qui CONTIENT le tableau des wallets
  - Sélecteur de cluster par projet (devnet/testnet/mainnet)
  - Sélecteur de wallet pour : Détails / Airdrop / Suppression / Transfert SOL
  - Menu "Édition du token" (stockage local tant qu'aucun endpoint n'est prévu côté API)

Prérequis :
    pip install rich requests

Variables d'environnement utiles :
    API_URL (ex: http://localhost:8000)
    API_KEY, API_KEY_DEVNET, API_KEY_TESTNET, API_KEY_MAINNET
    CLUSTER (devnet|testnet|mainnet)  -> défaut : devnet
"""

import os
import sys
import json
import platform
import requests
import getpass
from typing import Dict, Any, List, Optional, Tuple

from rich.console import Console, Group
from rich.table import Table
from rich.prompt import Prompt, IntPrompt
from rich.panel import Panel
from rich import box
from rich.text import Text

# ===============================
#  Console et configuration
# ===============================
console = Console()

API_URL = os.getenv("API_URL", "http://localhost:8000").rstrip("/")
DEFAULT_CLUSTER = os.getenv("CLUSTER", "devnet").strip().lower()
if DEFAULT_CLUSTER not in {"devnet", "testnet", "mainnet", "mainnet-beta"}:
    DEFAULT_CLUSTER = "devnet"

# Dossier local pour la config "Token" (pas d'endpoint API pour l'instant)
TOKENS_DIR = os.path.join(os.path.expanduser("~"), ".phmto_tokens")
os.makedirs(TOKENS_DIR, exist_ok=True)

# Session HTTP (réutilisation des connexions, + rapide et + stable)
HTTP = requests.Session()
HTTP_TIMEOUT = (5, 30)  # (connect, read) en secondes


# ===============================
#  Utilitaires d'interface
# ===============================
def clear_screen() -> None:
    """Nettoie l'écran du terminal sans clignoter outre mesure."""
    cmd = "cls" if platform.system().lower().startswith("win") else "clear"
    os.system(cmd)

def show_banner() -> None:
    """Bannière PHEMTO + sous-titre synthwave."""
    title = r"""
██████╗ ██╗  ██╗███████╗███╗   ███╗████████╗ ██████╗ ████████╗ ██████╗ 
██╔══██╗██║  ██║██╔════╝████╗ ████║╚══██╔══╝██╔═══██╗╚══██╔══╝██╔═══██╗
██████╔╝███████║█████╗  ██╔████╔██║   ██║   ██║   ██║   ██║   ██║   ██║
██╔═══╝ ██╔══██║██╔══╝  ██║╚██╔╝██║   ██║   ██║   ██║   ██║   ██║   ██║
██║     ██║  ██║███████╗██║ ╚═╝ ██║   ██║   ╚██████╔╝   ██║   ╚██████╔╝
╚═╝     ╚═╝  ╚═╝╚══════╝╚═╝     ╚═╝   ╚═╝    ╚═════╝    ╚═╝    ╚═════╝ 
""".rstrip("\n")
    subtitle = Text("⚡  PHEMTO_cliv2  ⚡", style="bold magenta")
    console.print(Panel(title, border_style="cyan", box=box.DOUBLE_EDGE))
    console.print(Panel(subtitle, border_style="magenta", box=box.ROUNDED))

def header_health(health: Optional[Dict[str, Any]]) -> Panel:
    """Construit un petit panneau d'état API (sans reprints intempestifs)."""
    if not health:
        return Panel("API non joignable", border_style="red", box=box.ROUNDED)
    txt = Text()
    txt.append("OK ", style="bold green")
    txt.append("• cluster=", style="dim"); txt.append(str(health.get("cluster") or DEFAULT_CLUSTER), style="bold cyan")
    txt.append("  • default_rpc=", style="dim"); txt.append(str(health.get("default_rpc") or "n/a"), style="bold magenta")
    return Panel(txt, border_style="magenta", box=box.ROUNDED)


# ===============================
#  Auth / Headers
# ===============================
def resolve_api_key(cluster: str) -> Optional[str]:
    """Résout la clé API en fonction du cluster (ou API_KEY générique)."""
    c = (cluster or DEFAULT_CLUSTER).lower()
    if c == "devnet":
        return os.getenv("API_KEY_DEVNET") or os.getenv("API_KEY")
    if c == "testnet":
        return os.getenv("API_KEY_TESTNET") or os.getenv("API_KEY")
    if c in {"mainnet", "mainnet-beta"}:
        return os.getenv("API_KEY_MAINNET") or os.getenv("API_KEY")
    return os.getenv("API_KEY")

def make_headers(cluster: str) -> Dict[str, str]:
    """Construit les en-têtes (Authorization + JSON)."""
    headers = {"Content-Type": "application/json"}
    api_key = resolve_api_key(cluster)
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


# ===============================
#  Appels API — helpers
# ===============================
def safe_json(resp: requests.Response) -> Any:
    """Parse JSON sinon renvoie texte (pour erreurs lisibles)."""
    try:
        return resp.json()
    except Exception:
        return resp.text

def api_get(path: str, cluster: str, params: Optional[Dict[str, Any]] = None) -> requests.Response:
    url = f"{API_URL}/{path.lstrip('/')}"
    return HTTP.get(url, headers=make_headers(cluster), params=params or {}, timeout=HTTP_TIMEOUT)

def api_post(path: str, cluster: str, body: Dict[str, Any]) -> requests.Response:
    url = f"{API_URL}/{path.lstrip('/')}"
    return HTTP.post(url, headers=make_headers(cluster), json=body, timeout=HTTP_TIMEOUT)

def api_delete(path: str, cluster: str) -> requests.Response:
    url = f"{API_URL}/{path.lstrip('/')}"
    return HTTP.delete(url, headers=make_headers(cluster), timeout=HTTP_TIMEOUT)


# ===============================
#  Fonctions API
# ===============================
def api_health() -> Optional[Dict[str, Any]]:
    try:
        r = HTTP.get(f"{API_URL}/health", timeout=HTTP_TIMEOUT)
        if r.status_code == 200:
            return r.json()
    except Exception:
        return None
    return None

def list_projects() -> List[Dict[str, Any]]:
    r = api_get("/api/v1/projects", DEFAULT_CLUSTER)
    if r.status_code == 200:
        return r.json().get("projects", [])
    _show_api_error(r, title="Impossible de lister les projets")
    return []

def create_project() -> None:
    name = Prompt.ask("[cyan]Nom du nouveau projet[/cyan]").strip()
    if not name:
        console.print("[yellow]Nom vide — création annulée.[/yellow]")
        return
    r = api_post("/api/v1/projects", DEFAULT_CLUSTER, {"name": name})
    data = safe_json(r)
    if r.status_code in (200, 201):
        console.print(Panel(f"Projet [bold cyan]{name}[/bold cyan] créé.", title="Succès",
                            border_style="green", box=box.ROUNDED))
    else:
        _show_api_error(r, data=data, title="Erreur création projet")

def fetch_project_wallets(project_id: str, cluster: str) -> List[Dict[str, Any]]:
    params = {"with_balance": "true", "cluster": cluster}
    r = api_get(f"/api/v1/projects/{project_id}/wallets", cluster, params=params)
    data = safe_json(r)
    if r.status_code != 200:
        _show_api_error(r, data=data, title="Impossible de lister les wallets")
        return []
    return (data or {}).get("wallets", [])

def wallet_details(address: str, cluster: str) -> Optional[Dict[str, Any]]:
    r = api_get(f"/api/v1/wallets/{address}", cluster, params={"cluster": cluster})
    data = safe_json(r)
    if r.status_code != 200:
        _show_api_error(r, data=data, title="Erreur fetch wallet")
        return None
    return data

def generate_wallets(project_id: str, cluster: str) -> None:
    n = IntPrompt.ask("[cyan]Combien de wallets créer ?[/cyan]", default=1)
    body = {"n": n, "with_balance": True, "cluster": cluster}
    r = api_post(f"/api/v1/projects/{project_id}/wallets", cluster, body)
    data = safe_json(r)
    if r.status_code in (200, 201):
        created = (data or {}).get("created", n)
        addrs = (data or {}).get("wallets", [])
        msg = Text()
        msg.append(f"{created} wallet(s) créé(s)\n", style="bold green")
        if addrs:
            msg.append("Adresses :\n", style="bold cyan")
            for a in addrs:
                msg.append(f" • {a}\n", style="magenta")
        console.print(Panel(msg, title="Succès", border_style="green", box=box.ROUNDED))
    else:
        _show_api_error(r, data=data, title="Erreur création wallets")

def airdrop_on_wallet(address: str, cluster: str) -> None:
    if cluster != "devnet":
        console.print(Panel("Airdrop uniquement sur [bold]devnet[/bold].",
                            border_style="yellow", box=box.ROUNDED))
        return
    try:
        sol = float(Prompt.ask("[cyan]Montant SOL à airdrop[/cyan]", default="0.2"))
    except Exception:
        console.print("[yellow]Montant invalide — annulé.[/yellow]")
        return
    body = {
        "address": address,
        "sol": sol,
        "cluster": "devnet",
        "confirm_seconds": 60,
        "confirm_interval": 1,
        "retries": 3,
        "backoff_seconds": 1.5
    }
    r = api_post("/api/v1/airdrop", "devnet", body)
    data = safe_json(r)
    if r.status_code in (200, 201, 202):
        console.print(Panel(json.dumps(data, indent=2, ensure_ascii=False),
                            title="Airdrop", border_style="cyan", box=box.ROUNDED))
    else:
        _show_api_error(r, data=data, title="Erreur airdrop")

def delete_wallet(project_id: str, address: str, cluster: str) -> None:
    r = api_delete(f"/api/v1/projects/{project_id}/wallets/{address}", cluster)
    data = safe_json(r)
    if r.status_code in (200, 204):
        console.print(Panel(f"Wallet {address} supprimé.", title="Succès",
                            border_style="green", box=box.ROUNDED))
    else:
        _show_api_error(r, data=data, title="Erreur suppression wallet")
def transfer_sol_from_sender(project_id: str, sender_wallet: Dict[str, Any], cluster: str = DEFAULT_CLUSTER) -> None:
    """
    Envoi de SOL avec sélection du wallet EXPÉDITEUR (demande de la clé privée),
    puis SAISIE MANUELLE de la clé publique du DESTINATAIRE.

    Étapes :
      1) Affiche le wallet expéditeur sélectionné (lecture depuis sender_wallet)
      2) Demande la pubkey du destinataire (saisie manuelle)
      3) Demande le montant en SOL
      4) Demande la clé privée expéditeur (saisie masquée — sécurité)
      5) Confirmation et appel POST /api/v1/transfer/sol

    Paramètres :
      - project_id : pour afficher un contexte si besoin (pas nécessaire côté API)
      - sender_wallet : dict du wallet expéditeur (doit contenir au moins "address")
      - cluster : cluster actuel (devnet/testnet/mainnet)
    """
    # 1) Contexte — affichage de l'expéditeur pour éviter toute erreur de sélection
    sender_addr = sender_wallet.get("address", "")
    sender_name = sender_wallet.get("name", "Wallet")
    if not sender_addr:
        console.print(Panel("Adresse expéditeur introuvable.", border_style="red", box=box.ROUNDED))
        return

    # 2) Saisie de la pubkey destinataire — on force une saisie non vide
    recipient_pubkey = Prompt.ask(
        f"[cyan]Clé publique (pubkey) du destinataire[/cyan]\n[dim](expéditeur : {sender_name} — {sender_addr})[/dim]"
    ).strip()
    if not recipient_pubkey:
        console.print("[yellow]Adresse destinataire vide — envoi annulé.[/yellow]")
        return

    # 3) Montant
    try:
        amount = float(Prompt.ask("[cyan]Montant à envoyer (SOL)[/cyan]", default="0.001"))
        if amount <= 0:
            raise ValueError("Montant non positif")
    except Exception:
        console.print("[yellow]Montant invalide — envoi annulé.[/yellow]")
        return

    # 4) Clé privée expéditeur — saisie masquée (ne s'affiche pas à l'écran)
    console.print(Panel(
        "Saisissez la [bold]clé privée expéditeur (base58)[/bold]. Elle ne sera pas affichée.",
        border_style="magenta", box=box.ROUNDED
    ))
    import getpass  # local import pour souligner l'usage ponctuel
    sender_priv = getpass.getpass("Clé privée expéditeur : ").strip()
    if not sender_priv:
        console.print("[yellow]Clé privée vide — envoi annulé.[/yellow]")
        return

    # 5) Récapitulatif + confirmation
    recap = (
        f"[cyan]Récapitulatif :[/cyan]\n"
        f" • Cluster       : [bold]{cluster}[/bold]\n"
        f" • Expéditeur    : [magenta]{sender_addr}[/magenta]\n"
        f" • Destinataire  : [magenta]{recipient_pubkey}[/magenta]\n"
        f" • Montant       : [green]{amount} SOL[/green]\n"
    )
    console.print(Panel(recap, title="Confirmer l'envoi ?", border_style="cyan", box=box.ROUNDED))
    confirm = Prompt.ask("[cyan]Confirmer ?[/cyan] (o/n)", choices=["o", "n"], default="o")
    if confirm != "o":
        console.print("[yellow]Envoi annulé par l'utilisateur.[/yellow]")
        return

    # 6) Appel API — conforme à /api/v1/transfer/sol (Swagger)
    payload = {
        "sender_private_key": sender_priv,            # clé privée base58
        "recipient_pubkey_b58": recipient_pubkey,     # pubkey destinataire
        "amount_sol": amount,                         # float SOL
        "cluster": cluster                            # devnet/testnet/mainnet
    }
    resp = api_post("/api/v1/transfer/sol", cluster, payload)
    data = safe_json(resp)

    # 7) Affichage du résultat
    if resp.status_code in (200, 201, 202):
        console.print(Panel(json.dumps(data, indent=2, ensure_ascii=False),
                            title="Transfert SOL — Réponse API", border_style="green", box=box.ROUNDED))
    else:
        _show_api_error(resp, data=data, title="Erreur lors de l'envoi de SOL")

def transfer_sol(cluster: str, recipient_pubkey: str) -> None:
    console.print(Panel("La clé privée expéditeur n'est pas affichée (saisie masquée).",
                        border_style="magenta", box=box.ROUNDED))
    sender_priv = getpass.getpass("Clé privée expéditeur (base58) : ").strip()
    if not sender_priv:
        console.print("[yellow]Clé privée vide — annulé.[/yellow]")
        return
    try:
        amount = float(Prompt.ask("[cyan]Montant à envoyer (SOL)[/cyan]", default="0.001"))
    except Exception:
        console.print("[yellow]Montant invalide — annulé.[/yellow]")
        return

    confirm = Prompt.ask(
        f"[cyan]Confirmer l'envoi de {amount} SOL à[/cyan] [magenta]{recipient_pubkey}[/magenta] ? (o/n)",
        choices=["o", "n"], default="o"
    )
    if confirm != "o":
        console.print("[yellow]Envoi annulé par l'utilisateur.[/yellow]")
        return

    body = {
        "sender_private_key": sender_priv,
        "recipient_pubkey_b58": recipient_pubkey,
        "amount_sol": amount,
        "cluster": cluster
    }
    r = api_post("/api/v1/transfer/sol", cluster, body)
    data = safe_json(r)
    if r.status_code in (200, 201, 202):
        console.print(Panel(json.dumps(data, indent=2, ensure_ascii=False),
                            title="Transfert SOL — Réponse", border_style="green", box=box.ROUNDED))
    else:
        _show_api_error(r, data=data, title="Erreur transfert SOL")


# ===============================
#  Mise en forme (tables/panels)
# ===============================
def build_wallets_table(wallets: List[Dict[str, Any]], cluster: str) -> Table:
    """Construit le tableau Rich des wallets (stable, sans overflow violent)."""
    t = Table(title=f"Wallets ({len(wallets)}) — cluster={cluster}",
              style="bold magenta", border_style="cyan", box=box.SQUARE)
    t.add_column("#", justify="right", style="bold cyan", no_wrap=True)
    t.add_column("Nom", style="cyan", no_wrap=True)
    t.add_column("Adresse (pubkey)", style="magenta")
    t.add_column("Solde (SOL)", justify="right", style="green", no_wrap=True)
    for i, w in enumerate(wallets, 1):
        t.add_row(
            str(i),
            w.get("name", f"Wallet {i}"),
            w.get("address", "n/a"),
            str(w.get("balance_sol", "n/a")),
        )
    return t

def render_project_panel(project: Dict[str, Any], cluster: str, wallets: List[Dict[str, Any]]) -> Panel:
    """Panel 'Projet sélectionné' qui CONTIENT le tableau (ou un message s'il n'y a pas de wallets)."""
    inner = build_wallets_table(wallets, cluster) if wallets else Panel(
        "Aucun wallet trouvé pour ce projet.", border_style="yellow", box=box.ROUNDED
    )
    title = f"Projet sélectionné : {project.get('name','N/A')}  ({project.get('project_id','N/A')})"
    return Panel(inner, title=title, border_style="cyan", box=box.HEAVY)


# ===============================
#  Sélecteurs (projets / wallets / cluster)
# ===============================
def select_project() -> Optional[Dict[str, Any]]:
    """Liste les projets et demande un index, retourne le projet choisi."""
    projs = list_projects()
    if not projs:
        console.print(Panel("Aucun projet. Crée-en un d'abord.", border_style="yellow", box=box.ROUNDED))
        return None
    t = Table(title=f"Projets ({len(projs)})", style="bold magenta", border_style="cyan", box=box.HEAVY_EDGE)
    t.add_column("#", justify="right", style="bold cyan", no_wrap=True)
    t.add_column("Nom", style="cyan", no_wrap=True)
    t.add_column("Project ID", style="magenta")
    for i, p in enumerate(projs, 1):
        t.add_row(str(i), p.get("name", "N/A"), p.get("project_id", "N/A"))
    console.print(t)
    idx = IntPrompt.ask("[cyan]Numéro du projet[/cyan]", default=1)
    if 1 <= idx <= len(projs):
        return projs[idx - 1]
    console.print("[red]Index invalide[/red]")
    return None

def select_wallet(wallets: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Affiche le tableau et demande l'index du wallet à utiliser."""
    if not wallets:
        console.print(Panel("Aucun wallet.", border_style="yellow", box=box.ROUNDED))
        return None
    console.print(build_wallets_table(wallets, "?"))  # cluster dans le titre → non pertinent ici
    idx = IntPrompt.ask("[cyan]Numéro du wallet[/cyan]", default=1)
    if 1 <= idx <= len(wallets):
        return wallets[idx - 1]
    console.print("[red]Index invalide[/red]")
    return None

def select_cluster(current: str) -> str:
    """Sélecteur de cluster stable."""
    mapping = {"1": "devnet", "2": "testnet", "3": "mainnet"}
    console.print(Panel(
        "Sélection du cluster :\n"
        "[1] devnet\n[2] testnet\n[3] mainnet",
        border_style="cyan", box=box.ROUNDED, title=f"Cluster actuel: {current}"
    ))
    choice = Prompt.ask("[cyan]Choix[/cyan]", choices=["1", "2", "3"], default="1")
    return mapping[choice]


# ===============================
#  Token — stockage local
# ===============================
def token_cfg_path(project_id: str) -> str:
    return os.path.join(TOKENS_DIR, f"{project_id}.json")

def load_token_cfg(project_id: str) -> Dict[str, Any]:
    """Charge la config token locale du projet (si existante)."""
    path = token_cfg_path(project_id)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_token_cfg(project_id: str, cfg: Dict[str, Any]) -> None:
    """Sauvegarde la config token locale du projet."""
    path = token_cfg_path(project_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

def token_editor_menu(project: Dict[str, Any]) -> None:
    """
    Menu d'édition de token (local, inspiré PPTX).
    Champs : name, symbol, contract_address, creator_wallet, image_url, description, supply, links{tiktok,twitter,website}
    """
    pid = project.get("project_id", "unknown")
    cfg = load_token_cfg(pid)

    while True:
        clear_screen()
        show_banner()
        console.print(Panel(f"Édition du token — projet {project.get('name')} ({pid})",
                            border_style="magenta", box=box.ROUNDED))

        # Affichage résumé du token
        summary = Table(title="Token (local)", border_style="cyan", style="bold magenta", box=box.SQUARE)
        summary.add_column("Champ", style="cyan"); summary.add_column("Valeur", style="white")
        summary.add_row("Nom", str(cfg.get("name", "")))
        summary.add_row("Symbole", str(cfg.get("symbol", "")))
        summary.add_row("Contrat (CA)", str(cfg.get("contract_address", "")))
        summary.add_row("Wallet créateur", str(cfg.get("creator_wallet", "")))
        summary.add_row("Image URL", str(cfg.get("image_url", "")))
        summary.add_row("Description", str(cfg.get("description", "")))
        summary.add_row("Supply", str(cfg.get("supply", "")))
        links = cfg.get("links", {}) or {}
        summary.add_row("TikTok", str(links.get("tiktok", "")))
        summary.add_row("Twitter", str(links.get("twitter", "")))
        summary.add_row("Website", str(links.get("website", "")))
        console.print(summary)

        console.print("\n[1] Modifier Nom")
        console.print("[2] Modifier Symbole")
        console.print("[3] Modifier Contrat (CA)")
        console.print("[4] Modifier Wallet créateur")
        console.print("[5] Modifier Image URL")
        console.print("[6] Modifier Description")
        console.print("[7] Modifier Supply")
        console.print("[8] Modifier Liens (TikTok/Twitter/Website)")
        console.print("[9] Enregistrer et revenir")
        console.print("[0] Annuler (sans enregistrer)")

        ch = Prompt.ask("[cyan]Choix[/cyan]", choices=[str(i) for i in range(0, 10)], default="9")
        if ch == "1":
            cfg["name"] = Prompt.ask("Nom", default=str(cfg.get("name", "")))
        elif ch == "2":
            cfg["symbol"] = Prompt.ask("Symbole", default=str(cfg.get("symbol", "")))
        elif ch == "3":
            cfg["contract_address"] = Prompt.ask("Contrat (CA)", default=str(cfg.get("contract_address", "")))
        elif ch == "4":
            cfg["creator_wallet"] = Prompt.ask("Wallet créateur", default=str(cfg.get("creator_wallet", "")))
        elif ch == "5":
            cfg["image_url"] = Prompt.ask("Image URL", default=str(cfg.get("image_url", "")))
        elif ch == "6":
            cfg["description"] = Prompt.ask("Description", default=str(cfg.get("description", "")))
        elif ch == "7":
            cfg["supply"] = Prompt.ask("Supply", default=str(cfg.get("supply", "")))
        elif ch == "8":
            links = cfg.get("links", {}) or {}
            links["tiktok"] = Prompt.ask("Lien TikTok", default=str(links.get("tiktok", "")))
            links["twitter"] = Prompt.ask("Lien Twitter", default=str(links.get("twitter", "")))
            links["website"] = Prompt.ask("Lien Website", default=str(links.get("website", "")))
            cfg["links"] = links
        elif ch == "9":
            save_token_cfg(pid, cfg)
            console.print(Panel("Token enregistré localement.", border_style="green", box=box.ROUNDED))
            Prompt.ask("[dim]Entrée pour revenir[/dim]")
            return
        elif ch == "0":
            return


# ===============================
#  Menus (stables)
# ===============================
def project_menu(project: Dict[str, Any]) -> None:
    """
    MENU PROJET — affichage stable :
    - En haut : bannière + état API
    - Panel "Projet sélectionné" qui CONTIENT la table des wallets
    - Menu fixe en bas
    - Sélecteur de CLUSTER (devnet/testnet/mainnet), persistant pour ce menu
    """
    # Cluster courant du "contexte projet"
    current_cluster = DEFAULT_CLUSTER

    while True:
        # --- 1) FETCH minimal —
        health = api_health()                      # ~1 requête / cycle
        wallets = fetch_project_wallets(project["project_id"], current_cluster)  # ~1 requête / cycle

        # --- 2) RENDER (1 seul redraw par cycle) —
        clear_screen()
        show_banner()
        main_layout = Group(
            header_health(health),
            render_project_panel(project, current_cluster, wallets),
            Panel(
                Text(
                    "[1] Changer de cluster   "
                    "[2] Générer wallets   "
                    "[3] Airdrop (devnet)   "
                    "[4] Supprimer wallet   "
                    "[5] Détails wallet   "
                    "[6] Envoyer SOL   "
                    "[7] Édition du token   "
                    "[0] Retour",
                    style="bold cyan"
                ),
                title="Menu Projet", border_style="cyan", box=box.ROUNDED
            )
        )
        console.print(main_layout)

        # --- 3) INPUT — choix utilisateur
        choice = Prompt.ask("[cyan]Choix[/cyan]", choices=[str(i) for i in range(0, 8)], default="0")

        # --- 4) ACTIONS — chacune limitera les reprints (on relance juste un cycle)
        if choice == "1":
            current_cluster = select_cluster(current_cluster)
        elif choice == "2":
            generate_wallets(project["project_id"], current_cluster)
            Prompt.ask("[dim]Entrée pour continuer[/dim]")
        elif choice == "3":
            # Sélecteur de wallet
            if not wallets:
                console.print(Panel("Aucun wallet.", border_style="yellow", box=box.ROUNDED))
                Prompt.ask("[dim]Entrée[/dim]"); continue
            w = select_wallet(wallets)
            if w:
                airdrop_on_wallet(w.get("address",""), current_cluster)
                Prompt.ask("[dim]Entrée pour continuer[/dim]")
        elif choice == "4":
            if not wallets:
                console.print(Panel("Aucun wallet.", border_style="yellow", box=box.ROUNDED))
                Prompt.ask("[dim]Entrée[/dim]"); continue
            w = select_wallet(wallets)
            if w:
                delete_wallet(project["project_id"], w.get("address",""), current_cluster)
                Prompt.ask("[dim]Entrée pour continuer[/dim]")
        elif choice == "5":
            if not wallets:
                console.print(Panel("Aucun wallet.", border_style="yellow", box=box.ROUNDED))
                Prompt.ask("[dim]Entrée[/dim]"); continue
            w = select_wallet(wallets)
            if w:
                data = wallet_details(w.get("address",""), current_cluster)
                if data:
                    # Détails formatés (selon PPTX)
                    name = data.get("name", w.get("name"))
                    addr = data.get("address", w.get("address"))
                    bal  = data.get("balance_sol", w.get("balance_sol"))
                    parent = data.get("project", {}) or {}
                    pid = parent.get("project_id", project.get("project_id"))
                    # Privkey indisponible côté API → on affiche "secret_path" si un jour exposé, sinon "—"
                    privk = data.get("secret_path") or "—"
                    txt = Text()
                    txt.append("Nom        : ", style="bold cyan"); txt.append(f"{name}\n")
                    txt.append("ID (pid)   : ", style="bold cyan"); txt.append(f"{pid}\n")
                    txt.append("Pubkey     : ", style="bold cyan"); txt.append(f"{addr}\n", style="magenta")
                    txt.append("Privkey    : ", style="bold cyan"); txt.append(f"{privk}\n", style="white")
                    txt.append("Solde (SOL): ", style="bold cyan"); txt.append(f"{bal}\n", style="green")
                    console.print(Panel(txt, title="Détail Wallet", border_style="cyan", box=box.ROUNDED))
                Prompt.ask("[dim]Entrée pour continuer[/dim]")
        elif choice == "6":
            # On sélectionne d'abord le WALLET EXPÉDITEUR dans le projet
            if not wallets:
                console.print(Panel("Aucun wallet.", border_style="yellow", box=box.ROUNDED))
                Prompt.ask("[dim]Entrée[/dim]")
            else:
                sender = select_wallet(wallets)  # réutilise le sélecteur existant (par index)
                if sender:
                    transfer_sol_from_sender(project["project_id"], sender, current_cluster)
                    Prompt.ask("[dim]Entrée pour continuer[/dim]")

        elif choice == "7":
            token_editor_menu(project)
        elif choice == "0":
            break

def main_menu() -> None:
    """MENU PRINCIPAL — stable & simple."""
    while True:
        clear_screen()
        show_banner()
        console.print(Panel(
            "[1] Lister projets\n"
            "[2] Créer projet\n"
            "[3] Sélectionner projet\n"
            "[0] Quitter",
            title="Menu Principal", border_style="cyan", box=box.ROUNDED
        ))
        choice = Prompt.ask("[cyan]Choix[/cyan]", choices=["0","1","2","3"], default="3")
        if choice == "1":
            projs = list_projects()
            if not projs:
                console.print(Panel("Aucun projet.", border_style="yellow", box=box.ROUNDED))
            else:
                t = Table(title=f"Projets ({len(projs)})", style="bold magenta", border_style="cyan", box=box.HEAVY_EDGE)
                t.add_column("#", justify="right", style="bold cyan", no_wrap=True)
                t.add_column("Nom", style="cyan", no_wrap=True)
                t.add_column("Project ID", style="magenta")
                for i, p in enumerate(projs, 1):
                    t.add_row(str(i), p.get("name", "N/A"), p.get("project_id", "N/A"))
                console.print(t)
            Prompt.ask("[dim]Entrée pour continuer[/dim]")
        elif choice == "2":
            create_project()
            Prompt.ask("[dim]Entrée pour continuer[/dim]")
        elif choice == "3":
            proj = select_project()
            if proj:
                project_menu(proj)
        elif choice == "0":
            console.print("[magenta]À bientôt ![/magenta]")
            sys.exit(0)


# ===============================
#  Erreurs API
# ===============================
def _show_api_error(resp: requests.Response, data: Any = None, title: str = "Erreur API") -> None:
    payload = data if data is not None else safe_json(resp)
    body = payload if isinstance(payload, str) else json.dumps(payload, indent=2, ensure_ascii=False)
    console.print(Panel(f"[bold red]HTTP {resp.status_code}[/bold red]\n{body}",
                        title=title, border_style="red", box=box.ROUNDED))


# ===============================
#  Entrée
# ===============================
if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        console.print("\n[magenta]Interruption utilisateur — au revoir ![/magenta]")
