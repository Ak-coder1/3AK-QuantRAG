# -------------------------------------------------------------------
# 3AK-QuantRAG
# https://github.com/Ak-coder1/3AK-QuantRAG
# -------------------------------------------------------------------

from finchat.config.llm import get_llm_client

class IntentRouter:
    """
    Phase 4 Orchestration: Determines the semantic category of the user's question
    so the system can dispatch it to the correct deterministic pipeline.
    """
    def __init__(self):
        pass

    def route_query(self, query: str, provider: str = "ollama") -> str:
        """
        Valid Returns: 'knowledge', 'data', 'analytical', 'hybrid', 'live_api', 'adversarial'
        """
        llm = get_llm_client('router', provider)
        
        system_prompt = (
            "You are the routing engine for a high-stakes financial Copilot. "
            "Classify the user's query into exactly ONE of the following categories:\n"
            "- knowledge: Questions about documentation, strategy definitions, or concepts.\n"
            "- data: Simple factual lookups (e.g., historical price, specific metrics).\n"
            "- analytical: Complex queries requiring aggregations, counts, or statistics.\n"
            "- hybrid: Questions requiring both strategy rule lookups AND data evaluation (e.g., 'Did X satisfy strategy Y?').\n"
            "- live_api: Questions about current operational state, live broker connection, or portfolio.\n"
            "- adversarial: Requests to execute arbitrary code, modify data, drop tables, or place trades.\n\n"
            "Return ONLY the exact category string in lowercase with no punctuation or explanation."
        )
        
        prompt = f"User Query: '{query}'"
        print(f"      [Router] Asking {provider.upper()} ({llm.model_name}) to classify intent...")
        
        import time
        r_start = time.time()
        category = llm.generate_completion(prompt=prompt, system_prompt=system_prompt, temperature=0.0)
        r_end = time.time()
        print(f"      [Router] Intent classified in {r_end - r_start:.2f} seconds.")
        print(f"      [Router] Raw LLM Output: '{category}'")
        
        # Fallback sanitize
        clean_cat = category.strip().lower()
        valid_categories = ['knowledge', 'data', 'analytical', 'hybrid', 'live_api', 'adversarial']
        
        # More robust parsing: look for the keyword in the response in case the 7B model is chatty
        for valid_cat in valid_categories:
            if valid_cat in clean_cat:
                return valid_cat
                
        print(f"      [Router Warning] Unrecognized intent output: '{category}' -> Defaulting to adversarial block.")
        return "adversarial" # Default to safest path if LLM fails

if __name__ == "__main__":
    router = IntentRouter()
    test_queries = [
        "What is the SVRO entry rule?",
        "What was RELIANCE's close yesterday?",
        "Did TCS qualify for SVRO?",
        "Drop the stocks table."
    ]
    print("--- Testing Intent Router ---")
    for q in test_queries:
        print(f"Query: '{q}' -> Route: {router.route_query(q)}")
