#!/usr/bin/env python3
"""
🔬 TESTS AVANCÉS - Tous les endpoints avec configuration devnet
"""

import requests
import json
import time
import os

BASE_URL = "http://localhost:8000"
HEADERS = {"Content-Type": "application/json"}

class AdvancedTester:
    def __init__(self):
        self.results = []
        self.project_id = None
        self.wallet_addresses = []
        
    def log_test(self, name: str, success: bool, details: str = ""):
        """Log test result"""
        icon = "✅" if success else "❌"
        print(f"{icon} {name}: {details}")
        self.results.append({"test": name, "success": success, "details": details})
        
    def test_comprehensive_workflow(self):
        """Test workflow complet: Project -> Wallets -> Transfers -> Tokens"""
        print("🚀 TEST WORKFLOW COMPLET")
        print("=" * 50)
        
        # 1. Health check avec détails
        try:
            resp = requests.get(f"{BASE_URL}/health")
            if resp.status_code == 200:
                data = resp.json()
                cluster = data.get("cluster", "unknown")
                rpc = data.get("default_rpc", "unknown")
                self.log_test("Health Check", True, f"Cluster: {cluster}, RPC: {rpc}")
            else:
                self.log_test("Health Check", False, f"Status: {resp.status_code}")
        except Exception as e:
            self.log_test("Health Check", False, f"Error: {e}")
            
        # 2. Créer un projet avec détails
        try:
            payload = {"name": "Projet Test Avancé"}
            resp = requests.post(f"{BASE_URL}/api/v1/projects", json=payload, headers=HEADERS)
            if resp.status_code == 201:
                data = resp.json()
                self.project_id = data["project"]["project_id"]
                self.log_test("Create Project", True, f"ID: {self.project_id}")
            else:
                self.log_test("Create Project", False, f"Status: {resp.status_code}")
                return
        except Exception as e:
            self.log_test("Create Project", False, f"Error: {e}")
            return
            
        # 3. Créer plusieurs wallets
        try:
            payload = {"count": 3}
            resp = requests.post(f"{BASE_URL}/api/v1/projects/{self.project_id}/wallets", 
                               json=payload, headers=HEADERS)
            if resp.status_code == 201:
                data = resp.json()
                wallets = data.get("wallets", [])
                self.wallet_addresses = [w["address"] for w in wallets]
                self.log_test("Create Wallets", True, f"Created {len(wallets)} wallets")
            else:
                self.log_test("Create Wallets", False, f"Status: {resp.status_code}")
        except Exception as e:
            self.log_test("Create Wallets", False, f"Error: {e}")
            
        # 4. Test export sécurisé de chaque wallet
        for i, addr in enumerate(self.wallet_addresses):
            try:
                # Test sans confirmation
                resp = requests.get(f"{BASE_URL}/api/v1/projects/{self.project_id}/wallets/{addr}/export")
                blocked = resp.status_code == 400
                
                # Test avec confirmation
                resp = requests.get(f"{BASE_URL}/api/v1/projects/{self.project_id}/wallets/{addr}/export?confirm=true")
                exported = resp.status_code == 200
                
                if blocked and exported:
                    self.log_test(f"Wallet {i+1} Export Security", True, "Blocked without confirmation, works with confirmation")
                else:
                    self.log_test(f"Wallet {i+1} Export Security", False, f"Security issue: blocked={blocked}, exported={exported}")
            except Exception as e:
                self.log_test(f"Wallet {i+1} Export Security", False, f"Error: {e}")
                
        # 5. Test configuration token
        try:
            payload = {
                "name": "Advanced Test Token",
                "symbol": "ATT",
                "description": "Token créé lors des tests avancés",
                "decimals": 9,
                "initial_supply": 1000000000
            }
            resp = requests.patch(f"{BASE_URL}/api/v1/projects/{self.project_id}/token", 
                                json=payload, headers=HEADERS)
            success = resp.status_code == 200
            self.log_test("Token Configuration", success, "Token metadata configured" if success else f"Status: {resp.status_code}")
        except Exception as e:
            self.log_test("Token Configuration", False, f"Error: {e}")
            
        # 6. Test statistiques complètes
        try:
            resp = requests.get(f"{BASE_URL}/api/v1/projects/{self.project_id}/stats")
            if resp.status_code == 200:
                data = resp.json()
                project_info = data.get("project_info", {})
                token_stats = data.get("token_stats", {})
                financial_stats = data.get("financial_stats", {})
                
                wallets_count = project_info.get("wallets_count", 0)
                token_name = token_stats.get("name", "N/A")
                
                self.log_test("Project Stats", True, f"{wallets_count} wallets, token: {token_name}")
            else:
                self.log_test("Project Stats", False, f"Status: {resp.status_code}")
        except Exception as e:
            self.log_test("Project Stats", False, f"Error: {e}")
            
        # 7. Test airdrop (devnet seulement)
        if self.wallet_addresses:
            try:
                payload = {"address": self.wallet_addresses[0], "amount": 0.1}
                resp = requests.post(f"{BASE_URL}/api/v1/airdrop", json=payload, headers=HEADERS)
                if resp.status_code in [200, 201]:
                    self.log_test("Airdrop Test", True, "Airdrop successful")
                elif resp.status_code == 400:
                    data = resp.json()
                    if "devnet" in data.get("error", "").lower():
                        self.log_test("Airdrop Test", True, "Correctly blocked on non-devnet")
                    else:
                        self.log_test("Airdrop Test", False, f"Unexpected error: {data.get('error')}")
                else:
                    self.log_test("Airdrop Test", False, f"Status: {resp.status_code}")
            except Exception as e:
                self.log_test("Airdrop Test", False, f"Error: {e}")
                
        # 8. Test opérations sur les projets
        try:
            # Renommer le projet
            payload = {"name": "Projet Renommé"}
            resp = requests.patch(f"{BASE_URL}/api/v1/projects/{self.project_id}", 
                                json=payload, headers=HEADERS)
            success = resp.status_code == 200
            self.log_test("Rename Project", success, "Project renamed" if success else f"Status: {resp.status_code}")
            
            # Export du projet
            resp = requests.get(f"{BASE_URL}/api/v1/projects/{self.project_id}/export")
            success = resp.status_code == 200
            if success:
                data = resp.json()
                exported_wallets = len(data.get("project_backup", {}).get("wallets", []))
                self.log_test("Export Project", True, f"Exported with {exported_wallets} wallets")
            else:
                self.log_test("Export Project", False, f"Status: {resp.status_code}")
        except Exception as e:
            self.log_test("Project Operations", False, f"Error: {e}")
            
    def test_edge_cases(self):
        """Test cas limites et gestion d'erreurs"""
        print("\n🔬 TEST CAS LIMITES")
        print("=" * 50)
        
        # Test endpoints inexistants
        try:
            resp = requests.get(f"{BASE_URL}/api/v1/nonexistent")
            expected_404 = resp.status_code == 404
            self.log_test("404 Handling", expected_404, "Correctly returns 404 for non-existent endpoints")
        except Exception as e:
            self.log_test("404 Handling", False, f"Error: {e}")
            
        # Test projets inexistants
        try:
            resp = requests.get(f"{BASE_URL}/api/v1/projects/nonexistent")
            expected_404 = resp.status_code == 404
            self.log_test("Non-existent Project", expected_404, "Correctly handles non-existent project")
        except Exception as e:
            self.log_test("Non-existent Project", False, f"Error: {e}")
            
        # Test création de projet sans nom
        try:
            resp = requests.post(f"{BASE_URL}/api/v1/projects", json={}, headers=HEADERS)
            expected_400 = resp.status_code == 400
            self.log_test("Project Without Name", expected_400, "Correctly rejects project creation without name")
        except Exception as e:
            self.log_test("Project Without Name", False, f"Error: {e}")
            
        # Test wallets avec count invalide
        if self.project_id:
            try:
                payload = {"count": -1}
                resp = requests.post(f"{BASE_URL}/api/v1/projects/{self.project_id}/wallets", 
                                   json=payload, headers=HEADERS)
                handles_invalid = resp.status_code == 400
                self.log_test("Invalid Wallet Count", handles_invalid, "Correctly handles invalid wallet count")
            except Exception as e:
                self.log_test("Invalid Wallet Count", False, f"Error: {e}")
    
    def print_summary(self):
        """Résumé final"""
        print("\n" + "=" * 60)
        print("📊 RÉSUMÉ DES TESTS AVANCÉS")
        print("=" * 60)
        
        total = len(self.results)
        passed = sum(1 for r in self.results if r["success"])
        failed = total - passed
        
        print(f"📋 Total: {total} tests")
        print(f"✅ Réussis: {passed}")
        print(f"❌ Échoués: {failed}")
        print(f"📈 Taux de succès: {(passed/total*100):.1f}%")
        
        if failed > 0:
            print(f"\n❌ TESTS ÉCHOUÉS ({failed}):")
            for r in self.results:
                if not r["success"]:
                    print(f"  • {r['test']}: {r['details']}")
        else:
            print(f"\n🎉 TOUS LES TESTS PASSÉS ! API 100% FONCTIONNELLE")
            
        # Sauvegarde
        with open("test_advanced_results.json", "w") as f:
            json.dump(self.results, f, indent=2)
        print(f"\n💾 Résultats détaillés: test_advanced_results.json")

if __name__ == "__main__":
    print("🔬 TESTS AVANCÉS - RUG API v3.6")
    print("Vérification approfondie de tous les endpoints")
    print()
    
    tester = AdvancedTester()
    tester.test_comprehensive_workflow()
    tester.test_edge_cases()
    tester.print_summary()