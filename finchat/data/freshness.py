from typing import Dict, Any

import os
import duckdb

class DataFreshnessContract:
    """
    Enforces temporal awareness by dynamically querying the underlying parquet files 
    for their max date. Prevents look-ahead bias and silent staleness.
    """
    def __init__(self):
        self.contracts = {
            "stock_indicator_43metric": {
                "source": "stocks.parquet",
                "date_column": "Date",
                "frequency": "daily",
                "status": "healthy"
            },
            "stock_earnings_dates_master": {
                "source": "earnings.parquet",
                "date_column": "Date",
                "frequency": "daily",
                "status": "healthy"
            },
            "options_flow": {
                "source": "delivery.parquet",
                "date_column": "Date",
                "frequency": "daily",
                "status": "healthy"
            },
            "macro": {
                "source": "index.parquet",
                "date_column": "Date",
                "frequency": "daily",
                "status": "healthy"
            }
        }

    def check_freshness(self, dataset_key: str) -> Dict[str, Any]:
        """Returns the raw freshness contract for a given dataset."""
        contract = self.contracts.get(dataset_key)
        if not contract:
            return {"status": "unknown"}
            
        parquet_path = f"data/parquet/{contract['source']}"
        if not os.path.exists(parquet_path):
            contract["status"] = "missing_file"
            contract["data_through"] = "UNKNOWN"
            return contract

        try:
            con = duckdb.connect(':memory:')
            res = con.execute(f"SELECT MAX({contract['date_column']}) FROM '{parquet_path}'").fetchone()
            
            if res and res[0]:
                contract["data_through"] = str(res[0]).split()[0]
            else:
                contract["data_through"] = "UNKNOWN"
        except Exception as e:
            print(f"[Freshness] Error dynamically checking {parquet_path}: {e}")
            contract["status"] = "error"
            contract["data_through"] = "UNKNOWN"

        return contract
        
    def get_llm_context(self, dataset_key: str) -> str:
        """Formats the freshness contract as a strict directive for the LLM."""
        contract = self.check_freshness(dataset_key)
        if contract['status'] == 'unknown':
            return f"[WARNING: Freshness for dataset '{dataset_key}' is unknown. Treat with caution.]"
            
        return (f"[FRESHNESS CONTRACT for '{dataset_key}']: "
                f"Data is strictly valid through {contract['data_through']}. "
                f"Do not attempt to answer questions about dates after {contract['data_through']} using this dataset.")

if __name__ == "__main__":
    contract_mgr = DataFreshnessContract()
    print(contract_mgr.get_llm_context("stocks"))
