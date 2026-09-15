import os
import yaml
from typing import Dict, List, Any

class SemanticDataCatalog:
    """
    Parses and serves the Semantic Data Catalog from the YAML definitions.
    This provides the LLM with exact formulas, units, null semantics, and join keys
    so it can write deterministic DuckDB SQL queries without hallucination.
    """
    def __init__(self, catalog_dir: str = "context/catalog"):
        self.catalog_dir = catalog_dir
        self.datasets: Dict[str, Dict[str, Any]] = {}
        self.metrics: Dict[str, Dict[str, Any]] = {}
        self._load_catalog()

    def _load_catalog(self):
        """Loads all YAML files from the context/catalog directory."""
        if not os.path.exists(self.catalog_dir):
            print(f"Warning: Catalog directory {self.catalog_dir} not found.")
            return

        for filename in os.listdir(self.catalog_dir):
            if filename.endswith(".yaml") or filename.endswith(".yml"):
                filepath = os.path.join(self.catalog_dir, filename)
                with open(filepath, 'r') as f:
                    try:
                        # Some YAML files might contain multiple documents or lists of datasets
                        content = yaml.safe_load(f)
                        if isinstance(content, list):
                            for dataset in content:
                                self._register_dataset(dataset)
                        elif isinstance(content, dict):
                            self._register_dataset(content)
                    except Exception as e:
                        print(f"Error parsing {filepath}: {e}")

    def _register_dataset(self, dataset: Dict[str, Any]):
        dataset_key = dataset.get("dataset_key")
        if not dataset_key:
            return
        
        self.datasets[dataset_key] = dataset
        
        # Register individual metrics/columns for quick semantic lookup
        for col in dataset.get("columns", []):
            col_name = col.get("name")
            if col_name:
                self.metrics[f"{dataset_key}.{col_name}"] = col

    def get_table_schema_prompt(self, dataset_key: str, table_name_override: str = None) -> str:
        """
        Generates a highly compressed, LLM-friendly schema prompt for a specific dataset,
        including all units, formulas, and verified semantics.
        """
        if dataset_key not in self.datasets:
            return f"Dataset {dataset_key} not found."
            
        dataset = self.datasets[dataset_key]
        display_name = table_name_override if table_name_override else dataset_key
        prompt = f"TABLE NAME IN DATABASE: {display_name}\n"
        prompt += f"PURPOSE: {dataset.get('purpose', '').strip()}\n\n"
        prompt += "COLUMNS (Semantic Definitions):\n"
        
        for col in dataset.get("columns", []):
            name = col.get("name", "Unknown")
            dtype = col.get("dtype", "Unknown")
            meaning = col.get("meaning", "").strip().replace("\n", " ")
            
            prompt += f"- `{name}` ({dtype}): {meaning}\n"
            
            best_used = col.get("best_used_for")
            if best_used and best_used != "UNVERIFIED - needs review":
                prompt += f"  > Usage: {best_used}\n"
                
        return prompt

    def get_all_dataset_keys(self) -> List[str]:
        return list(self.datasets.keys())


if __name__ == "__main__":
    # Test loading the catalog and generating a schema prompt
    catalog = SemanticDataCatalog("../../context/catalog")
    print(f"Loaded {len(catalog.datasets)} datasets.")
    
    # Example: print the schema for the OHLCV indicator set if it exists
    if "stock_indicator_43metric" in catalog.datasets:
        print("\n--- Example Schema Prompt for LLM ---")
        print(catalog.get_table_schema_prompt("stock_indicator_43metric"))
