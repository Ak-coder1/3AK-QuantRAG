# -------------------------------------------------------------------
# 3AK-QuantRAG
# https://github.com/Ak-coder1/3AK-QuantRAG
# -------------------------------------------------------------------

from dataclasses import dataclass
from typing import Any

@dataclass
class EvidenceObject:
    """
    Standardized Evidence payload that all tools must return.
    Ensures that the LLM is always provided with provenance and context rather than raw strings.
    """
    result: Any                     # The factual result (e.g., 1.87, True, or tabular JSON)
    source: str                     # Source of the data (e.g., "v_stock_daily", "svro.yaml")
    as_of: str                      # Context date the data is valid for
    query_id: str                   # Traceable ID (e.g., "duckdb_exec_7392")
    calculation: str                # The formula, SQL, or logic used
    data_timestamp: str             # When the underlying data was last updated
    confidence: str = "deterministic" # Confidence level (deterministic, heuristic, inference)

    def to_llm_context(self) -> str:
        """Formats the evidence clearly for the LLM to ingest during the Explain phase."""
        return (
            f"--- EVIDENCE BLOCK [{self.query_id}] ---\n"
            f"Result: {self.result}\n"
            f"Source: {self.source}\n"
            f"Calculation/Logic: {self.calculation}\n"
            f"Valid As Of: {self.as_of} (Data pulled at {self.data_timestamp})\n"
            f"Confidence: {self.confidence}\n"
            f"--------------------------------"
        )
