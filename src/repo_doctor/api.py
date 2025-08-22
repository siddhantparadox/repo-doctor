import os
import json
import requests
from typing import Tuple, Dict, Any

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = os.getenv("REPO_DOCTOR_MODEL", "z-ai/glm-4.5")

SYSTEM_PROMPT = """You are Repo Doctor, a tight code patch generator.
Rules
1. Output one single fenced code block labeled diff that contains a unified diff. No chit chat.
2. Keep the patch minimal. Do not refactor unless needed to make tests pass.
3. Change only files that exist in the repo snapshot.
4. If a test needs adjusting because the code is correct, adjust the test with the smallest change.
5. Use correct paths relative to repo root.
6. Do not add binary files.
7. If unsure, prefer a guard clause or a clear fix with a small test.
"""

def build_user_prompt(project_name: str,
                      failure_brief: str,
                      focused_file_list: str,
                      code_slices: str) -> str:
    return f"""Project
{project_name}

Failure brief
{failure_brief}

Files in focus
{focused_file_list}

Code excerpts with line numbers
{code_slices}

Goal
Produce ONE unified diff that fixes the failing tests and keeps behavior sane.
"""

def call_glm_45(user_prompt: str,
                temperature: float = 0.0,
                max_tokens: int = 2000) -> Tuple[str, Dict[str, Any]]:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY not set")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        # Enable thinking by default and hide it in responses
        "reasoning": {"enabled": True, "exclude": True},
        # Also include Z.ai provider-specific flag for compatibility
        "thinking": {"type": "enabled"},
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    resp = requests.post(OPENROUTER_URL, headers=headers, data=json.dumps(payload), timeout=120)
    resp.raise_for_status()
    data = resp.json()

    # Collect usage including reasoning if present
    usage = data.get("usage", {})
    choice = data["choices"][0]
    message = choice["message"]
    content = message.get("content", "")

    return content, {"usage": usage, "raw": data}