#!/usr/bin/env python3
"""
🧪 SUITE DE TESTS COMPLÈTE - RUG API v3.6
Teste TOUS les endpoints pour garantir un fonctionnement parfait.
"""

import requests
import json
import time
from typing import Dict, List, Any

# Configuration de base
BASE_URL = "http://localhost:8000"
HEADERS = {"Content-Type": "application/json"}

class EndpointTester:
    def __init__(self):
        self.results: List[Dict[str, Any]] = []
        self.project_id = None
        self.wallet_address = None
        
    def log_result(self, endpoint: str, method: str, status_code: int, success: bool, details: str = ""):
        """Enregistre le résultat d'un test."""
        result = {
            "endpoint": endpoint,
            "method": method,
            "status_code": status_code,
            "success": success,
            "details": details,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        self.results.append(result)
        status_icon = "✅" if success else "❌"
        print(f"{status_icon} {method} {endpoint} -> {status_code} | {details}")
        
    def test_health(self):
        """Test endpoint /health"""
        try:
            response = requests.get(f"{BASE_URL}/health")
            success = response.status_code == 200
            details = "Health check working" if success else f"Unexpected status: {response.status_code}"
            self.log_result("/health", "GET", response.status_code, success, details)
            if success:
                data = response.json()
                print(f"  📊 Service: {data.get('service')}, Cluster: {data.get('cluster')}")
        except Exception as e:
            self.log_result("/health", "GET", 0, False, f"Exception: {str(e)}")
            
    def test_projects_basic(self):
        """Test endpoints de base des projets."""
        # 1. Créer un projet
        try:
            payload = {"name": "Test Project API"}
            response = requests.post(f"{BASE_URL}/api/v1/projects", 
                                   json=payload, headers=HEADERS)
            success = response.status_code == 201
            if success:
                data = response.json()
                self.project_id = data.get("project", {}).get("project_id")
                details = f"Project created: {self.project_id}"
            else:
                details = f"Create failed: {response.text}"
            self.log_result("/api/v1/projects", "POST", response.status_code, success, details)
        except Exception as e:
            self.log_result("/api/v1/projects", "POST", 0, False, f"Exception: {str(e)}")
            
        # 2. Lister les projets
        try:
            response = requests.get(f"{BASE_URL}/api/v1/projects")
            success = response.status_code == 200
            if success:
                data = response.json()
                projects_count = len(data.get("projects", []))
                details = f"Listed {projects_count} projects"
            else:
                details = f"List failed: {response.text}"
            self.log_result("/api/v1/projects", "GET", response.status_code, success, details)
        except Exception as e:
            self.log_result("/api/v1/projects", "GET", 0, False, f"Exception: {str(e)}")
            
        # 3. Détails d'un projet (si créé)
        if self.project_id:
            try:
                response = requests.get(f"{BASE_URL}/api/v1/projects/{self.project_id}")
                success = response.status_code == 200
                details = "Project details retrieved" if success else f"Details failed: {response.text}"
                self.log_result(f"/api/v1/projects/{self.project_id}", "GET", response.status_code, success, details)
            except Exception as e:
                self.log_result(f"/api/v1/projects/{self.project_id}", "GET", 0, False, f"Exception: {str(e)}")
    
    def test_wallets_basic(self):
        """Test endpoints de base des wallets."""
        if not self.project_id:
            print("❌ Skipping wallet tests - no project_id available")
            return
            
        # 1. Créer des wallets
        try:
            payload = {"count": 2}
            response = requests.post(f"{BASE_URL}/api/v1/projects/{self.project_id}/wallets",
                                   json=payload, headers=HEADERS)
            success = response.status_code == 201
            if success:
                data = response.json()
                wallets = data.get("wallets", [])
                if wallets:
                    self.wallet_address = wallets[0].get("address")
                details = f"Created {len(wallets)} wallets"
            else:
                details = f"Wallet creation failed: {response.text}"
            self.log_result(f"/api/v1/projects/{self.project_id}/wallets", "POST", response.status_code, success, details)
        except Exception as e:
            self.log_result(f"/api/v1/projects/{self.project_id}/wallets", "POST", 0, False, f"Exception: {str(e)}")
            
        # 2. Lister les wallets du projet
        try:
            response = requests.get(f"{BASE_URL}/api/v1/projects/{self.project_id}/wallets")
            success = response.status_code == 200
            if success:
                data = response.json()
                wallets_count = len(data.get("wallets", []))
                details = f"Listed {wallets_count} wallets"
            else:
                details = f"Wallet list failed: {response.text}"
            self.log_result(f"/api/v1/projects/{self.project_id}/wallets", "GET", response.status_code, success, details)
        except Exception as e:
            self.log_result(f"/api/v1/projects/{self.project_id}/wallets", "GET", 0, False, f"Exception: {str(e)}")
            
        # 3. Test endpoint export sécurisé
        if self.wallet_address:
            try:
                # Test sans confirmation (doit échouer)
                response = requests.get(f"{BASE_URL}/api/v1/projects/{self.project_id}/wallets/{self.wallet_address}/export")
                success = response.status_code == 400  # Doit échouer sans confirmation
                details = "Security check working (export blocked)" if success else "Security issue - export should be blocked"
                self.log_result(f"/api/v1/projects/{self.project_id}/wallets/{self.wallet_address}/export", "GET", response.status_code, success, details)
                
                # Test avec confirmation (doit marcher)
                response = requests.get(f"{BASE_URL}/api/v1/projects/{self.project_id}/wallets/{self.wallet_address}/export?confirm=true")
                success = response.status_code == 200
                details = "Export with confirmation working" if success else f"Export failed: {response.text}"
                self.log_result(f"/api/v1/projects/{self.project_id}/wallets/{self.wallet_address}/export?confirm=true", "GET", response.status_code, success, details)
            except Exception as e:
                self.log_result(f"/api/v1/projects/{self.project_id}/wallets/{self.wallet_address}/export", "GET", 0, False, f"Exception: {str(e)}")
    
    def test_transfers_basic(self):
        """Test endpoints de transferts."""
        # Test airdrop (devnet seulement)
        try:
            if self.wallet_address:
                payload = {"address": self.wallet_address, "amount": 0.1}
                response = requests.post(f"{BASE_URL}/api/v1/airdrop",
                                       json=payload, headers=HEADERS)
                success = response.status_code in [200, 201]
                details = "Airdrop successful" if success else f"Airdrop failed: {response.text}"
                self.log_result("/api/v1/airdrop", "POST", response.status_code, success, details)
            else:
                self.log_result("/api/v1/airdrop", "POST", 0, False, "No wallet address available")
        except Exception as e:
            self.log_result("/api/v1/airdrop", "POST", 0, False, f"Exception: {str(e)}")
    
    def test_tokens_basic(self):
        """Test endpoints de tokens."""
        if not self.project_id:
            print("❌ Skipping token tests - no project_id available")
            return
            
        # Test configuration de token
        try:
            payload = {
                "name": "Test Token",
                "symbol": "TEST",
                "description": "Token de test pour l'API",
                "decimals": 9,
                "initial_supply": 1000000
            }
            response = requests.patch(f"{BASE_URL}/api/v1/projects/{self.project_id}/token",
                                    json=payload, headers=HEADERS)
            success = response.status_code == 200
            details = "Token metadata updated" if success else f"Token update failed: {response.text}"
            self.log_result(f"/api/v1/projects/{self.project_id}/token", "PATCH", response.status_code, success, details)
        except Exception as e:
            self.log_result(f"/api/v1/projects/{self.project_id}/token", "PATCH", 0, False, f"Exception: {str(e)}")
            
    def test_stats_endpoint(self):
        """Test endpoint de statistiques."""
        if not self.project_id:
            print("❌ Skipping stats test - no project_id available")
            return
            
        try:
            response = requests.get(f"{BASE_URL}/api/v1/projects/{self.project_id}/stats")
            success = response.status_code == 200
            if success:
                data = response.json()
                wallets_count = data.get("project_info", {}).get("wallets_count", 0)
                details = f"Stats retrieved - {wallets_count} wallets"
            else:
                details = f"Stats failed: {response.text}"
            self.log_result(f"/api/v1/projects/{self.project_id}/stats", "GET", response.status_code, success, details)
        except Exception as e:
            self.log_result(f"/api/v1/projects/{self.project_id}/stats", "GET", 0, False, f"Exception: {str(e)}")
    
    def run_all_tests(self):
        """Lance tous les tests dans l'ordre logique."""
        print("🧪 DÉBUT DES TESTS COMPLETS - RUG API v3.6")
        print("=" * 60)
        
        # Tests de base
        self.test_health()
        print()
        
        # Tests projets
        print("📂 TESTS PROJECTS:")
        self.test_projects_basic()
        print()
        
        # Tests wallets
        print("🔐 TESTS WALLETS:")
        self.test_wallets_basic()
        print()
        
        # Tests transferts
        print("💸 TESTS TRANSFERS:")
        self.test_transfers_basic()
        print()
        
        # Tests tokens
        print("🪙 TESTS TOKENS:")
        self.test_tokens_basic()
        print()
        
        # Tests stats
        print("📊 TESTS STATS:")
        self.test_stats_endpoint()
        print()
        
        self.print_summary()
    
    def print_summary(self):
        """Affiche un résumé des tests."""
        print("=" * 60)
        print("📋 RÉSUMÉ DES TESTS")
        print("=" * 60)
        
        total_tests = len(self.results)
        successful_tests = len([r for r in self.results if r["success"]])
        failed_tests = total_tests - successful_tests
        
        print(f"📊 Total: {total_tests} tests")
        print(f"✅ Réussis: {successful_tests}")
        print(f"❌ Échoués: {failed_tests}")
        print(f"📈 Taux de succès: {(successful_tests/total_tests*100):.1f}%")
        
        if failed_tests > 0:
            print("\n❌ TESTS ÉCHOUÉS:")
            for result in self.results:
                if not result["success"]:
                    print(f"  • {result['method']} {result['endpoint']} - {result['details']}")
        
        # Sauvegarder les résultats
        with open("test_results.json", "w") as f:
            json.dump(self.results, f, indent=2)
        print(f"\n💾 Résultats sauvegardés dans test_results.json")

if __name__ == "__main__":
    print("🚀 Démarrage des tests endpoints...")
    print("⚠️  Assurez-vous que FEMTO est en cours d'exécution sur le port 8000")
    print()
    
    tester = EndpointTester()
    tester.run_all_tests()