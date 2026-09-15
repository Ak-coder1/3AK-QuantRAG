import json
import urllib.request
from typing import List

class LocalEmbeddingModel:
    """
    Wrapper for local embedding generation.
    Connects to the local Ollama instance's /api/embeddings endpoint.
    By default, configured for high-quality semantic models like BAAI/bge-m3 or mxbai-embed-large.
    """
    def __init__(self, model_name: str = "bge-m3", base_url: str = "http://localhost:11434"):
        self.model_name = model_name
        self.base_url = base_url

    def get_embedding(self, text: str) -> List[float]:
        payload = {
            "model": self.model_name,
            "prompt": text
        }
        try:
            req = urllib.request.Request(
                f"{self.base_url}/api/embeddings",
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode('utf-8'))
                return result.get("embedding", [])
        except Exception as e:
            print(f"Embedding Generation Failed: {e}")
            return []

if __name__ == "__main__":
    import sys
    
    # Using the bge-m3 model as specified in the design doc
    test_model = "bge-m3" 
    
    print(f"Testing Local Ollama Embeddings using model: '{test_model}'...")
    
    client = LocalEmbeddingModel(model_name=test_model)
    
    test_text = "What are the rules for the MIP8 trading strategy?"
    print(f"\nGenerating embedding for text: '{test_text}'")
    
    vector = client.get_embedding(test_text)
    
    if vector:
        print(f"\nSuccess! Generated vector with dimension: {len(vector)}")
        print(f"First 5 dimensions: {vector[:5]}")
    else:
        print("\nFailed to generate embedding. Make sure Ollama is running and the model is pulled.")
