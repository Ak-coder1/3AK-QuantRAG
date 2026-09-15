# -------------------------------------------------------------------
# 3AK-QuantRAG
# https://github.com/Ak-coder1/3AK-QuantRAG
# -------------------------------------------------------------------

import uuid
from datetime import datetime
import re

from finchat.data.semantic_catalog import SemanticDataCatalog
from finchat.config.llm import get_llm_client
from finchat.data.sql_validator import SQLValidator
from finchat.evidence.evidence_object import EvidenceObject
from finchat.data.freshness import DataFreshnessContract

class DeterministicQueryEngine:
    """
    The Phase 2 Data Agent.
    Orchestrates the flow from Question -> Schema Context -> LLM SQL -> Validation -> DuckDB -> Evidence.
    """
    def __init__(self, catalog_dir: str = "context/catalog"):
        self.catalog = SemanticDataCatalog(catalog_dir)
        self.freshness = DataFreshnessContract()
        
    def _extract_sql(self, llm_response: str) -> str:
        """Extracts SQL from markdown wrappers safely."""
        match = re.search(r"```sql\n(.*?)\n```", llm_response, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return llm_response.replace('```', '').strip()

    def execute_query(self, dataset_key: str, user_question: str, as_of_date: str, provider: str = "ollama") -> EvidenceObject:
        """
        Executes the exact deterministic query pipeline.
        """
        llm = get_llm_client('sql', provider)
        
        # 1. Contextualization (Freshness + Semantics)
        if dataset_key not in self.catalog.datasets:
            raise ValueError(f"Dataset {dataset_key} not found in Semantic Catalog.")
            
        # Map dataset keys to the actual physical table names created via DuckDB Views
        dataset_to_table = {
            "stock_indicator_43metric": "stocks",
            "cme_stocks_parquet": "cme_stocks",
            "delivery_parquet": "delivery",
            "index_parquet": "index",
            "sector_index_parquet": "sector_index"
        }
        
        target_table_name = dataset_to_table.get(dataset_key, dataset_key)
        schema_prompt = self.catalog.get_table_schema_prompt(dataset_key, table_name_override=target_table_name)
        
        # Give LLM the base stocks schema too if it's not the primary one
        if dataset_key not in ["stocks_parquet", "stock_indicator_43metric"]:
            base_schema = self.catalog.get_table_schema_prompt("stock_indicator_43metric", table_name_override="stocks")
            schema_prompt += "\n\n" + base_schema
            
        freshness_context = self.freshness.get_llm_context(dataset_key)
        
        import os
        
        # Dynamically list all available parquet files to inform the LLM
        available_tables = []
        if os.path.exists('data/parquet/'):
            for f in os.listdir('data/parquet/'):
                if f.endswith('.parquet'):
                    available_tables.append(f.replace('.parquet', ''))
                    
        available_tables_str = ", ".join([f"'{t}'" for t in available_tables])
        
        # Explicit instruction to use the right table
        system_prompt = (
            "You are a deterministic SQL data agent. Your output must be ONLY valid DuckDB SQL wrapped in ```sql ... ```. "
            f"You have access to the following tables mapped from parquet files: {available_tables_str}. "
            "CRITICAL INSTRUCTION: If you need columns from multiple tables, you MUST explicitly JOIN them using `USING (symbol, date)`. "
            "Do NOT use short table aliases (like 's.' or 'cs.'). You MUST use FULL table names (like 'stocks.' or 'cme_stocks.') to prefix your columns so you do not get confused about which column belongs to which table! "
            "Do NOT invent table names like 'stock_data'. ONLY use the table names provided in 'TABLE NAME IN DATABASE'."
        )
        full_prompt = f"{system_prompt}\n\n{freshness_context}\n\n{schema_prompt}"
        
        # 2. Text-to-SQL Generation
        print(f"      [DataEngine] Asking {provider.upper()} ({llm.model_name}) to generate DuckDB SQL for dataset '{dataset_key}'...")
        import time
        s_start = time.time()
        raw_llm_response = llm.generate_sql(full_prompt, user_question)
        s_end = time.time()
        print(f"      [DataEngine] SQL Generated in {s_end - s_start:.2f} seconds.")
        print(f"      [DataEngine] Raw LLM Output:\n{raw_llm_response}\n")
        sql = self._extract_sql(raw_llm_response)
        print(f"      [DataEngine] Extracted SQL:\n{sql}\n")
        
        # 4. Static Validation & DuckDB Execution (Read-Only via View)
        query_id = f"duckdb_exec_{uuid.uuid4().hex[:8]}"
        
        import duckdb
        try:
            # 3. Static Validation (Throws error if malicious or invalid)
            SQLValidator.validate(sql)
            
            # We spin up an ephemeral memory DB and map the Parquets to Views.
            con = duckdb.connect(database=':memory:', read_only=False)
            
            import os
            if os.path.exists('data/parquet/'):
                for f in os.listdir('data/parquet/'):
                    if f.endswith('.parquet'):
                        table_name = f.replace('.parquet', '')
                        file_path = os.path.join('data/parquet', f)
                        
                        # Create a temporary view to check columns
                        con.execute(f"CREATE VIEW temp_{table_name} AS SELECT * FROM '{file_path}';")
                        cols = [c[0] for c in con.execute(f"DESCRIBE temp_{table_name}").fetchall()]
                        
                        # Standardize 'key' to 'symbol' so the LLM can always JOIN ON symbol safely
                        if 'key' in cols and 'symbol' not in cols:
                            con.execute(f"CREATE VIEW {table_name} AS SELECT *, key AS symbol FROM '{file_path}';")
                        else:
                            con.execute(f"CREATE VIEW {table_name} AS SELECT * FROM '{file_path}';")
            
            # ---------------------------------------------------------
            # 5. Execution & Self-Healing Loop
            # ---------------------------------------------------------
            max_retries = 3
            result_df = None
            
            for attempt in range(max_retries):
                try:
                    result_df = con.execute(sql).df()
                    break # Success!
                except Exception as e:
                    error_msg = str(e)
                    print(f"      [DataEngine] Execution error on attempt {attempt+1}: {error_msg}")
                    
                    # Heal 1: Wrong alias for column (e.g. s.rs_ratio_mid)
                    match_alias = re.search(r'Values list "([^"]+)" does not have a column named "([^"]+)"', error_msg)
                    if match_alias:
                        wrong_alias = match_alias.group(1)
                        col_name = match_alias.group(2)
                        print(f"      [DataEngine] Auto-healing alias error for column {col_name}")
                        # Swap alias blindly (if s -> cs, if cs -> s)
                        if wrong_alias == 's':
                            sql = re.sub(rf'\bs\.{col_name}\b', f'cs.{col_name}', sql)
                        elif wrong_alias == 'cs':
                            sql = re.sub(rf'\bcs\.{col_name}\b', f's.{col_name}', sql)
                        continue
                        
                    # Heal 2: Ambiguous column (e.g. close)
                    match_ambig = re.search(r'Ambiguous reference to column name "([^"]+)"', error_msg)
                    if match_ambig:
                        col_name = match_ambig.group(1)
                        print(f"      [DataEngine] Auto-healing ambiguous column {col_name}")
                        # Default ambiguous columns to stocks table
                        sql = re.sub(rf'(?<!\.)\b{col_name}\b', f'stocks.{col_name}', sql)
                        continue
                        
                    # If we can't heal it, re-raise to fail the pipeline
                    if attempt == max_retries - 1:
                        raise e
            
            # Bound the size of the result to prevent overflowing the LLM context
            if result_df is not None and len(result_df) > 50:
                result_df = result_df.head(50)
                
            executed_result = result_df.to_json(orient='records') if result_df is not None else "[]"
            confidence = "deterministic"
            
        except Exception as e:
            executed_result = f"DUCKDB SQL EXECUTION ERROR: {str(e)}"
            confidence = "error"
        
        # 5. Evidence Assembly
        contract = self.freshness.check_freshness(dataset_key)
        
        evidence = EvidenceObject(
            result=executed_result,
            source=f"DuckDB Engine -> data/parquet/stocks.parquet",
            as_of=as_of_date,
            query_id=query_id,
            calculation=sql,
            data_timestamp=contract.get('last_updated', datetime.now().isoformat()),
            confidence=confidence
        )
        
        return evidence

if __name__ == "__main__":
    # Test the Phase 2 Engine
    engine = DeterministicQueryEngine("../../context/catalog")
    dataset = "stock_indicator_43metric"
    question = "Show me the top 10 stocks by setup_score where RVol20 is greater than 1.5."
    as_of = "2026-09-12"
    
    print("--- Executing Deterministic Pipeline ---")
    try:
        evidence = engine.execute_query(dataset, question, as_of)
        print(evidence.to_llm_context())
    except Exception as e:
        print(f"Pipeline Failed: {e}")
