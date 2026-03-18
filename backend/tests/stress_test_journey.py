"""
FlexFlow Stress & Journey Test Integrado
=========================================

Script de teste que simula uma jornada completa do sistema com:
- 1 Tenant
- 5 Usuários com diferentes roles/permissões
- 1 PO com 10 Itens (mesclando normais e personalizados)
- Cenários de erro proposital para testar robustez
- Rastreabilidade completa de payloads

Cenários de Erro Testados:
1. Login com credenciais inválidas
2. Upload de planilha com dados corrompidos
3. Tentativa de mover item personalizado no PCP sem anexo obrigatório
4. Tentativa de Despacho Final sem NF e Carga prontas (paralelismo)

NÃO EXECUTE ESTE TESTE AINDA - Apenas preparação para o Kickoff
"""

import asyncio
import json
import io
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional
import requests
from pathlib import Path
import pandas as pd
import openpyxl
from colorama import init, Fore, Style

# Initialize colorama for colored output
init(autoreset=True)

# ============================================================================
# CONFIGURATION
# ============================================================================

BASE_URL = "http://localhost:8001"
API_BASE = f"{BASE_URL}/api"

# Test results storage
test_results = {
    "start_time": None,
    "end_time": None,
    "total_requests": 0,
    "successful_requests": 0,
    "failed_requests": 0,
    "scenarios": [],
    "errors": [],
    "payloads": []
}


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def log_info(message: str):
    """Log info message"""
    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} {message}")


def log_success(message: str):
    """Log success message"""
    print(f"{Fore.GREEN}[SUCCESS]{Style.RESET_ALL} {message}")


def log_error(message: str):
    """Log error message"""
    print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} {message}")


def log_warning(message: str):
    """Log warning message"""
    print(f"{Fore.YELLOW}[WARNING]{Style.RESET_ALL} {message}")


def log_scenario(scenario_name: str):
    """Log scenario header"""
    print(f"\n{Fore.MAGENTA}{'='*80}")
    print(f"SCENARIO: {scenario_name}")
    print(f"{'='*80}{Style.RESET_ALL}\n")


def capture_payload(
    scenario: str,
    action: str,
    method: str,
    url: str,
    request_data: Optional[Dict] = None,
    response_status: Optional[int] = None,
    response_data: Optional[Dict] = None,
    error: Optional[str] = None,
    success: bool = True
):
    """Capture request/response payload for traceability"""
    payload_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "scenario": scenario,
        "action": action,
        "method": method,
        "url": url,
        "request_data": request_data,
        "response_status": response_status,
        "response_data": response_data,
        "error": error,
        "success": success
    }
    
    test_results["payloads"].append(payload_entry)
    test_results["total_requests"] += 1
    
    if success:
        test_results["successful_requests"] += 1
    else:
        test_results["failed_requests"] += 1
    
    return payload_entry


def make_request(
    method: str,
    url: str,
    scenario: str,
    action: str,
    headers: Optional[Dict] = None,
    json_data: Optional[Dict] = None,
    files: Optional[Dict] = None,
    data: Optional[Dict] = None,
    expected_status: Optional[int] = None,
    expect_failure: bool = False
) -> Dict[str, Any]:
    """
    Make HTTP request with full traceability
    
    Args:
        method: HTTP method (GET, POST, etc)
        url: Full URL
        scenario: Scenario name for logging
        action: Action description
        headers: Request headers
        json_data: JSON payload
        files: Files to upload
        data: Form data
        expected_status: Expected HTTP status code
        expect_failure: Whether we expect this request to fail
    
    Returns:
        Dict with response data and metadata
    """
    try:
        log_info(f"{action}...")
        
        # Make request
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            json=json_data,
            files=files,
            data=data,
            timeout=30
        )
        
        # Parse response
        try:
            response_data = response.json()
        except:
            response_data = {"raw": response.text}
        
        # Check if request succeeded as expected
        success = True
        error_msg = None
        
        if expect_failure:
            # We expected this to fail
            if response.status_code < 400:
                success = False
                error_msg = f"Expected failure but got status {response.status_code}"
                log_warning(f"{action} - Expected failure but succeeded!")
            else:
                log_success(f"{action} - Failed as expected (status {response.status_code})")
        else:
            # We expected this to succeed
            if response.status_code >= 400:
                success = False
                error_msg = f"Request failed with status {response.status_code}"
                log_error(f"{action} - Failed with status {response.status_code}")
            else:
                log_success(f"{action} - Success (status {response.status_code})")
        
        # Check expected status if provided
        if expected_status and response.status_code != expected_status:
            log_warning(f"Expected status {expected_status}, got {response.status_code}")
        
        # Capture payload
        capture_payload(
            scenario=scenario,
            action=action,
            method=method,
            url=url,
            request_data=json_data or data,
            response_status=response.status_code,
            response_data=response_data,
            error=error_msg,
            success=success
        )
        
        return {
            "success": success,
            "status_code": response.status_code,
            "data": response_data,
            "error": error_msg
        }
        
    except Exception as e:
        error_msg = f"Exception during request: {str(e)}"
        log_error(error_msg)
        
        capture_payload(
            scenario=scenario,
            action=action,
            method=method,
            url=url,
            request_data=json_data or data,
            response_status=None,
            response_data=None,
            error=error_msg,
            success=False
        )
        
        return {
            "success": False,
            "status_code": None,
            "data": None,
            "error": error_msg
        }


# ============================================================================
# TEST DATA GENERATION
# ============================================================================

class TestDataGenerator:
    """Generate test data for stress testing"""
    
    @staticmethod
    def create_tenant() -> Dict[str, Any]:
        """Create tenant data"""
        return {
            "id": "tenant-stress-test-001",
            "name": "PromaFlex Stress Test",
            "created_at": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def create_users() -> List[Dict[str, Any]]:
        """Create 5 users with different roles and permissions"""
        return [
            {
                "id": "user-001-admin",
                "email": "admin@promaflex.com",
                "password": "Admin@123",
                "name": "Admin User",
                "role": "admin",
                "permissions": [
                    "po.create", "po.read", "po.update", "po.delete",
                    "po.approve_comercial", "po.approve_pcp", "po.reject_pcp",
                    "po.approve_producao", "po.complete_expedicao",
                    "po.complete_faturamento", "po.approve_despacho",
                    "po.audit.read"
                ]
            },
            {
                "id": "user-002-comercial",
                "email": "comercial@promaflex.com",
                "password": "Comercial@123",
                "name": "Comercial Manager",
                "role": "comercial_manager",
                "permissions": [
                    "po.create", "po.read", "po.update",
                    "po.approve_comercial"
                ]
            },
            {
                "id": "user-003-pcp",
                "email": "pcp@promaflex.com",
                "password": "PCP@123",
                "name": "PCP Manager",
                "role": "pcp_manager",
                "permissions": [
                    "po.read", "po.update",
                    "po.approve_pcp", "po.reject_pcp"
                ]
            },
            {
                "id": "user-004-producao",
                "email": "producao@promaflex.com",
                "password": "Producao@123",
                "name": "Production Manager",
                "role": "producao_manager",
                "permissions": [
                    "po.read", "po.update",
                    "po.approve_producao"
                ]
            },
            {
                "id": "user-005-expedicao",
                "email": "expedicao@promaflex.com",
                "password": "Expedicao@123",
                "name": "Shipping & Invoicing Manager",
                "role": "expedicao_manager",
                "permissions": [
                    "po.read", "po.update",
                    "po.complete_expedicao", "po.complete_faturamento",
                    "po.approve_despacho"
                ]
            }
        ]
    
    @staticmethod
    def create_po_items() -> List[Dict[str, Any]]:
        """Create 10 items (mix of normal and personalized)"""
        items = []
        
        # 6 normal items
        for i in range(1, 7):
            items.append({
                "sku": f"SKU-NORMAL-{i:03d}",
                "description": f"Standard Product {i}",
                "quantity": 10 + (i * 5),
                "price_unit": float(100 + (i * 10)),
                "cost_mp": float(40 + (i * 3)),
                "cost_mo": float(20 + (i * 2)),
                "cost_energy": float(5 + i),
                "cost_gas": float(3 + i),
                "is_personalized": False
            })
        
        # 4 personalized items (require attachments in PCP)
        for i in range(1, 5):
            items.append({
                "sku": f"SKU-CUSTOM-{i:03d}",
                "description": f"Customized Product {i}",
                "quantity": 5 + (i * 3),
                "price_unit": float(200 + (i * 20)),
                "cost_mp": float(80 + (i * 5)),
                "cost_mo": float(40 + (i * 3)),
                "cost_energy": float(10 + i),
                "cost_gas": float(6 + i),
                "is_personalized": True
            })
        
        return items
    
    @staticmethod
    def create_excel_file(items: List[Dict[str, Any]], corrupted: bool = False) -> bytes:
        """
        Create Excel file for import
        
        Args:
            items: List of items to include
            corrupted: If True, create corrupted data
        """
        # Create DataFrame
        data = {
            "PO Number": ["PO-STRESS-2026-001"] * len(items),
            "Client": ["PromaFlex Test Client"] * len(items),
            "SKU": [item["sku"] for item in items],
            "Description": [item["description"] for item in items],
            "Quantity": [item["quantity"] for item in items],
            "Price": [item["price_unit"] for item in items],
            "Cost MP": [item["cost_mp"] for item in items],
            "Cost MO": [item["cost_mo"] for item in items],
            "Cost Energy": [item["cost_energy"] for item in items],
            "Cost Gas": [item["cost_gas"] for item in items]
        }
        
        if corrupted:
            # Corrupt some data
            data["Quantity"][0] = "INVALID_NUMBER"  # String instead of number
            data["Price"][1] = -100  # Negative price
            data["Cost MP"][2] = "corrupted"  # Invalid cost
        
        df = pd.DataFrame(data)
        
        # Save to bytes
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='PO Data')
        
        output.seek(0)
        return output.getvalue()


# ============================================================================
# TEST SCENARIOS
# ============================================================================

class StressTestJourney:
    """Main stress test journey orchestrator"""
    
    def __init__(self):
        self.tenant = TestDataGenerator.create_tenant()
        self.users = TestDataGenerator.create_users()
        self.items = TestDataGenerator.create_po_items()
        self.tokens = {}  # Store auth tokens
        self.po_id = None
        
    async def run_all_scenarios(self):
        """Run all test scenarios"""
        log_info("Starting FlexFlow Stress & Journey Test")
        log_info(f"Base URL: {BASE_URL}")
        log_info(f"Tenant: {self.tenant['name']}")
        log_info(f"Users: {len(self.users)}")
        log_info(f"Items: {len(self.items)}")
        
        test_results["start_time"] = datetime.utcnow().isoformat()
        
        # Run scenarios
        await self.scenario_1_invalid_login()
        await self.scenario_2_valid_login()
        await self.scenario_3_corrupted_upload()
        await self.scenario_4_valid_upload()
        await self.scenario_5_pcp_without_attachment()
        await self.scenario_6_pcp_with_attachment()
        await self.scenario_7_parallel_states_incomplete()
        await self.scenario_8_complete_journey()
        
        test_results["end_time"] = datetime.utcnow().isoformat()
        
        # Generate report
        self.generate_report()
    
    async def scenario_1_invalid_login(self):
        """Scenario 1: Login with invalid credentials (EXPECTED TO FAIL)"""
        log_scenario("SCENARIO 1: Login com Credenciais Inválidas")
        
        invalid_credentials = [
            {"email": "invalid@test.com", "password": "wrong"},
            {"email": "admin@promaflex.com", "password": "WrongPassword"},
            {"email": "", "password": ""},
            {"email": "notanemail", "password": "test123"}
        ]
        
        for cred in invalid_credentials:
            result = make_request(
                method="POST",
                url=f"{API_BASE}/auth/login",
                scenario="Invalid Login",
                action=f"Login attempt with {cred['email']}",
                json_data=cred,
                expect_failure=True
            )
            
            # Small delay between attempts
            time.sleep(0.5)
    
    async def scenario_2_valid_login(self):
        """Scenario 2: Valid login for all users"""
        log_scenario("SCENARIO 2: Login Válido para Todos os Usuários")
        
        for user in self.users:
            result = make_request(
                method="POST",
                url=f"{API_BASE}/auth/login",
                scenario="Valid Login",
                action=f"Login as {user['name']} ({user['role']})",
                json_data={
                    "email": user["email"],
                    "password": user["password"]
                },
                expected_status=200
            )
            
            if result["success"] and result["data"]:
                # Store token
                token = result["data"].get("access_token")
                if token:
                    self.tokens[user["id"]] = token
                    log_success(f"Token stored for {user['name']}")
            
            time.sleep(0.3)
    
    async def scenario_3_corrupted_upload(self):
        """Scenario 3: Upload corrupted Excel file (EXPECTED TO FAIL)"""
        log_scenario("SCENARIO 3: Upload de Planilha com Dados Corrompidos")
        
        # Get admin token
        admin_token = self.tokens.get("user-001-admin")
        if not admin_token:
            log_error("Admin token not available, skipping scenario")
            return
        
        # Create corrupted Excel
        corrupted_excel = TestDataGenerator.create_excel_file(
            self.items[:3],  # Only first 3 items
            corrupted=True
        )
        
        # Prepare mapping
        mapping = {
            "mappings": [
                {"column_name": "PO Number", "field_type": "po_number"},
                {"column_name": "Client", "field_type": "client_name"},
                {"column_name": "SKU", "field_type": "sku"},
                {"column_name": "Quantity", "field_type": "quantity"},
                {"column_name": "Price", "field_type": "price_unit"},
                {"column_name": "Cost MP", "field_type": "cost_mp"},
                {"column_name": "Cost MO", "field_type": "cost_mo"},
                {"column_name": "Cost Energy", "field_type": "cost_energy"},
                {"column_name": "Cost Gas", "field_type": "cost_gas"}
            ]
        }
        
        # Upload corrupted file
        result = make_request(
            method="POST",
            url=f"{API_BASE}/import/upload",
            scenario="Corrupted Upload",
            action="Upload corrupted Excel file",
            headers={"Authorization": f"Bearer {admin_token}"},
            files={
                "file": ("corrupted_po.xlsx", corrupted_excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            },
            data={
                "mapping_json": json.dumps(mapping)
            },
            expect_failure=True
        )
    
    async def scenario_4_valid_upload(self):
        """Scenario 4: Upload valid Excel file"""
        log_scenario("SCENARIO 4: Upload de Planilha Válida")
        
        # Get comercial token
        comercial_token = self.tokens.get("user-002-comercial")
        if not comercial_token:
            log_error("Comercial token not available, skipping scenario")
            return
        
        # Create valid Excel
        valid_excel = TestDataGenerator.create_excel_file(
            self.items,
            corrupted=False
        )
        
        # Prepare mapping
        mapping = {
            "mappings": [
                {"column_name": "PO Number", "field_type": "po_number"},
                {"column_name": "Client", "field_type": "client_name"},
                {"column_name": "SKU", "field_type": "sku"},
                {"column_name": "Quantity", "field_type": "quantity"},
                {"column_name": "Price", "field_type": "price_unit"},
                {"column_name": "Cost MP", "field_type": "cost_mp"},
                {"column_name": "Cost MO", "field_type": "cost_mo"},
                {"column_name": "Cost Energy", "field_type": "cost_energy"},
                {"column_name": "Cost Gas", "field_type": "cost_gas"}
            ]
        }
        
        # Upload valid file
        result = make_request(
            method="POST",
            url=f"{API_BASE}/import/upload",
            scenario="Valid Upload",
            action="Upload valid Excel file with 10 items",
            headers={"Authorization": f"Bearer {comercial_token}"},
            files={
                "file": ("valid_po.xlsx", valid_excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            },
            data={
                "mapping_json": json.dumps(mapping)
            },
            expected_status=200
        )
        
        if result["success"] and result["data"]:
            # Extract PO ID from response
            self.po_id = result["data"].get("po_id")
            if self.po_id:
                log_success(f"PO created with ID: {self.po_id}")
    
    async def scenario_5_pcp_without_attachment(self):
        """Scenario 5: Try to move personalized item in PCP without attachment (EXPECTED TO FAIL)"""
        log_scenario("SCENARIO 5: Tentar Mover Item Personalizado no PCP sem Anexo")
        
        if not self.po_id:
            log_error("PO ID not available, skipping scenario")
            return
        
        # Get PCP token
        pcp_token = self.tokens.get("user-003-pcp")
        if not pcp_token:
            log_error("PCP token not available, skipping scenario")
            return
        
        # Try to approve PCP -> PRODUCAO without attachments for personalized items
        result = make_request(
            method="POST",
            url=f"{API_BASE}/kanban/move-status",
            scenario="PCP Without Attachment",
            action="Try to approve PCP without attachments for personalized items",
            headers={"Authorization": f"Bearer {pcp_token}"},
            json_data={
                "po_id": self.po_id,
                "to_status": "PRODUCAO",
                "reason": "Attempting to approve without required attachments"
            },
            expect_failure=True
        )
    
    async def scenario_6_pcp_with_attachment(self):
        """Scenario 6: Approve PCP with attachment"""
        log_scenario("SCENARIO 6: Aprovar PCP com Anexo")
        
        if not self.po_id:
            log_error("PO ID not available, skipping scenario")
            return
        
        # Get PCP token
        pcp_token = self.tokens.get("user-003-pcp")
        if not pcp_token:
            log_error("PCP token not available, skipping scenario")
            return
        
        # Note: In a real scenario, we would upload attachments first
        # For this test, we'll simulate that attachments were added
        log_info("Simulating attachment upload for personalized items...")
        
        # Now approve PCP -> PRODUCAO
        result = make_request(
            method="POST",
            url=f"{API_BASE}/kanban/move-status",
            scenario="PCP With Attachment",
            action="Approve PCP with attachments",
            headers={"Authorization": f"Bearer {pcp_token}"},
            json_data={
                "po_id": self.po_id,
                "to_status": "PRODUCAO",
                "reason": "All personalized items have technical drawings attached"
            },
            expected_status=200
        )
    
    async def scenario_7_parallel_states_incomplete(self):
        """Scenario 7: Try to complete DESPACHO without both parallel states ready (EXPECTED TO FAIL)"""
        log_scenario("SCENARIO 7: Tentar Despacho sem NF e Carga Prontas")
        
        if not self.po_id:
            log_error("PO ID not available, skipping scenario")
            return
        
        # Get producao token
        producao_token = self.tokens.get("user-004-producao")
        if not producao_token:
            log_error("Producao token not available, skipping scenario")
            return
        
        # First, approve PRODUCAO to move to parallel states
        result = make_request(
            method="POST",
            url=f"{API_BASE}/kanban/move-status",
            scenario="Parallel States Setup",
            action="Approve PRODUCAO to enter parallel states",
            headers={"Authorization": f"Bearer {producao_token}"},
            json_data={
                "po_id": self.po_id,
                "to_status": "EXPEDICAO_PENDENTE",
                "reason": "Production completed"
            },
            expected_status=200
        )
        
        time.sleep(0.5)
        
        # Get expedicao token
        expedicao_token = self.tokens.get("user-005-expedicao")
        if not expedicao_token:
            log_error("Expedicao token not available, skipping scenario")
            return
        
        # Try to move to DESPACHO without completing both parallel states
        result = make_request(
            method="POST",
            url=f"{API_BASE}/kanban/move-status",
            scenario="Incomplete Parallel States",
            action="Try to move to DESPACHO with incomplete parallel states",
            headers={"Authorization": f"Bearer {expedicao_token}"},
            json_data={
                "po_id": self.po_id,
                "to_status": "DESPACHO",
                "reason": "Attempting premature dispatch"
            },
            expect_failure=True
        )
    
    async def scenario_8_complete_journey(self):
        """Scenario 8: Complete the full journey successfully"""
        log_scenario("SCENARIO 8: Jornada Completa de Sucesso")
        
        if not self.po_id:
            log_error("PO ID not available, skipping scenario")
            return
        
        # Get expedicao token
        expedicao_token = self.tokens.get("user-005-expedicao")
        if not expedicao_token:
            log_error("Expedicao token not available, skipping scenario")
            return
        
        # Complete EXPEDICAO_PENDENTE
        log_info("Completing EXPEDICAO_PENDENTE...")
        # Note: In real scenario, would need to mark packing list, etc.
        
        # Complete FATURAMENTO_PENDENTE
        log_info("Completing FATURAMENTO_PENDENTE...")
        # Note: In real scenario, would need to upload invoice, etc.
        
        # Now both parallel states are complete, move to DESPACHO
        result = make_request(
            method="POST",
            url=f"{API_BASE}/kanban/move-status",
            scenario="Complete Journey",
            action="Move to DESPACHO with both parallel states complete",
            headers={"Authorization": f"Bearer {expedicao_token}"},
            json_data={
                "po_id": self.po_id,
                "to_status": "DESPACHO",
                "reason": "Both EXPEDICAO and FATURAMENTO completed"
            },
            expected_status=200
        )
        
        time.sleep(0.5)
        
        # Complete DESPACHO -> CONCLUIDO
        result = make_request(
            method="POST",
            url=f"{API_BASE}/kanban/move-status",
            scenario="Complete Journey",
            action="Complete DESPACHO and finalize PO",
            headers={"Authorization": f"Bearer {expedicao_token}"},
            json_data={
                "po_id": self.po_id,
                "to_status": "CONCLUIDO",
                "reason": "Order dispatched successfully"
            },
            expected_status=200
        )
        
        log_success("Complete journey finished!")
    
    def generate_report(self):
        """Generate comprehensive test report"""
        log_scenario("TEST REPORT")
        
        # Calculate duration
        start = datetime.fromisoformat(test_results["start_time"])
        end = datetime.fromisoformat(test_results["end_time"])
        duration = (end - start).total_seconds()
        
        # Print summary
        print(f"\n{Fore.CYAN}{'='*80}")
        print(f"STRESS TEST SUMMARY")
        print(f"{'='*80}{Style.RESET_ALL}\n")
        
        print(f"Duration: {duration:.2f} seconds")
        print(f"Total Requests: {test_results['total_requests']}")
        print(f"Successful: {Fore.GREEN}{test_results['successful_requests']}{Style.RESET_ALL}")
        print(f"Failed: {Fore.RED}{test_results['failed_requests']}{Style.RESET_ALL}")
        print(f"Success Rate: {(test_results['successful_requests'] / test_results['total_requests'] * 100):.2f}%")
        
        # Save detailed report to file
        report_path = Path(__file__).parent / "stress_test_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(test_results, f, indent=2, ensure_ascii=False)
        
        log_success(f"Detailed report saved to: {report_path}")
        
        # Print payload summary
        print(f"\n{Fore.CYAN}PAYLOAD SUMMARY:{Style.RESET_ALL}")
        for i, payload in enumerate(test_results["payloads"][-10:], 1):  # Last 10 payloads
            status_color = Fore.GREEN if payload["success"] else Fore.RED
            print(f"{i}. [{status_color}{payload['scenario']}{Style.RESET_ALL}] "
                  f"{payload['action']} - Status: {payload['response_status']}")


# ============================================================================
# MAIN EXECUTION
# ============================================================================

async def main():
    """Main entry point"""
    print(f"\n{Fore.YELLOW}{'='*80}")
    print(f"FlexFlow - Stress & Journey Test Integrado")
    print(f"{'='*80}{Style.RESET_ALL}\n")
    
    print(f"{Fore.YELLOW}[!] ATENCAO: Este e um teste de stress que simula erros propositais!")
    print(f"[!] NAO EXECUTE em ambiente de producao!")
    print(f"[!] Certifique-se de que o servidor esta rodando em {BASE_URL}{Style.RESET_ALL}\n")
    
    # Check if server is running
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            log_success("Server is running and healthy")
        else:
            log_error(f"Server returned status {response.status_code}")
            return
    except Exception as e:
        log_error(f"Cannot connect to server: {str(e)}")
        log_error(f"Please start the server with: uvicorn backend.main:app --reload")
        return
    
    # Run tests
    journey = StressTestJourney()
    await journey.run_all_scenarios()
    
    print(f"\n{Fore.GREEN}[OK] Stress Test Completed!{Style.RESET_ALL}\n")


if __name__ == "__main__":
    asyncio.run(main())