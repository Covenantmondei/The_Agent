import os
import requests
from typing import Dict, List
from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "phi")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "60"))


def check_ollama_status() -> Dict:
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        if response.status_code == 200:
            data = response.json()
            models = [model.get("name") for model in data.get("models", [])]
            
            return {
                "status": "available",
                "models": models,
                "url": OLLAMA_BASE_URL,
                "configured_model": OLLAMA_MODEL,
                "model_available": OLLAMA_MODEL in models
            }
        else:
            return {
                "status": "unavailable",
                "error": f"Status code: {response.status_code}",
                "url": OLLAMA_BASE_URL
            }
    except requests.exceptions.RequestException as e:
        return {
            "status": "unavailable",
            "error": str(e),
            "url": OLLAMA_BASE_URL
        }