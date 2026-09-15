from typing import Dict, Any
import uuid

class ActionGateway:
    """
    PHASE 8: Controlled Actions
    The strict barrier between FinChat proposing an action and it actually executing.
    """
    
    def propose_action(self, action_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Registers an action proposal. FinChat CANNOT execute actions directly.
        It generates a proposal, returns the ID to the UI, and the USER must click 'Approve'.
        """
        proposal_id = f"action_req_{uuid.uuid4().hex[:8]}"
        
        # Example: Writing to a pending actions table or sending to UI via WebSockets
        print(f"[ACTION GATEWAY] Action '{action_type}' proposed. Awaiting user approval.")
        print(f"   Payload: {payload}")
        
        return {
            "proposal_id": proposal_id,
            "status": "PENDING_HUMAN_APPROVAL",
            "message": "Action successfully proposed. Waiting for user to approve in the UI."
        }
