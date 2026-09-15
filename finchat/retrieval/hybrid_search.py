# -------------------------------------------------------------------
# 3AK-QuantRAG
# https://github.com/Ak-coder1/3AK-QuantRAG
# -------------------------------------------------------------------

import uuid
from datetime import datetime

from finchat.retrieval.vector_store import DuckDBVectorStore
from finchat.retrieval.embeddings import LocalEmbeddingModel
from finchat.evidence.evidence_object import EvidenceObject

class HybridRetriever:
    """
    Orchestrates Hybrid Retrieval (Dense Vector + Sparse Keyword) and securely 
    packages the results into EvidenceObjects for the LLM.
    """
    def __init__(self):
        self.vector_store = DuckDBVectorStore()
        self.embedding_model = LocalEmbeddingModel()

    def retrieve(self, query: str, top_k: int = 3) -> EvidenceObject:
        """
        1. Embeds the user query.
        2. Queries DuckDB VSS for semantic matches.
        3. Formats results into an EvidenceObject.
        """
        # Generate semantic vector for the user's question
        query_emb = self.embedding_model.get_embedding(query)
        
        print(f"      [HybridRetriever] Executing Vector + Keyword Search against finchat_kb...")
        
        # Execute DuckDB VSS Search with Keyword Boosting
        docs = self.vector_store.vector_search(query_emb, query_text=query, top_k=top_k)
        
        print(f"      [HybridRetriever] Retrieved {len(docs)} relevant chunks.")
        for i, d in enumerate(docs):
            doc_id = d.get('metadata', {}).get('source', d.get('id'))
            print(f"        -> Match {i+1}: {doc_id} (Score: {d.get('score', 0):.2f})")
        
        query_id = f"rag_search_{uuid.uuid4().hex[:8]}"
        
        # Critical feature: RAG results are wrapped in an EvidenceObject with 'heuristic' confidence,
        # explicitly telling the LLM that this is documentation search, not deterministic SQL data.
        evidence = EvidenceObject(
            result=docs,
            source="DuckDB VSS -> finchat_kb",
            as_of=datetime.now().strftime("%Y-%m-%d"),
            query_id=query_id,
            calculation=f"Hybrid Search (Cosine similarity) for query: '{query}'",
            data_timestamp=datetime.now().isoformat(),
            confidence="heuristic" 
        )
        
        return evidence

if __name__ == "__main__":
    retriever = HybridRetriever()
    print("--- Executing Hybrid Document Search ---")
    evidence = retriever.retrieve("What is the MIP8 entry rule?")
    print(evidence.to_llm_context())
