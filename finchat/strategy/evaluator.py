import uuid
from datetime import datetime
from finchat.strategy.registry import StrategyRegistry
from finchat.evidence.evidence_object import EvidenceObject
import duckdb

class HybridStrategyEngine:
    """
    PHASE 5: Hybrid Strategy Intelligence
    Unlike the standard Data Agent which generates SQL via an LLM, this engine uses
    the Canonical Strategy Registry to construct 100% deterministic SQL logic.
    """
    def __init__(self, registry_dir: str = "context/strategies"):
        self.registry = StrategyRegistry(registry_dir)
        
    def evaluate(self, symbol: str, strategy_name: str, target_date: str) -> EvidenceObject:
        """
        Evaluates a stock against a strictly defined strategy.
        """
        strategy = self.registry.get_strategy(strategy_name)
        if not strategy:
            return EvidenceObject(
                result=f"Strategy '{strategy_name}' not found.",
                source="HybridStrategyEngine",
                as_of=target_date,
                query_id="error",
                calculation="None",
                data_timestamp=datetime.now().isoformat()
            )
            
        # 1. Compile deterministic evaluation plan from the YAML rules
        conditions = []
        for rule in strategy.get('entry', []):
            # Using the exact SQL logic defined by the quant in the YAML
            conditions.append(f"({rule['sql_condition']}) AS rule_{rule['rule_id']}")
            
        if not conditions:
            select_clause = "'No entry rules defined' AS status"
        else:
            select_clause = ",\n    ".join(conditions)
        
        # 2. Build the exact deterministic SQL
        sql = f"""
SELECT 
    symbol,
    date,
    {select_clause}
FROM 'data/parquet/stocks.parquet'
WHERE symbol = '{symbol}' 
  AND date = '{target_date}'
"""
        
        # 3. Execute
        try:
            con = duckdb.connect(':memory:', read_only=False)
            df = con.execute(sql).df()
            result_json = df.to_json(orient='records')
            confidence = "deterministic"
        except Exception as e:
            result_json = f"Evaluation Error: {str(e)}"
            confidence = "error"
            
        return EvidenceObject(
            result=result_json,
            source=f"StrategyRegistry({strategy_name}) + DuckDB",
            as_of=target_date,
            query_id=f"hybrid_eval_{uuid.uuid4().hex[:8]}",
            calculation=sql,
            data_timestamp=datetime.now().isoformat(),
            confidence=confidence
        )
