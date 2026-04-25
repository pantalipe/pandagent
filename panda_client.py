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

# -------------------------------------------------
# DEFAULTS
# -------------------------------------------------
OLLAMA_BASE_URL    = "http://localhost:11434"
DEFAULT_TEXT_MODEL = "phi3"
DEFAULT_CODE_MODEL = "deepseek-coder:6.7b-instruct-q4_K_M"

# -------------------------------------------------
# TASK → MODEL ROUTING MAP
# Derived from ollama-bench results (2026-04-25).
# Keys match task/channel identifiers used across the ecosystem.
# Override at runtime by passing model= to ask() directly.
# -------------------------------------------------
TASK_MODEL_MAP: dict[str, str] = {
    # commit messages — deepseek is most consistent (0.67 on complex diff)
    "commit":            "deepseek-coder:6.7b-instruct-q4_K_M",
    # code generation — phi3 fastest + consistency 1.0 on Solidity
    "code_python":       "phi3",
    "code_solidity":     "phi3",
    # README / generic text — phi3 fastest, quality acceptable
    "readme":            "phi3",
    # short-form video scripts by channel
    "script_bitcoinfacil": "llama3.1:8b",   # pt-BR hooks — llama best quality
    "script_pandapoints":  "mistral:7b",    # EN hooks  — mistral most consistent
}

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

# Phrases/patterns that signal the model leaked prompt content into the output.
# Matched case-insensitively. Anything from the match onward gets stripped.
_COMMIT_LEAK_MARKERS = [
    "developer notes:",
    "developer context:",
    "project context:",
    "generate the commit message",
    "git status:",
    "git diff:",
    "no diff available",
    "reply only",
    "status:",
    "stack:",
    "objective:",
    "description:",
    ". prepared to",
    ". status:",
    ". stack:",
    " #",        # issue/PR references like #123 or #abc
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

    # -------------------------------------------------
    # PUBLIC API
    # -------------------------------------------------

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
            "auto"  -> route based on prompt content (default)
            "text"  -> force text/planning model (phi3)
            "code"  -> force code model (deepseek-coder)
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

    # -------------------------------------------------
    # CONVENIENCE SHORTCUTS
    # -------------------------------------------------

    def commit_message(
        self,
        diff: str,
        status: str = "",
        extra_context: str = "",
        project_name: str = "",
    ) -> dict:
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
        project_name : str
            The project name to use as the commit scope (optional).

        Returns
        -------
        dict  ->  {"ok": bool, "output": str, "model": str, "task": str}
        """
        context_parts = []
        if status.strip():
            context_parts.append(f"### git status\n{status.strip()}")
        if diff.strip():
            context_parts.append(f"### git diff\n{diff.strip()[:3000]}")
        if extra_context.strip():
            context_parts.append(f"### background info (DO NOT copy into output)\n{extra_context.strip()}")

        context = "\n\n".join(context_parts) if context_parts else "(no diff available)"

        scope_rule = (
            f"   Use '{project_name}' as the scope, e.g. feat({project_name}): ...\n"
            if project_name else
            "   Infer the scope from the diff (module, file area or feature name).\n"
        )

        system = (
            "You are a git commit message generator.\n"
            "Rules:\n"
            "1. Output ONE single line following Conventional Commits: "
            "<type>(<scope>): <description>\n"
            "   Valid types: feat, fix, refactor, docs, chore, test, style, perf\n"
            f"{scope_rule}"
            "2. Write NOTHING else -- no body, no footer, no explanation, "
            "no issue references (#), no metadata.\n"
            "3. The background info section is for context only -- "
            "do NOT reproduce any of it in the output.\n"
            "4. Stop immediately after the commit subject line."
        )

        result = self.ask(
            prompt="Commit message:",
            task="text",
            system=system,
            context=context,
            temperature=0.2,
            max_tokens=200,
        )

        if result["ok"]:
            result["output"] = self._clean_commit(result["output"])
            if not result["output"]:
                return self._err(
                    "Model returned an empty commit message after cleanup.",
                    result["model"], result["task"],
                )

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
        """Generate a README.md in English for a project."""
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
            task="text", system=system, context=context, temperature=0.4, max_tokens=2048,
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
        channel: str = "",
    ) -> dict:
        """
        Generate a short-form video script (for rotman).

        Parameters
        ----------
        channel : str
            Optional channel identifier used for model routing via TASK_MODEL_MAP.
            Accepted values: "bitcoinfacil" (pt-BR), "pandapoints" (en).
            When provided, overrides the default text model for this call.
            If omitted, falls back to DEFAULT_TEXT_MODEL.
        """
        # Resolve model from channel if provided
        task_key = f"script_{channel.lower().replace('-', '')}" if channel else ""
        model = TASK_MODEL_MAP.get(task_key, self.text_model)

        # Auto-set language from channel if caller didn't override the default
        if channel.lower() in ("bitcoinfacil",) and language == "pt-BR":
            language = "pt-BR"
        elif channel.lower() in ("pandapoints",) and language == "pt-BR":
            language = "en"

        context_parts = [f"Topic: {topic}"]
        if persona.strip():
            context_parts.append(f"Channel persona:\n{persona.strip()}")
        context_parts.append(f"Target duration: ~{duration_seconds} seconds. Output language: {language}.")
        system = (
            "You are a short-form video scriptwriter. "
            "Write an engaging, conversational script for the topic below. "
            "Structure: hook (5s) -> main content -> CTA. "
            "Keep it natural for text-to-speech narration. "
            "Reply ONLY with the script text -- no stage directions, no scene headers, no formatting."
        )
        result = self.ask(
            prompt="Write the video script for the topic above.",
            task="text", system=system, context="\n".join(context_parts),
            temperature=0.7, max_tokens=1024,
        )
        # Stamp which model was actually used for script routing
        result["routed_via"] = task_key or "default"
        result["model"] = model
        return result

    def generate_hardhat_test(
        self,
        function_name: str,
        abi_entry: dict,
        contract_name: str = "PandaPoints",
        contract_context: str = "",
    ) -> dict:
        """
        Generate a Hardhat/ethers.js test scaffold for a single contract function.

        Parameters
        ----------
        function_name : str
            The name of the function to test (e.g. "buyTokens").
        abi_entry : dict
            The ABI entry for that function (parsed from abi.json).
        contract_name : str
            The Solidity contract name used in the test description (default: "PandaPoints").
        contract_context : str
            Optional extra context about the contract behaviour to guide generation.

        Returns
        -------
        dict  ->  {"ok": bool, "output": str, "model": str, "task": str}

        Notes
        -----
        - Output is a standalone Hardhat test file using ethers.js v6 syntax.
        - The file can be saved directly to test/generated/<functionName>.test.js.
        - Uses deepseek-coder (code model) with temperature 0.2 for deterministic output.
        """
        abi_json  = json.dumps(abi_entry, indent=2)
        state_mut = abi_entry.get("stateMutability", "nonpayable")
        inputs    = abi_entry.get("inputs", [])
        outputs   = abi_entry.get("outputs", [])

        inputs_desc  = ", ".join(f"{i['name']} ({i['type']})" for i in inputs)  if inputs  else "none"
        outputs_desc = ", ".join(f"{o['name']} ({o['type']})" for o in outputs) if outputs else "none"

        context_parts = [
            f"Contract: {contract_name}",
            f"Function to test: {function_name}",
            f"stateMutability: {state_mut}",
            f"Inputs: {inputs_desc}",
            f"Outputs: {outputs_desc}",
            f"\nABI entry:\n{abi_json}",
        ]
        if contract_context.strip():
            context_parts.append(f"\nContract context:\n{contract_context.strip()}")

        context = "\n".join(context_parts)

        system = (
            "You are a Solidity smart contract test engineer.\n"
            "Generate a complete, runnable Hardhat test file in JavaScript for the function described below.\n\n"
            "Rules:\n"
            "1. Use ethers.js v6 syntax (e.g. ethers.parseEther, signer.getAddress, contract.connect).\n"
            "2. Import loadFixture EXACTLY like this:\n"
            '   const { loadFixture } = require("@nomicfoundation/hardhat-network-helpers");\n'
            "   Do NOT use @nomiclabs/hardhat-waffle or any waffle import -- it does not exist in this project.\n"
            "3. The fixture must deploy the contract using ethers.getContractFactory.\n"
            "   Since the contract has a constructor with no arguments, use: await factory.deploy();\n"
            "4. Include at least 3 test cases: happy path, edge case, and revert/failure case.\n"
            "5. Use descriptive it() labels that explain what is being asserted.\n"
            "6. For payable functions, send value using { value: ethers.parseEther('1.0') }.\n"
            "7. For view/pure functions, assert the return value with expect().\n"
            "8. Do NOT import the ABI from an external file -- use ethers.getContractFactory with the contract name.\n"
            "9. Output ONLY the JavaScript file content. No markdown fences, no explanation.\n"
            '10. The very first line of the file must be exactly: "use strict";'
        )

        result = self.ask(
            prompt=f"Generate the Hardhat test file for the '{function_name}' function.",
            task="code",
            system=system,
            context=context,
            temperature=0.2,
            max_tokens=2048,
        )

        if result["ok"]:
            result["output"] = self._clean_markdown_fences(result["output"])

        return result

    # -------------------------------------------------
    # OUTPUT CLEANERS
    # -------------------------------------------------

    @staticmethod
    def _clean_commit(raw: str) -> str:
        """
        Extracts a clean conventional commit subject line from model output.
        Takes the first line that starts with a conventional type,
        strips artifacts and leak markers. No length truncation.
        """
        if not raw:
            return ""

        lines = [l.strip() for l in raw.strip().splitlines() if l.strip()]
        if not lines:
            return ""

        conventional_types = (
            "feat", "fix", "refactor", "docs", "chore",
            "test", "style", "perf", "build", "ci",
        )
        candidate = lines[0]
        for line in lines:
            if any(line.lower().startswith(t) for t in conventional_types):
                candidate = line
                break

        # Strip markdown artifacts
        candidate = candidate.strip("`*\"'")

        # Cut at any leak marker (case-insensitive), whichever comes first
        lower = candidate.lower()
        cut_at = len(candidate)
        for marker in _COMMIT_LEAK_MARKERS:
            idx = lower.find(marker)
            if idx != -1 and idx < cut_at:
                cut_at = idx
        candidate = candidate[:cut_at].strip()

        # Strip trailing punctuation
        candidate = candidate.rstrip(".,;:")

        return candidate.strip()

    @staticmethod
    def _clean_markdown_fences(raw: str) -> str:
        """Removes wrapping ```markdown / ``` / ```javascript fences."""
        text = raw.strip()
        text = re.sub(r"^```(?:markdown|javascript|js|solidity)?\s*\n?", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\n?```\s*$", "", text)
        text = re.sub(r"^(?:markdown|javascript)\s*\n", "", text, flags=re.IGNORECASE)
        return text.strip()

    # -------------------------------------------------
    # INTERNAL HELPERS
    # -------------------------------------------------

    def _resolve(self, prompt: str, task: str) -> tuple[str, str]:
        if task == "code":
            return self.code_model, "code"
        if task == "text":
            return self.text_model, "text"
        score = sum(1 for kw in _CODE_KEYWORDS if kw in prompt.lower())
        if score >= 2:
            return self.code_model, "code"
        return self.text_model, "text"

    def _build_prompt(self, prompt: str, system: str, context: str) -> str:
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
