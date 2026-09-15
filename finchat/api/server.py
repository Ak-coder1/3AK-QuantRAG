# -------------------------------------------------------------------
# 3AK-QuantRAG
# https://github.com/Ak-coder1/3AK-QuantRAG
# -------------------------------------------------------------------

import sys
import threading
import queue
from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
from finchat.retrieval.hybrid_search import HybridRetriever
from finchat.orchestration.agent import CopilotOrchestrator
import json

app = Flask(__name__)
CORS(app)

# Thread-local storage to capture prints per request natively
thread_local = threading.local()

class StreamCaptureStdout:
    def __init__(self, original_stdout):
        self.original_stdout = original_stdout

    def write(self, text):
        if hasattr(thread_local, 'log_queue'):
            thread_local.log_queue.put({"type": "log", "content": text})
        self.original_stdout.write(text)

    def flush(self):
        self.original_stdout.flush()

# Redirect stdout to capture prints dynamically across all modules
sys.stdout = StreamCaptureStdout(sys.stdout)

# Initialize singletons for the API
retriever = HybridRetriever()

@app.route('/api/finchat/search_docs', methods=['POST'])
def search_docs():
    data = request.get_json() or {}
    query = data.get("query")
    if not query:
        return jsonify({"error": "Missing 'query' parameter"}), 400
    evidence = retriever.retrieve(query)
    return jsonify({
        "query": query,
        "evidence": {
            "query_id": evidence.query_id,
            "results": evidence.result,
            "source": evidence.source,
            "confidence": evidence.confidence,
            "calculation": evidence.calculation,
            "as_of": evidence.as_of
        }
    })

@app.route('/api/finchat/ask', methods=['POST'])
def ask_copilot():
    data = request.get_json() or {}
    query = data.get("query")
    provider = data.get("provider", "ollama")
    
    if not query:
        return jsonify({"error": "Missing 'query' parameter"}), 400
        
    def generate():
        q = queue.Queue()
        
        def run_orchestrator():
            # Set up the thread-local queue for this specific background thread
            thread_local.log_queue = q
            try:
                orchestrator = CopilotOrchestrator()
                result = orchestrator.process_query(query, provider=provider)
                
                answer = result["answer"]
                evidence_list = result["evidence_list"]
                
                # Extract unique symbols from evidence data
                symbols = set()
                for ev in evidence_list:
                    result_data = ev.result
                    # DuckDB SQL agent returns a JSON string, so we must parse it
                    if isinstance(result_data, str):
                        try:
                            result_data = json.loads(result_data)
                        except json.JSONDecodeError:
                            pass
                            
                    if isinstance(result_data, list):
                        for row in result_data:
                            if isinstance(row, dict):
                                sym = row.get("symbol") or row.get("Symbol")
                                if sym and isinstance(sym, str):
                                    symbols.add(sym.upper())
                    elif isinstance(result_data, dict) and "active_positions" in result_data:
                        for pos in result_data["active_positions"]:
                            if isinstance(pos, dict):
                                sym = pos.get("symbol") or pos.get("Symbol")
                                if sym:
                                    symbols.add(sym.upper())
                                    
                symbols = sorted(list(symbols))
                q.put({"type": "done", "answer": answer, "symbols": symbols})
            except Exception as e:
                q.put({"type": "error", "content": str(e)})
            finally:
                if hasattr(thread_local, 'log_queue'):
                    del thread_local.log_queue

        # Start the orchestrator in a background thread
        t = threading.Thread(target=run_orchestrator)
        t.start()
        
        # Stream the results back as newline-delimited JSON
        while True:
            try:
                # Wait up to 15 seconds for an item
                item = q.get(timeout=15.0)
                yield json.dumps(item) + "\n"
                if item["type"] in ("done", "error"):
                    break
            except queue.Empty:
                # Yield a heartbeat to prevent browser/network timeouts when using slow local LLMs
                yield json.dumps({"type": "heartbeat"}) + "\n"
                
    return Response(stream_with_context(generate()), mimetype='application/x-ndjson')

if __name__ == '__main__':
    print("Starting FinChat API Gateway on port 5005...")
    app.run(host='0.0.0.0', port=5005, debug=True, threaded=True)
