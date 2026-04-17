"""
panda_client.py — Shared Ollama client for the PandaEcosystem

Single point of contact with Ollama.
Import this module from any project instead of calling Ollama directly.

Usage:
    from panda_client import PandaClient

    client = PandaClient()
    response = client.ask("Explain this diff", task="code")
    response = client.ask("Write a summary", task="text")
    response = client.ask("Any prompt")  # auto-routes based on content

Importable from other projects:
    import sys
    sys.path.insert(0, "C:/Users/panta/pandagent")
    from panda_client import PandaClient
"""

import json
import re
import urllib.error
import urllib.request

# ─────────────────────────────────────────────
# DEFAULTS
# ─────────────────────────────────────────────
OLLAMA_BASE_URL    = "http://localhost:11434"
DEFAULT_TEXT_MODEL = "phi3"
DEFAULT_CODE_MODEL = "deepseek-coder:6.7b-instruct-q4_K_M"

# Keywords that signal a CODE task
_CODE_KEYWORDS = [
    "python", "solidity", "javascript", "typescript", "html", "css",
    "bash", "shell", "script", "sql", "json", "yaml", "toml",
    "code", "function", "class", "implement", "create file",
    "contract", "deploy", "compile", "bug", "error", "fix", "refactor",
    "install", "npm", "pip", "import", "export",
    "api", "endpoint", "route", "web3", "abi", "erc",
    "next.js", "react", "hardhat", "foundry", "truffle",
    "execute", "run", "command",
]

# Phrases the model might leak from the prompt into its response.
# Anything from here onward gets stripped from commit message output.
_COMMIT_LEAK_MARKERS = [
    "developer context:",
    "generate the commit message",
    "git status:",
    "git diff:",
    "no diff available",
    "reply only",
]


class PandaClient:
    """
    Lightweight Ollama client with model routing.

    Parameters
    ----------
    text_model : str
        Model used for planning, analysis and text generation (default: phi3).
    code_model : str
        Model used for code generation and debugging (default: deepseek-coder).
    base_url : str
        Ollama base URL (default: http://localhost:11434).
    """

    def __init__(
        self,
        text_model: str = DEFAULT_TEXT_MODEL,
        code_model: str = DEFAULT_CODE_MODEL,
        base_url: str = OLLAMA_BASE_URL,
    ):
        self.text_model = text_model
        self.code_model = code_model
        self._generate_url = f"{base_url}/api/generate"
        self._tags_url     = f"{base_url}/api/tags"

    # ─────────────────────────────────────────────
    # PUBLIC API
    # ─────────────────────────────────────────────

    def is_online(self) -> bool:
        """Returns True if Ollama is reachable."""
        try:
            req = urllib.request.Request(self._tags_url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except Exception:
            return False

    def available_models(self) -> list[str]:
        """Returns list of models currently installed in Ollama."""
        try:
            req = urllib.request.Request(self._tags_url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []

    def ask(
        self,
        prompt: str,
        task: str = "auto",
        system: str = "",
        context: str = "",
        temperature: float | None = None,
        max_tokens: int = 2048,
        stream: bool = False,
    ) -> dict:
        """
        Send a prompt to Ollama and return the response.

        Parameters
        ----------
        prompt : str
            The user prompt.
        task : str
            "auto"  → route based on prompt content (default)
            "text"  → force text/planning model (phi3)
            "code"  → force code model (deepseek-coder)
        system : str
            Optional system prompt injected before the user prompt.
        context : str
            Optional extra context appended after the system prompt and before
            the user prompt (e.g. git diff, file contents, project description).
        temperature : float | None
            Override temperature. Defaults: 0.5 for text, 0.2 for code.
        max_tokens : int
            Max tokens to generate (default: 2048).
        stream : bool
            Whether to use streaming (default: False).

        Returns
        -------
        dict
            {
                "ok": bool,
                "output": str,       # the model response or error message
                "model": str,        # model that was used
                "task": str,         # "text" or "code"
            }
        """
        model, resolved_task = self._resolve(prompt, task)

        if temperature is None:
            temperature = 0.2 if resolved_task == "code" else 0.5

        full_prompt = self._build_prompt(prompt, system, context)

        payload = {
            "model":  model,
            "prompt": full_prompt,
            "stream": stream,
            "options": {
                "temperature": temperature,
                "top_p":       0.9,
                "num_predict": max_tokens,
            },
        }

        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                self._generate_url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=None) as resp:
                result   = json.loads(resp.read().decode("utf-8"))
                response = result.get("response", "").strip()
                if not response:
                    return self._err("Ollama returned an empty response.", model, resolved_task)
                return {"ok": True, "output": response, "model": model, "task": resolved_task}

        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode("utf-8")
            except Exception:
                pass
            return self._err(f"Ollama HTTP {e.code}: {e.reason}. {detail}".strip(), model, resolved_task)
        except urllib.error.URLError as e:
            return self._err(f"Ollama not reachable: {e.reason}", model, resolved_task)
        except Exception as e:
            return self._err(f"Unexpected error: {e}", model, resolved_task)

    # ─────────────────────────────────────────────
    # CONVENIENCE SHORTCUTS
    # ─────────────────────────────────────────────

    def commit_message(self, diff: str, status: str = "", extra_context: str = "") -> dict:
        """
        Generate a conventional commit message from a git diff.

        Parameters
        ----------
        diff : str
            Output of `git diff` or `git diff --cached`.
        status : str
            Output of `git status --short` (optional, improves quality).
        extra_context : str
            Any additional context from the developer (optional).

        Returns
        -------
        dict  →  {"ok": bool, "output": str, "model": str, "task": str}
        """
        # Build context block — kept separate from the instruction
        context_parts = []
        if status.strip():
            context_parts.append(f"### git status\n{status.strip()}")
        if diff.strip():
            context_parts.append(f"### git diff\n{diff.strip()[:3000]}")
        if extra_context.strip():
            context_parts.append(f"### notes from developer\n{extra_context.strip()}")

        context = "\n\n".join(context_parts) if context_parts else "(no diff available)"

        # Tighter system prompt — explicit stop condition
        system = (
            "You are a git commit message generator.\n"
            "Rules:\n"
            "1. Output ONE single line following Conventional Commits: "
            "<type>(<scope>): <description>\n"
            "   Valid types: feat, fix, refactor, docs, chore, test, style, perf\n"
            "2. The line must be under 72 characters.\n"
            "3. Write NOTHING else — no body, no footer, no explanation, "
            "no bullet points, no markdown, no quotes.\n"
            "4. Stop after the first line. Do not continue writing."
        )

        result = self.ask(
            prompt="Commit message:",
            task="text",
            system=system,
            context=context,
            temperature=0.2,
            max_tokens=80,  # Hard cap — a commit subject is never more than ~72 chars
        )

        if result["ok"]:
            result["output"] = self._clean_commit(result["output"])
            if not result["output"]:
                return self._err("Model returned an empty commit message after cleanup.", result["model"], result["task"])

        return result

    def generate_readme(
        self,
        project_name: str,
        description: str = "",
        objective: str = "",
        stack: list[str] | None = None,
        status: str = "",
        file_structure: str = "",
        project_context: str = "",
    ) -> dict:
        """
        Generate a README.md in English for a project.

        Parameters
        ----------
        project_name : str
            Name of the project.
        description : str
            Short description.
        objective : str
            What the project is trying to achieve.
        stack : list[str]
            Technologies used.
        status : str
            Development status.
        file_structure : str
            File tree as a string (from scan_project_structure or similar).
        project_context : str
            Any additional context (package.json contents, etc).

        Returns
        -------
        dict  →  {"ok": bool, "output": str, "model": str, "task": str}
        """
        stack_str = ", ".join(stack or [])

        context_parts = [
            f"Project name: {project_name}",
            f"Description: {description}" if description else "",
            f"Objective: {objective}"     if objective    else "",
            f"Stack: {stack_str}"         if stack_str    else "",
            f"Status: {status}"           if status       else "",
        ]
        if file_structure.strip():
            context_parts.append(f"\nFile structure:\n{file_structure.strip()}")
        if project_context.strip():
            context_parts.append(f"\nAdditional context:\n{project_context.strip()[:800]}")

        context = "\n".join(p for p in context_parts if p)

        system = (
            "You are a technical writer. "
            "Generate a clean and professional README.md in English for the project described below. "
            "Use markdown. Include: project name, short description, what it does, main features, "
            "stack, how to run (if inferable), and project structure. "
            "Do NOT include a license section. Keep it concise and developer-focused. "
            "IMPORTANT: Output raw markdown only. "
            "Do NOT wrap the output in ```markdown fences or any other code block. "
            "Start directly with # ProjectName."
        )

        result = self.ask(
            prompt="Generate the README.md for the project above.",
            task="text",
            system=system,
            context=context,
            temperature=0.4,
            max_tokens=2048,
        )

        if result["ok"]:
            result["output"] = self._clean_markdown_fences(result["output"])

        return result

    def generate_script(
        self,
        topic: str,
        persona: str = "",
        duration_seconds: int = 60,
        language: str = "pt-BR",
    ) -> dict:
        """
        Generate a short-form video script (for rotman).

        Parameters
        ----------
        topic : str
            The video topic.
        persona : str
            Channel persona instructions (from persona_bitcoinfacil.txt, etc).
        duration_seconds : int
            Target video duration in seconds (default: 60).
        language : str
            Output language (default: pt-BR).

        Returns
        -------
        dict  →  {"ok": bool, "output": str, "model": str, "task": str}
        """
        context_parts = [f"Topic: {topic}"]
        if persona.strip():
            context_parts.append(f"Channel persona:\n{persona.strip()}")
        context_parts.append(
            f"Target duration: ~{duration_seconds} seconds. "
            f"Output language: {language}."
        )

        system = (
            "You are a short-form video scriptwriter. "
            "Write an engaging, conversational script for the topic below. "
            "Structure: hook (5s) → main content → CTA. "
            "Keep it natural for text-to-speech narration. "
            "Reply ONLY with the script text — no stage directions, no scene headers, no formatting."
        )

        return self.ask(
            prompt="Write the video script for the topic above.",
            task="text",
            system=system,
            context="\n".join(context_parts),
            temperature=0.7,
            max_tokens=1024,
        )

    # ─────────────────────────────────────────────
    # OUTPUT CLEANERS
    # ─────────────────────────────────────────────

    @staticmethod
    def _clean_commit(raw: str) -> str:
        """
        Extracts the conventional commit subject line from model output.

        Strategy:
        1. Split into lines, take the first non-empty one.
        2. Strip markdown formatting (bold, backticks, quotes).
        3. Cut anything after a known prompt-leak marker.
        4. Validate it looks like a conventional commit; if not, return as-is
           (better than returning empty).
        """
        if not raw:
            return ""

        lines = [l.strip() for l in raw.strip().splitlines() if l.strip()]
        if not lines:
            return ""

        # Pick the first line that looks like a conventional commit
        # (starts with a known type keyword)
        conventional_types = (
            "feat", "fix", "refactor", "docs", "chore",
            "test", "style", "perf", "build", "ci",
        )
        candidate = lines[0]
        for line in lines:
            if any(line.lower().startswith(t) for t in conventional_types):
                candidate = line
                break

        # Strip markdown formatting artifacts
        candidate = candidate.strip("`*\"'")

        # Cut at any prompt-leak marker (case-insensitive)
        lower = candidate.lower()
        for marker in _COMMIT_LEAK_MARKERS:
            idx = lower.find(marker)
            if idx != -1:
                candidate = candidate[:idx].strip()
                break

        # Strip trailing punctuation that doesn't belong
        candidate = candidate.rstrip(".,;:")

        return candidate.strip()

    @staticmethod
    def _clean_markdown_fences(raw: str) -> str:
        """
        Removes wrapping ```markdown ... ``` or ``` ... ``` fences
        that models sometimes add despite being told not to.
        Also strips a leading 'markdown' word if the model just output that.
        """
        text = raw.strip()

        # Remove opening ```markdown or ```
        text = re.sub(r"^```(?:markdown)?\s*\n?", "", text, flags=re.IGNORECASE)

        # Remove closing ```
        text = re.sub(r"\n?```\s*$", "", text)

        # If the whole thing starts with just the word "markdown" on its own line
        text = re.sub(r"^markdown\s*\n", "", text, flags=re.IGNORECASE)

        return text.strip()

    # ─────────────────────────────────────────────
    # INTERNAL HELPERS
    # ─────────────────────────────────────────────

    def _resolve(self, prompt: str, task: str) -> tuple[str, str]:
        """Resolves which model and task type to use."""
        if task == "code":
            return self.code_model, "code"
        if task == "text":
            return self.text_model, "text"
        # Auto-route
        score = sum(1 for kw in _CODE_KEYWORDS if kw in prompt.lower())
        if score >= 2:
            return self.code_model, "code"
        return self.text_model, "text"

    def _build_prompt(self, prompt: str, system: str, context: str) -> str:
        """Assembles the final prompt string."""
        parts = []
        if system.strip():
            parts.append(system.strip())
        if context.strip():
            parts.append(context.strip())
        parts.append(prompt.strip())
        return "\n\n".join(parts)

    @staticmethod
    def _err(message: str, model: str, task: str) -> dict:
        return {"ok": False, "output": message, "model": model, "task": task}
