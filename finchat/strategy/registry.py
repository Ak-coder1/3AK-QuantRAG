# -------------------------------------------------------------------
# 3AK-QuantRAG
# https://github.com/Ak-coder1/3AK-QuantRAG
# -------------------------------------------------------------------

import os
import yaml
from typing import Dict, Any

class StrategyRegistry:
    """
    Parses and serves the Canonical Strategy Registry.
    Provides machine-readable rules (SQL conditions, logic) to the orchestrator
    so that rule evaluation is deterministic rather than LLM-inferred.
    """
    def __init__(self, registry_dir: str = "context/strategies"):
        self.registry_dir = registry_dir
        self.strategies: Dict[str, Dict[str, Any]] = {}
        self._load_strategies()

    def _load_strategies(self):
        if not os.path.exists(self.registry_dir):
            os.makedirs(self.registry_dir, exist_ok=True)
            return
            
        for filename in os.listdir(self.registry_dir):
            if filename.endswith(".yaml") or filename.endswith(".yml"):
                filepath = os.path.join(self.registry_dir, filename)
                with open(filepath, 'r') as f:
                    try:
                        data = yaml.safe_load(f)
                        if data and 'strategy' in data:
                            self.strategies[data['strategy'].upper()] = data
                    except Exception as e:
                        print(f"Error parsing {filepath}: {e}")

    def get_strategy(self, name: str) -> Dict[str, Any]:
        """Retrieve a canonical strategy definition by name."""
        return self.strategies.get(name.upper())

    def get_strategy_evaluation_plan(self, name: str) -> str:
        """
        Formats the strategy rules into a deterministic evaluation plan
        for the LLM / Orchestrator to follow.
        """
        strategy = self.get_strategy(name)
        if not strategy:
            return f"Strategy '{name}' not found in registry."
            
        plan = f"STRATEGY: {strategy['strategy']} (v{strategy.get('version', 'unknown')})\n"
        plan += f"DESC: {strategy.get('description', '')}\n\n"
        plan += "DETERMINISTIC EVALUATION RULES:\n"
        
        for rule in strategy.get('entry', []):
            rule_id = rule.get('rule_id', 'unknown')
            desc = rule.get('description', '')
            cond = rule.get('sql_condition', 'needs manual validation')
            plan += f"- Rule [{rule_id}]: {desc}\n"
            plan += f"  > SQL Eval: {cond}\n"
            
        return plan

if __name__ == "__main__":
    registry = StrategyRegistry("../../context/strategies")
    print("Loaded strategies:", list(registry.strategies.keys()))
    print("\n--- Example Evaluation Plan ---")
    print(registry.get_strategy_evaluation_plan("SVRO"))
