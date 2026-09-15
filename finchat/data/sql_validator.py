# -------------------------------------------------------------------
# 3AK-QuantRAG
# https://github.com/Ak-coder1/3AK-QuantRAG
# -------------------------------------------------------------------

import re

class SQLValidator:
    """
    Validates LLM-generated SQL to prevent mutation, destructive operations,
    and filesystem leaks before the query is ever passed to DuckDB.
    """
    
    FORBIDDEN_KEYWORDS = [
        "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", 
        "COPY", "ATTACH", "DETACH", "GRANT", "REVOKE", "TRUNCATE"
    ]
    
    @classmethod
    def validate(cls, sql: str) -> bool:
        """
        Performs static analysis on the SQL string. 
        Returns True if safe, raises ValueError if unsafe.
        """
        # Normalize and remove comments for checking
        clean_sql = re.sub(r'--.*$', '', sql, flags=re.MULTILINE)
        clean_sql = re.sub(r'/\*.*?\*/', '', clean_sql, flags=re.DOTALL)
        upper_sql = clean_sql.upper()
        
        # Word boundary check for forbidden keywords
        for kw in cls.FORBIDDEN_KEYWORDS:
            if re.search(rf'\b{kw}\b', upper_sql):
                raise ValueError(f"SECURITY VIOLATION: Generated SQL contains prohibited keyword '{kw}'")
                
        # Basic sanity checks to ensure it's a retrieval query
        if not upper_sql.strip().startswith("SELECT") and not upper_sql.strip().startswith("WITH"):
             raise ValueError("SECURITY VIOLATION: FinChat SQL must begin with SELECT or WITH.")
             
        return True
