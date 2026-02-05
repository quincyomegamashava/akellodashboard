import os
import json
import requests
from flask import current_app

class LLMService:
    def __init__(self):
        self.base_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434').rstrip('/')
        self.headers = {}
        authz = os.getenv('OLLAMA_AUTHORIZATION')
        api_key = os.getenv('OLLAMA_API_KEY')
        if authz:
            self.headers['Authorization'] = authz
        elif api_key:
            self.headers['Authorization'] = f'Bearer {api_key}'

    def list_models(self):
        # Try HTTP API first
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=10, headers=self.headers)
            r.raise_for_status()
            data = r.json() or {}
            models = [m.get('name') for m in data.get('models', []) if m.get('name')]
            if models:
                return models
        except Exception:
            pass
            
        # Try Python library fallback (with explicit host)
        try:
            from ollama import Client
            client = Client(host=self.base_url)
            res = client.list()
            models = [m.get('name') for m in (res.get('models') or []) if m.get('name')]
            if models:
                return models
        except Exception as e:
            # Return default list and error if possible, but for service just return defaults or raise
            current_app.logger.error(f"Failed to list models: {e}")
            
        # Final fallback
        return ['llama3.1', 'llama3', 'mistral', 'phi3', 'qwen2', 'gemma']

    def generate_chat_stream(self, model, messages, options=None, timeout=(30, None)):
        if options is None:
            options = {}
            
        resp = requests.post(f"{self.base_url}/api/chat", json={
            'model': model,
            'messages': messages,
            'stream': True,
            'options': options
        }, timeout=timeout, headers=self.headers, stream=True)
        resp.raise_for_status()
        
        return resp.iter_lines()

    def generate_chat(self, model, messages, options=None, timeout=60):
        if options is None:
            options = {}
            
        # Try streaming first for progress updates (though we consume it all here)
        # or just use non-streaming if we don't need progress
        
        content = ''
        try:
            # Try streaming first 
            resp = requests.post(f"{self.base_url}/api/chat", json={
                'model': model,
                'messages': messages,
                'stream': True,
                'options': options
            }, timeout=timeout+30, headers=self.headers, stream=True)
            resp.raise_for_status()
            
            for line in resp.iter_lines():
                if line:
                    try:
                        chunk = json.loads(line)
                        if 'message' in chunk and 'content' in chunk['message']:
                            content += chunk['message']['content']
                        elif 'response' in chunk:
                            content += chunk['response']
                    except json.JSONDecodeError:
                        continue
            return content
        except Exception as e:
            # Fallback to non-streaming
            try:
                resp2 = requests.post(f"{self.base_url}/api/chat", json={
                    'model': model,
                    'messages': messages,
                    'stream': False,
                    'options': options
                }, timeout=timeout, headers=self.headers)
                resp2.raise_for_status()
                payload = resp2.json()
                return payload.get('message', {}).get('content') or ''
            except Exception as e2:
                # Final fallback: Python library
                try:
                    from ollama import Client
                    client = Client(host=self.base_url)
                    res = client.chat(model=model, messages=messages, options=options)
                    return res.get('message', {}).get('content') or ''
                except Exception as e3:
                    raise Exception(f'Failed to generate from Ollama: {str(e3)}')
