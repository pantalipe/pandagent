"""
brain.py — Model routing and Ollama calls

Routing logic:
  - phi3               → planning, analysis, general questions
  - deepseek-coder     → code generation, debugging, file creation
"""

import json
import re
import urllib.error
import urllib.request

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_TAGS_URL = "http://localhost:11434/api/tags"


# ─────────────────────────────────────────────
# Keywords indicating a CODE task
# ─────────────────────────────────────────────
CODE_KEYWORDS = [
    # languages / tools
    "python", "solidity", "javascript", "typescript", "html", "css",
    "bash", "shell", "script", "sql", "json", "yaml", "toml",
    # code actions
    "code", "function", "class", "implement", "create file",
    "contract", "deploy", "compile", "bug", "error", "fix", "refactor",
    "install", "npm", "pip", "import", "export",
    "api", "endpoint", "route", "web3", "abi", "erc",
    "next.js", "react", "hardhat", "foundry", "truffle",
    # terminal commands
    "execute", "run", "command",
]

# ─────────────────────────────────────────────
# Keywords indicating a PLANNING task
# ─────────────────────────────────────────────
GENERAL_KEYWORDS = [
    "plan", "strategy", "architecture", "structure", "organize",
    "how does", "explain", "summarize", "analyze", "decision",
    "compare", "best way", "roadmap", "steps", "what", "when",
    "why", "difference",
]


class Brain:
    GENERAL_MODEL = "phi3"
    CODER_MODEL   = "deepseek-coder:6.7b-instruct-q4_K_M"

    # System prompts per model
    SYSTEM_PROMPTS = {
        "general": """You are PandaAgent, an assistant specialized in software planning and architecture.
Focus: Web3, DeFi, smart contracts, Python projects, and development strategy.
Be direct, objective, and respond in English.
When the task involves specific code, say: "I'll hand this off to the code module."
IMPORTANT: Always respond in plain text. NEVER use JSON, NEVER use action blocks.
""",
        "coder": """You are PandaAgent in code mode. Expert in Python, Solidity, Web3, JavaScript.

CRITICAL RULE: When the user asks to CREATE a file, you MUST respond ONLY with an action JSON. Nothing before, nothing after.

For ONE action:
{"action": "create_file", "path": "file.py", "content": "content here", "reason": "description"}

For MULTIPLE sequential actions, use a JSON list:
[
  {"action": "run_command", "command": "copy C:/Downloads/rb.py C:/project/rb.py", "reason": "copy file"},
  {"action": "run_command", "command": "python rb.py", "reason": "test"},
  {"action": "run_command", "command": "git add . && git commit -m 'update'", "reason": "commit"},
  {"action": "run_command", "command": "git push", "reason": "push"}
]

Available actions:
- create_file  → {"action": "create_file", "path": "...", "content": "...", "reason": "..."}
- run_command  → {"action": "run_command", "command": "...", "reason": "..."}
- read_file    → {"action": "read_file", "path": "...", "reason": "..."}

IMPORTANT:
- Use a JSON list when there are 2 or more actions to execute in sequence
- Put the COMPLETE code inside the "content" field
- Use \\n for line breaks inside JSON
- Only explain in text when the user asks a question, not when requesting file creation
""",
    }

    def set_project_context(self, name: str, description: str, stack: list[str]):
        """Injects project context into system prompts."""
        ctx = (
            f"\nACTIVE PROJECT: {name}\n"
            f"Description: {description}\n"
            f"Stack: {', '.join(stack)}\n"
            f"Keep all generated code compatible with this stack.\n"
        )
        for key in self.SYSTEM_PROMPTS:
            self.SYSTEM_PROMPTS[key] = self.SYSTEM_PROMPTS[key].rstrip() + ctx

    def check_ollama(self) -> bool:
        """Checks if Ollama is running."""
        try:
            req = urllib.request.Request(OLLAMA_TAGS_URL, method="GET")
            with urllib.request.urlopen(req, timeout=None) as resp:
                return resp.status == 200
        except Exception:
            return False

    def route(self, user_input: str) -> tuple[str, str]:
        """
        Decides which model to use based on message content.
        Returns: (model_name, prompt_type)
        """
        text = user_input.lower()

        code_score    = sum(1 for kw in CODE_KEYWORDS    if kw in text)
        general_score = sum(1 for kw in GENERAL_KEYWORDS if kw in text)

        # If tied or ambiguous, prefer coder (safer for mixed tasks)
        if code_score >= general_score:
            return self.CODER_MODEL, "coder"
        else:
            return self.GENERAL_MODEL, "general"



    def _call(self, model: str, prompt_type: str, prompt: str, history: list) -> str:
        """Makes the Ollama API call and returns the response."""
        system = self.SYSTEM_PROMPTS[prompt_type]

        context = system + "\n\n"
        for turn in history[-4:]:
            context += f"User: {turn['user']}\nAgent: {turn['agent']}\n\n"
        context += f"User: {prompt}\nAgent:"

        payload = {
            "model": model,
            "prompt": context,
            "stream": False,
            "options": {
                "temperature": 0.2 if prompt_type == "coder" else 0.5,
                "top_p": 0.9,
                "num_predict": 2048,
            },
        }

        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                OLLAMA_URL,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read().decode("utf-8")).get("response", "").strip()
        except urllib.error.URLError as e:
            return f"ERROR: Ollama is not running. Run: ollama serve ({e.reason})"
        except Exception as e:
            return f"Unexpected error: {e}"

    def translate_to_english(self, text: str) -> str:
        """Detects language and translates to English if needed."""
        prompt = (
            f"If the following text is already in English, return it exactly as is. "
            f"If it is in another language, translate it to English. "
            f"Return ONLY the translated or original text, nothing else.\n\n{text}"
        )
        result = self._call(self.GENERAL_MODEL, "general", prompt, [])
        return result.strip() or text

    def think(self, user_input: str, history: list) -> tuple[str, str]:
        """
        Processes input and returns (model_used, response).
        """
        model, prompt_type = self.route(user_input)

        # Routing log
        icon = "💻" if prompt_type == "coder" else "🧠"
        short_model = model.split(":")[0]
        print(f"\n{icon} Routing to: {short_model} ({prompt_type})", flush=True)

        response = self._call(model, prompt_type, user_input, history)
        return short_model, response

    def interpret_result(
        self,
        original_input: str,
        original_response: str,
        action_result: str,
        history: list,
    ) -> str:
        """
        After executing an action, interprets the result and generates a final response.
        Uses the same model that was used in the original response.
        """
        model, prompt_type = self.route(original_input)

        prompt = (
            f"Original task: {original_input}\n\n"
            f"Action executed and result:\n{action_result}\n\n"
            "Interpret the result above. If there was an error, suggest a fix. "
            "If successful, confirm and offer next steps."
        )

        return self._call(model, prompt_type, prompt, history)
