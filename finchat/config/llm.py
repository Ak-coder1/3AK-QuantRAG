import json
import urllib.request
import urllib.error
from typing import List, Dict, Any, Optional

class OllamaClient:
    """
    A lightweight, local-only client for Ollama that avoids heavy external dependencies
    where possible, strictly utilizing the model specified.
    """
    def __init__(self, model_name: str = "qwen3.8:27b", base_url: str = "http://localhost:11434"):
        self.model_name = model_name
        self.base_url = base_url

    def generate_sql(self, schema_prompt: str, user_query: str) -> str:
        """
        Specialized prompt format to strictly generate DuckDB SQL using Qwen3.
        """
        system_prompt = (
            "You are an expert DuckDB SQL developer for 3AK-QuantRAG. "
            "You only return valid DuckDB SQL wrapped in ```sql ... ```. "
            "You never provide conversational text, explanations, or assumptions. "
            "Use the provided semantic schema exactly as defined."
        )
        
        prompt = f"SCHEMA:\n{schema_prompt}\n\nUSER QUERY:\n{user_query}\n\nSQL:"
        
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False,
            "options": {
                "temperature": 0.0, # Strict deterministic generation
                "top_p": 0.9
            }
        }
        
        try:
            req = urllib.request.Request(
                f"{self.base_url}/api/generate",
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode('utf-8'))
                return result.get("response", "").strip()
        except urllib.error.URLError as e:
            return f"-- ERROR: Could not connect to local Ollama at {self.base_url}. Error: {e}"
            
    def generate_completion(self, prompt: str, system_prompt: str = "You are an expert AI assistant.", temperature: float = 0.0) -> str:
        """
        General text completion endpoint for Orchestration, Planning, and Summarization.
        """
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "top_p": 0.9
            }
        }
        
        try:
            req = urllib.request.Request(
                f"{self.base_url}/api/generate",
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode('utf-8'))
                return result.get("response", "").strip()
        except urllib.error.URLError as e:
            return f"Error connecting to Ollama: {e}"

import yaml
import os

def load_settings():
    config_path = "finchat/config/settings.yaml"
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            return yaml.safe_load(f) or {}
    return {}

class GeminiClient:
    """
    Lightning-fast Cloud Inference using Google Gemini.
    """
    def __init__(self, model_name: str = "gemini-3.5-flash"):
        self.model_name = model_name
        settings = load_settings()
        self.api_key = os.environ.get("GEMINI_API_KEY") or settings.get("GEMINI_API_KEY")
        if not self.api_key:
            print("WARNING: GEMINI_API_KEY not found in env or finchat/config/settings.yaml!")

    def generate_sql(self, prompt: str, user_question: str) -> str:
        system_prompt = (
            "You are an elite SQL expert for DuckDB. Based on the provided semantic catalog schema, "
            "generate ONLY the valid DuckDB SQL query to answer the user's question. "
            "Wrap your SQL in ```sql ... ``` code blocks. Do not add any explanation."
        )
        return self.generate_completion(f"{prompt}\n\nUser Question: {user_question}", system_prompt, 0.0)

    def generate_completion(self, prompt: str, system_prompt: str = "You are an expert AI assistant.", temperature: float = 0.0) -> str:
        if not self.api_key:
            return "Error: GEMINI_API_KEY is not set in finchat/config/settings.yaml."
            
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
        
        payload = {
            "system_instruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": [
                {"parts": [{"text": prompt}]}
            ],
            "generationConfig": {
                "temperature": temperature
            }
        }
        
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode('utf-8'))
                candidates = result.get("candidates", [])
                if candidates:
                    return candidates[0]["content"]["parts"][0]["text"].strip()
                return ""
        except Exception as e:
            return f"Gemini API Error: {e}"

class ClaudeClient:
    """
    Lightning-fast Cloud Inference using Anthropic Claude.
    """
    def __init__(self, model_name: str = "claude-3-haiku-20240307"):
        self.model_name = model_name
        settings = load_settings()
        self.api_key = os.environ.get("ANTHROPIC_API_KEY") or settings.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            print("WARNING: ANTHROPIC_API_KEY not found in env or finchat/config/settings.yaml!")

    def generate_sql(self, prompt: str, user_question: str) -> str:
        system_prompt = (
            "You are an elite SQL expert for DuckDB. Based on the provided semantic catalog schema, "
            "generate ONLY the valid DuckDB SQL query to answer the user's question. "
            "Wrap your SQL in ```sql ... ``` code blocks. Do not add any explanation."
        )
        return self.generate_completion(f"{prompt}\n\nUser Question: {user_question}", system_prompt, 0.0)

    def generate_completion(self, prompt: str, system_prompt: str = "You are an expert AI assistant.", temperature: float = 0.0) -> str:
        if not self.api_key:
            return "Error: ANTHROPIC_API_KEY is not set in finchat/config/settings.yaml."
            
        url = "https://api.anthropic.com/v1/messages"
        
        payload = {
            "model": self.model_name,
            "max_tokens": 1024,
            "temperature": temperature,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }
        
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode('utf-8'),
                headers={
                    'Content-Type': 'application/json',
                    'x-api-key': self.api_key,
                    'anthropic-version': '2023-06-01'
                }
            )
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode('utf-8'))
                if "content" in result and len(result["content"]) > 0:
                    return result["content"][0]["text"].strip()
                return ""
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            return f"Anthropic API Error: {e.code} - {error_body}"
        except Exception as e:
            return f"Anthropic API Error: {e}"

class GroqClient:
    """
    Lightning-fast Cloud Inference using Groq's LPU infrastructure (LLaMA models).
    """
    def __init__(self, model_name: str = "openai/gpt-oss-20b"):
        self.model_name = model_name
        settings = load_settings()
        self.api_key = os.environ.get("GROQ_API_KEY") or settings.get("GROQ_API_KEY")
        if not self.api_key:
            print("WARNING: GROQ_API_KEY not found in env or finchat/config/settings.yaml!")

    def generate_sql(self, prompt: str, user_question: str) -> str:
        system_prompt = (
            "You are an elite SQL expert for DuckDB. Based on the provided semantic catalog schema, "
            "generate ONLY the valid DuckDB SQL query to answer the user's question. "
            "Wrap your SQL in ```sql ... ``` code blocks. Do not add any explanation."
        )
        return self.generate_completion(f"{prompt}\n\nUser Question: {user_question}", system_prompt, 0.0)

    def generate_completion(self, prompt: str, system_prompt: str = "You are an expert AI assistant.", temperature: float = 0.0) -> str:
        if not self.api_key:
            return "Error: GROQ_API_KEY is not set in finchat/config/settings.yaml."
            
        url = "https://api.groq.com/openai/v1/chat/completions"
        
        payload = {
            "model": self.model_name,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
        }
        
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode('utf-8'),
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {self.api_key}',
                    'User-Agent': 'Mozilla/5.0'
                }
            )
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode('utf-8'))
                if "choices" in result and len(result["choices"]) > 0:
                    return result["choices"][0]["message"]["content"].strip()
                return ""
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            return f"Groq API Error: {e.code} - {error_body}"
        except Exception as e:
            return f"Groq API Error: {e}"

def get_llm_client(role: str, provider: str = "ollama"):
    """
    Factory to seamlessly switch between Local Ollama, Cloud Gemini, Anthropic Claude, and Groq dynamically per request.
    role: 'router', 'sql', 'synthesis'
    provider: 'ollama', 'gemini', 'claude', 'groq'
    """
    provider = provider.lower()
    
    if provider == "gemini":
        if role == 'sql':
            return GeminiClient(model_name="gemini-3.1-pro-preview")
        else:
            return GeminiClient(model_name="gemini-3.5-flash")
    elif provider == "claude":
        if role == 'sql':
            return ClaudeClient(model_name="claude-3-5-sonnet-20241022")
        else:
            return ClaudeClient(model_name="claude-3-5-haiku-20241022")
    elif provider == "groq":
        if role == 'sql':
            return GroqClient(model_name="openai/gpt-oss-120b")
        else:
            return GroqClient(model_name="openai/gpt-oss-20b")
    else:
        # Default to local
        if role == 'sql':
            return OllamaClient(model_name="qwen3.8:27b") # Heavy weight reasoning for complex DuckDB SQL
        else:
            return OllamaClient(model_name="qwen2.5:7b") # Lightweight for fast routing/extraction

if __name__ == "__main__":
    # Smoke test to ensure Ollama is reachable
    client = OllamaClient()
    dummy_schema = "TABLE: stocks\nCOLUMNS:\n- symbol (string)\n- close (float)\n- rvol20 (float): volume / 20 day avg"
    query = "Select top 5 symbols with rvol20 greater than 2"
    print("Testing SQL Generation with Qwen...")
    print(client.generate_sql(dummy_schema, query))
