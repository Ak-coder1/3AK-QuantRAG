# -------------------------------------------------------------------
# 3AK-QuantRAG
# https://github.com/Ak-coder1/3AK-QuantRAG
# -------------------------------------------------------------------

import duckdb
from typing import List, Dict, Any

class DuckDBVectorStore:
    """
    Manages the Knowledge RAG vector store natively using DuckDB VSS.
    Eliminates the need for external vector databases (Chroma/LanceDB),
    consolidating the analytical and document layers onto the same engine.
    """
    def __init__(self, db_path: str = "finchat/data/finchat_kb.duckdb", embedding_dim: int = 1024):
        self.db_path = db_path
        self.embedding_dim = embedding_dim
        # We lazily initialize to avoid locking during import, but will connect on first use
        self.conn = None

    def _connect(self):
        if not self.conn:
            self.conn = duckdb.connect(self.db_path)
            self._initialize_extensions()
            self._create_tables()

    def _initialize_extensions(self):
        """Install and load required DuckDB extensions for Hybrid RAG."""
        try:
            self.conn.execute("INSTALL vss;")
            self.conn.execute("LOAD vss;")
        except duckdb.Error as e:
            print(f"[VectorStore] WARNING: VSS extension failed to load. Vector similarity may fallback to slower native array functions. Error: {e}")

    def _create_tables(self):
        """
        Creates the document table with array support for embeddings.
        """
        self.conn.execute(f"""
            CREATE TABLE IF NOT EXISTS kb_docs (
                id VARCHAR PRIMARY KEY,
                content TEXT,
                metadata JSON,
                embedding FLOAT[{self.embedding_dim}]
            );
        """)

    def add_documents(self, documents: List[Dict[str, Any]]):
        """
        Inserts chunks and their embeddings into the store.
        documents should be a list of dicts: {"id": str, "content": str, "metadata": dict, "embedding": List[float]}
        """
        self._connect()
        # Use executemany for bulk insertion
        insert_data = []
        for doc in documents:
            import json as json_lib
            insert_data.append((
                doc["id"], 
                doc["content"], 
                json_lib.dumps(doc.get("metadata", {})), 
                doc["embedding"]
            ))
            
        self.conn.executemany("""
            INSERT INTO kb_docs (id, content, metadata, embedding) 
            VALUES (?, ?, ?, ?)
            ON CONFLICT (id) DO UPDATE SET 
                content = excluded.content,
                metadata = excluded.metadata,
                embedding = excluded.embedding;
        """, insert_data)

    def vector_search(self, query_embedding: List[float], query_text: str = "", top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Performs an exact or approximate nearest neighbor search.
        If query_text is provided, extracts uppercase acronyms and boosts their score via ILIKE.
        """
        self._connect()
        import json as json_lib
        import re
        
        # Extract uppercase keywords/acronyms like SVRO, MIP8, VCP
        keywords = re.findall(r'\b[A-Z0-9]{3,}\b', query_text)
        
        keyword_boost_sql = ""
        if keywords:
            # Create a CASE WHEN for each keyword to boost the semantic score
            boosts = []
            for kw in keywords:
                boosts.append(f"CASE WHEN content ILIKE '%{kw}%' THEN 0.2 ELSE 0.0 END")
            keyword_boost_sql = " + " + " + ".join(boosts)
        
        # We use array_cosine_similarity (higher is better, range -1 to 1)
        res = self.conn.execute(f"""
            SELECT id, content, metadata, 
                   array_cosine_similarity(embedding, $1::FLOAT[{self.embedding_dim}]) {keyword_boost_sql} as score
            FROM kb_docs 
            WHERE embedding IS NOT NULL
            ORDER BY score DESC 
            LIMIT ?
        """, [query_embedding, top_k]).fetchall()
        
        results = []
        for row in res:
            results.append({
                "id": row[0],
                "content": row[1],
                "metadata": json_lib.loads(row[2]) if row[2] else {},
                "score": float(row[3]) if row[3] else 0.0
            })
            
        return results
