"""
executor.py — Detecta e executa ações do agente no sistema local

Ações suportadas:
  run_command  → executa comando de terminal
  create_file  → cria arquivo no workspace
  read_file    → lê conteúdo de arquivo
"""

import json
import re
import subprocess
import platform
from pathlib import Path

WORKSPACE = Path.home() / "panda_workspace"


def ensure_workspace():
    WORKSPACE.mkdir(parents=True, exist_ok=True)


class Executor:
    def __init__(self):
        ensure_workspace()
        self._confirm_rules: list[str] = []

    def set_confirmation_rules(self, rules: list[str]):
        """Define quais comandos exigem confirmação do usuário."""
        self._confirm_rules = [r.lower() for r in rules]

    def _requires_confirmation(self, cmd: str) -> bool:
        cmd_lower = cmd.lower()
        return any(rule in cmd_lower for rule in self._confirm_rules)

    def _ask_confirmation(self, cmd: str) -> bool:
        print(f"\n⚠️  Ação requer aprovação:")
        print(f"   $ {cmd}")
        answer = input("\n   Confirma? (s/n): ").strip().lower()
        return answer == "s"

    # ─────────────────────────────────────────────
    # EXTRAÇÃO DE AÇÃO DO JSON NA RESPOSTA
    # ─────────────────────────────────────────────
    def extract_action(self, response: str) -> dict | None:
        """Extrai o primeiro JSON de ação encontrado na resposta."""
        patterns = [
            r'```json\s*(\{.*?\})\s*```',        # bloco ```json ... ```
            r'```\s*(\{.*?\})\s*```',             # bloco ``` ... ```
            r'(\{[^{}]*"action"\s*:[^{}]*\})',    # JSON inline simples
            r'(\{.*?"action".*?\})',               # JSON multiline
        ]

        for pattern in patterns:
            matches = re.findall(pattern, response, re.DOTALL)
            for raw in matches:
                raw = raw.strip()
                try:
                    data = json.loads(raw)
                    if "action" in data:
                        return data
                except json.JSONDecodeError:
                    # Tenta consertar escapes comuns
                    try:
                        fixed = raw.replace('\n', '\\n').replace('\t', '\\t')
                        data = json.loads(fixed)
                        if "action" in data:
                            return data
                    except Exception:
                        continue
        return None

    # ─────────────────────────────────────────────
    # DISPATCHER
    # ─────────────────────────────────────────────
    def handle(self, response: str) -> str | None:
        """
        Verifica se a resposta contém uma ação e a executa.
        Retorna o resultado da ação ou None se não há ação.
        """
        action = self.extract_action(response)
        if not action:
            return None

        action_type = action.get("action", "")
        reason      = action.get("reason", "sem descrição")

        print(f"\n⚙️  Executando [{action_type}]: {reason}")

        if action_type == "run_command":
            return self._run_command(action)

        elif action_type == "create_file":
            return self._create_file(action)

        elif action_type == "read_file":
            return self._read_file(action)

        else:
            return f"Ação desconhecida: '{action_type}'"

    # ─────────────────────────────────────────────
    # AÇÕES
    # ─────────────────────────────────────────────
    def _run_command(self, action: dict) -> str:
        cmd = action.get("command", "").strip()
        if not cmd:
            return "Erro: campo 'command' vazio."

        # Verifica se precisa de confirmação
        if self._requires_confirmation(cmd):
            if not self._ask_confirmation(cmd):
                return f"Comando cancelado pelo usuário: {cmd}"

        print(f"   $ {cmd}")

        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(WORKSPACE),
            )
            output = []
            output.append(f"Comando: {cmd}")
            output.append(f"Exit code: {result.returncode}")
            if result.stdout.strip():
                output.append(f"stdout:\n{result.stdout.strip()}")
            if result.stderr.strip():
                output.append(f"stderr:\n{result.stderr.strip()}")
            return "\n".join(output)

        except subprocess.TimeoutExpired:
            return f"Timeout: '{cmd}' demorou mais de 60s."
        except Exception as e:
            return f"Erro ao executar comando: {e}"

    def _create_file(self, action: dict) -> str:
        path    = action.get("path", "").strip()
        content = action.get("content", "")

        if not path:
            return "Erro: campo 'path' vazio."

        full_path = (
            Path(path) if Path(path).is_absolute()
            else WORKSPACE / path
        )

        try:
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding="utf-8")
            print(f"   📄 Criado: {full_path}")
            return f"Arquivo criado: {full_path} ({len(content)} chars)"
        except Exception as e:
            return f"Erro ao criar arquivo: {e}"

    def _read_file(self, action: dict) -> str:
        path = action.get("path", "").strip()

        if not path:
            return "Erro: campo 'path' vazio."

        full_path = (
            Path(path) if Path(path).is_absolute()
            else WORKSPACE / path
        )

        if not full_path.exists():
            return f"Arquivo não encontrado: {full_path}"

        try:
            content = full_path.read_text(encoding="utf-8")
            print(f"   📖 Lido: {full_path}")
            return f"Conteúdo de '{path}':\n{content}"
        except Exception as e:
            return f"Erro ao ler arquivo: {e}"
