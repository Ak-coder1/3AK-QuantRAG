# -------------------------------------------------------------------
# 3AK-QuantRAG
# https://github.com/Ak-coder1/3AK-QuantRAG
# -------------------------------------------------------------------

from finchat.orchestration.router import IntentRouter
from finchat.data.sql_agent import DeterministicQueryEngine
from finchat.data.live_gateway import LiveToolGateway
from finchat.retrieval.hybrid_search import HybridRetriever
from finchat.evidence.evidence_object import EvidenceObject
from finchat.config.llm import get_llm_client
from datetime import datetime

import time

class CopilotOrchestrator:
    """
    The main intelligence layer that receives user queries, plans the execution,
    aggregates Evidence Objects, and synthesizes the final explainable answer.
    """
    def __init__(self):
        self.router = IntentRouter()
        self.data_engine = DeterministicQueryEngine("context/catalog")
        self.rag_engine = HybridRetriever()
        self.live_gateway = LiveToolGateway()

    def process_query(self, query: str, provider: str = "ollama") -> str:
        start_time = time.time()
        print(f"\n[Orchestrator] Processing: '{query}' (Mode: {provider.upper()})")
        
        # Step 1: Routing
        intent = self.router.route_query(query, provider)
        print(f"[Orchestrator] Detected Intent: {intent.upper()}")
        
        evidence_list = []
        
        # Step 2: Execution (Dispatching based on Intent)
        if intent == "adversarial":
            return "Security Policy Violation: I cannot modify data, execute arbitrary code, or fulfill this request."
            
        elif intent == "knowledge":
            # Document Search
            evidence = self.rag_engine.retrieve(query)
            evidence_list.append(evidence)
            
        elif intent in ["data", "analytical"]:
            dataset_key = self._extract_dataset(query, provider)
            print(f"[Orchestrator] Extracted Dataset Entity: {dataset_key.upper()}")
            # SQL Data Agent
            as_of = datetime.now().strftime("%Y-%m-%d")
            evidence = self.data_engine.execute_query(dataset_key, query, as_of, provider)
            evidence_list.append(evidence)
            
        elif intent == "hybrid":
            dataset_key = self._extract_dataset(query, provider)
            print(f"[Orchestrator] Extracted Dataset Entity: {dataset_key.upper()}")
            # Multi-Hop Execution
            print("[Orchestrator] Executing Multi-Hop Hybrid Plan...")
            rag_evidence = self.rag_engine.retrieve(query)
            evidence_list.append(rag_evidence)
            data_evidence = self.data_engine.execute_query(dataset_key, query, datetime.now().strftime("%Y-%m-%d"), provider)
            evidence_list.append(data_evidence)
            
        elif intent == "live_api":
            # Phase 6: Live Portfolio State
            print("[Orchestrator] Routing to LiveToolGateway...")
            evidence = self.live_gateway.fetch_live_state()
            evidence_list.append(evidence)
        else:
            evidence_list.append(EvidenceObject(
                result={},
                source="Router",
                as_of=datetime.now().strftime("%Y-%m-%d"),
                query_id="fallback_001",
                calculation=f"Intent '{intent}' is unrecognized.",
                data_timestamp=datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                confidence="error"
            ))
            
        # Step 3: Synthesis & Explanation
        answer = self._synthesize_answer(query, evidence_list, provider)
        
        end_time = time.time()
        print(f"[Orchestrator] Total Execution Time: {end_time - start_time:.2f} seconds")
        
        return {
            "answer": answer,
            "evidence_list": evidence_list
        }

    def _extract_dataset(self, query: str, provider: str = "ollama") -> str:
        """
        Dynamically extracts the target dataset from the user's query.
        """
        llm = get_llm_client('router', provider)
        prompt = f"User Query: '{query}'"
        system_prompt = (
            "You are an Entity Extraction engine. Identify the most relevant dataset for this query.\n"
            "Available datasets:\n"
            "- stock_indicator_43metric: (default) General market data, prices, volume, moving averages.\n"
            "- cme_stocks_parquet: Relative Strength (rs_ratio, rs_mom), momentum, and comparative performance against Nifty 500/Midcap.\n"
            "- delivery_parquet: Daily delivery volumes, institutional accumulation, and delivery percentage.\n"
            "- index_parquet: Broader market index OHLCV and indicators (e.g., Nifty 50, Nifty 500).\n"
            "- sector_index_parquet: Sector-specific index data (e.g., Auto, IT, Pharma).\n"
            "Return ONLY the exact dataset name string in lowercase. If unsure, return 'stock_indicator_43metric'."
        )
        print(f"      [Extractor] Asking {provider.upper()} ({llm.model_name}) to extract dataset entity...")
        dataset = llm.generate_completion(prompt=prompt, system_prompt=system_prompt, temperature=0.0).strip().lower()
        
        # Sanitize fallback
        valid_datasets = ["stock_indicator_43metric", "cme_stocks_parquet", "delivery_parquet", "index_parquet", "sector_index_parquet"]
        for valid in valid_datasets:
            if valid in dataset:
                return valid
        return "stock_indicator_43metric"

    def _synthesize_answer(self, query: str, evidence_list: list[EvidenceObject], provider: str = "ollama") -> str:
        """
        Final phase: The LLM reads all gathered evidence and answers the user.
        """
        llm = get_llm_client('synthesis', provider)
        print("[Orchestrator] Synthesizing final answer from Evidence...")
        system_prompt = (
            "You are 3AK-QuantRAG, a deterministic AI copilot for quantitative finance. "
            "You MUST base your answer strictly on the provided EVIDENCE BLOCKS. "
            "If the evidence does not contain the answer, explicitly state that. "
            "Do NOT hallucinate financial data. Always cite the Source and Calculation used."
            "You are a quantitative trading assistant. Answer the user's query using ONLY the provided Evidence Block. "
            "Do NOT hallucinate metrics, dates, or prices. If the evidence contains an error, state the error gracefully."
        )
        
        compiled_evidence = "\n".join([e.to_llm_context() for e in evidence_list])
        print(f"      [Synthesizer] Compiled Evidence Block (Sent to {provider.upper()} - {llm.model_name}):\n{compiled_evidence}\n")
        
        prompt = (
            f"User Question: '{query}'\n\n"
            f"--- EVIDENCE BLOCKS ---\n"
            f"{compiled_evidence}\n"
            f"-----------------------\n\n"
            "Generate a clear, explainable answer based ONLY on the evidence above."
        )
        
        import time
        s_start = time.time()
        response = llm.generate_completion(prompt=prompt, system_prompt=system_prompt, temperature=0.0)
        s_end = time.time()
        print(f"[Orchestrator] Synthesis completed in {s_end - s_start:.2f} seconds.")
        return response

if __name__ == "__main__":
    copilot = CopilotOrchestrator()
    answer = copilot.process_query("What is the SVRO entry rule?")
    print("\n--- FINAL ANSWER ---")
    print(answer)
