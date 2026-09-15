import urllib.request
import json
from datetime import datetime
from finchat.evidence.evidence_object import EvidenceObject

class LiveToolGateway:
    """
    Phase 6: Connects the Orchestrator to the Live TradeSetup ChartingClient API.
    Fetches real-time portfolio state, positions, and orders.
    """
    def __init__(self, base_url="http://127.0.0.1:5000"):
        self.base_url = base_url

    def fetch_live_state(self) -> EvidenceObject:
        print("      [LiveGateway] Fetching live portfolio overview and positions...")
        try:
            # 1. Fetch Overview (KPIs, Equity, Regime)
            req_overview = urllib.request.Request(f"{self.base_url}/api/tm/overview")
            with urllib.request.urlopen(req_overview, timeout=3.0) as res:
                overview = json.loads(res.read().decode('utf-8'))
                
            # 2. Fetch Active Positions
            req_pos = urllib.request.Request(f"{self.base_url}/api/tm/positions")
            with urllib.request.urlopen(req_pos, timeout=3.0) as res:
                positions = json.loads(res.read().decode('utf-8'))
                
            # 3. Fetch Pending Trades (PTrades)
            req_ptrades = urllib.request.Request(f"{self.base_url}/api/tm/ptrades")
            try:
                with urllib.request.urlopen(req_ptrades, timeout=3.0) as res:
                    ptrades = json.loads(res.read().decode('utf-8'))
            except Exception:
                ptrades = []
                
            # 4. Fetch Today's Audit Log
            today_str = datetime.now().strftime("%Y-%m-%d")
            req_audit = urllib.request.Request(f"{self.base_url}/api/tm/audit?date={today_str}")
            try:
                with urllib.request.urlopen(req_audit, timeout=3.0) as res:
                    audit = json.loads(res.read().decode('utf-8'))
            except Exception:
                audit = {}
                
            combined_data = {
                "portfolio_kpis": overview,
                "active_positions": positions,
                "pending_ptrades": ptrades,
                "audit_events_today": audit
            }
            
            print("      [LiveGateway] Successfully fetched live portfolio state.")
            
            return EvidenceObject(
                result=combined_data,
                source="LiveToolGateway -> ChartingClient REST API",
                as_of=datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                query_id="live_state_001",
                calculation="Live HTTP GET to /api/tm/overview, /api/tm/positions, ptrades, and audit logs.",
                data_timestamp=datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                confidence="deterministic"
            )
        except Exception as e:
            print(f"      [LiveGateway Error] Could not connect to ChartingClient API: {e}")
            return EvidenceObject(
                result={"error": f"Failed to connect to ChartingClient on {self.base_url}. Is the main server running?"},
                source="LiveToolGateway -> ChartingClient REST API",
                as_of=datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                query_id="live_state_error",
                calculation=f"Attempted GET /api/tm/overview. Exception: {str(e)}",
                data_timestamp=datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                confidence="error"
            )
