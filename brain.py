"""
brain.py — Roteamento de modelos e chamadas ao Ollama

Lógica de decisão:
  - phi3               → planejamento, análise, perguntas gerais
  - deepseek-coder     → geração de código, debug, arquivos
"""

import re
import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_TAGS_URL = "http://localhost:11434/api/tags"


# ─────────────────────────────────────────────
# Palavras-chave que indicam tarefa de CÓDIGO
# ─────────────────────────────────────────────
CODE_KEYWORDS = [
    # linguagens / ferramentas
    "python", "solidity", "javascript", "typescript", "html", "css",
    "bash", "shell", "script", "sql", "json", "yaml", "toml",
    # ações de código
    "código", "code", "função", "function", "classe", "class",
    "implementar", "implement", "criar arquivo", "create file",
    "contrato", "contract", "deploy", "compile", "compilar",
    "bug", "erro", "error", "fix", "corrigir", "refatorar", "refactor",
    "instalar", "install", "npm", "pip", "import", "export",
    "api", "endpoint", "rota", "route", "web3", "abi", "erc",
    "next.js", "react", "hardhat", "foundry", "truffle",
    # comandos de terminal
    "execute", "executar", "rodar", "run", "comando",
]

# ─────────────────────────────────────────────
# Palavras-chave que indicam tarefa de PLANEJAMENTO
# ─────────────────────────────────────────────
GENERAL_KEYWORDS = [
    "planejar", "plan", "estratégia", "strategy", "arquitetura",
    "estrutura", "organizar", "organize", "como funciona", "explain",
    "explique", "resumir", "resume", "analisar", "analyze",
    "decisão", "decision", "comparar", "compare", "melhor forma",
    "roadmap", "etapas", "passos", "steps", "o que", "quando",
    "por que", "porque", "diferença", "diferenças",
]


class Brain:
    GENERAL_MODEL = "phi3"
    CODER_MODEL   = "deepseek-coder:6.7b-instruct-q4_K_M"

    # Prompts de sistema por modelo
    SYSTEM_PROMPTS = {
        "general": """Você é o PandaAgent, assistente especializado em planejamento e arquitetura de software.
Foco: Web3, DeFi, smart contracts, projetos Python e estratégia de desenvolvimento.
Seja direto, objetivo e use português.
Quando a tarefa envolver código específico, diga: "Vou passar para o módulo de código."
IMPORTANTE: Responda SEMPRE em texto corrido. NUNCA use JSON, NUNCA use blocos de ação.
""",
        "coder": """Você é o PandaAgent modo código. Especialista em Python, Solidity, Web3, JavaScript.

REGRA CRÍTICA: Quando o usuário pedir para CRIAR um arquivo, você DEVE responder APENAS com JSON de ação. Nada antes, nada depois.

Para UMA ação:
{"action": "create_file", "path": "arquivo.py", "content": "conteúdo", "reason": "descrição"}

Para MÚLTIPLAS ações em sequência, use uma lista JSON:
[
  {"action": "run_command", "command": "copy C:/Downloads/rb.py C:/projeto/rb.py", "reason": "copiar arquivo"},
  {"action": "run_command", "command": "python rb.py", "reason": "testar"},
  {"action": "run_command", "command": "git add . && git commit -m 'update'", "reason": "commit"},
  {"action": "run_command", "command": "git push", "reason": "push"}
]

Ações disponíveis:
- create_file  → {"action": "create_file", "path": "...", "content": "...", "reason": "..."}
- run_command  → {"action": "run_command", "command": "...", "reason": "..."}
- read_file    → {"action": "read_file", "path": "...", "reason": "..."}

IMPORTANTE:
- Use lista JSON quando houver 2 ou mais ações a executar em ordem
- Coloque o código COMPLETO dentro do campo "content"
- Use \\n para quebras de linha dentro do JSON
- Use português nos comentários do código
- Só explique em texto quando o usuário fizer uma pergunta, não pedir criação
""",
    }

    def set_project_context(self, name: str, description: str, stack: list[str]):
        """Injeta contexto do projeto nos prompts do sistema."""
        ctx = (
            f"\nPROJETO ATIVO: {name}\n"
            f"Descrição: {description}\n"
            f"Stack: {', '.join(stack)}\n"
            f"Mantenha todo código gerado compatível com essa stack.\n"
        )
        for key in self.SYSTEM_PROMPTS:
            self.SYSTEM_PROMPTS[key] = self.SYSTEM_PROMPTS[key].rstrip() + ctx

    def check_ollama(self) -> bool:
        """Verifica se o Ollama está rodando."""
        try:
            r = requests.get(OLLAMA_TAGS_URL, timeout=3)
            return r.status_code == 200
        except Exception:
            return False

    def route(self, user_input: str) -> tuple[str, str]:
        """
        Decide qual modelo usar com base no conteúdo da mensagem.
        Retorna: (nome_modelo, tipo_prompt)
        """
        text = user_input.lower()

        code_score    = sum(1 for kw in CODE_KEYWORDS    if kw in text)
        general_score = sum(1 for kw in GENERAL_KEYWORDS if kw in text)

        # Se empate ou ambíguo, prefere coder (mais seguro para tarefas mistas)
        if code_score >= general_score:
            return self.CODER_MODEL, "coder"
        else:
            return self.GENERAL_MODEL, "general"



    def _call(self, model: str, prompt_type: str, prompt: str, history: list) -> str:
        """Faz a chamada ao Ollama e retorna a resposta."""
        system = self.SYSTEM_PROMPTS[prompt_type]

        context = system + "\n\n"
        for turn in history[-4:]:
            context += f"Usuário: {turn['user']}\nAgente: {turn['agent']}\n\n"
        context += f"Usuário: {prompt}\nAgente:"

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
            r = requests.post(OLLAMA_URL, json=payload)#), timeout=180)
            r.raise_for_status()
            return r.json().get("response", "").strip()
        except requests.exceptions.ConnectionError:
            return "ERRO: Ollama não está rodando. Execute: ollama serve"
        #except requests.exceptions.Timeout:
        #    return "ERRO: Timeout — modelo demorou mais de 3min. Tente um modelo menor."
        except Exception as e:
            return f"ERRO inesperado: {e}"

    def think(self, user_input: str, history: list) -> tuple[str, str]:
        """
        Pensa sobre o input e retorna (modelo_usado, resposta).
        """
        model, prompt_type = self.route(user_input)

        # Log de roteamento no terminal
        icon = "💻" if prompt_type == "coder" else "🧠"
        short_model = model.split(":")[0]
        print(f"\n{icon} Roteando para: {short_model} ({prompt_type})", flush=True)

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
        Após executar uma ação, interpreta o resultado e gera resposta final.
        Usa o mesmo modelo que foi usado na resposta original.
        """
        model, prompt_type = self.route(original_input)

        prompt = (
            f"Tarefa original: {original_input}\n\n"
            f"Ação executada e resultado:\n{action_result}\n\n"
            "Interprete o resultado acima. Se houve erro, sugira correção. "
            "Se foi bem-sucedido, confirme e ofereça próximos passos."
        )

        return self._call(model, prompt_type, prompt, history)
