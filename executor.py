"""
executor.py — Detects and executes agent actions on the local system

Supported actions:
  run_command  → executes a terminal command
  create_file  → creates a file in the workspace
  read_file    → reads file content

Modes:
  handle()          → executes the first action found (original behavior)
  handle_sequence() → executes all found actions in order
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
        """Defines which commands require user confirmation."""
        self._confirm_rules = [r.lower() for r in rules]

    def _requires_confirmation(self, cmd: str) -> bool:
        cmd_lower = cmd.lower()
        return any(rule in cmd_lower for rule in self._confirm_rules)

    def _ask_confirmation(self, cmd: str) -> bool:
        print(f"\n⚠️  Action requires approval:")
        print(f"   $ {cmd}")
        answer = input("\n   Confirm? (y/n): ").strip().lower()
        return answer == "y"

    # ─────────────────────────────────────────────
    # ACTION JSON EXTRACTION
    # ─────────────────────────────────────────────
    def extract_action(self, response: str) -> dict | None:
        """Extracts the first action JSON found in the response."""
        actions = self.extract_actions(response)
        return actions[0] if actions else None

    def extract_actions(self, response: str) -> list[dict]:
        """
        Extracts ALL action JSONs found in the response, in order.
        Supports JSON lists and multiple separate blocks.
        """
        found = []

        # 1. Try JSON list: [{"action":...}, {"action":...}]
        list_patterns = [
            r'```json\s*(\[.*?\])\s*```',
            r'```\s*(\[.*?\])\s*```',
            r'(\[\s*\{.*?"action".*?\}\s*\])',
        ]
        for pattern in list_patterns:
            matches = re.findall(pattern, response, re.DOTALL)
            for raw in matches:
                try:
                    data = json.loads(raw)
                    if isinstance(data, list):
                        valid = [d for d in data if isinstance(d, dict) and "action" in d]
                        if valid:
                            return valid
                except Exception:
                    continue

        # 2. Try individual JSONs in sequence
        patterns = [
            r'```json\s*(\{.*?\})\s*```',
            r'```\s*(\{.*?\})\s*```',
            r'(\{[^{}]*"action"\s*:[^{}]*\})',
            r'(\{.*?"action".*?\})',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, response, re.DOTALL)
            for raw in matches:
                raw = raw.strip()
                try:
                    data = json.loads(raw)
                    if "action" in data and data not in found:
                        found.append(data)
                except json.JSONDecodeError:
                    try:
                        fixed = raw.replace('\n', '\\n').replace('\t', '\\t')
                        data = json.loads(fixed)
                        if "action" in data and data not in found:
                            found.append(data)
                    except Exception:
                        continue

        return found

    # ─────────────────────────────────────────────
    # DISPATCHER — single action (original behavior)
    # ─────────────────────────────────────────────
    def handle(self, response: str) -> str | None:
        """
        Checks if the response contains an action and executes it.
        Returns the result or None if no action found.
        """
        action = self.extract_action(response)
        if not action:
            return None
        return self._dispatch(action)

    # ─────────────────────────────────────────────
    # DISPATCHER — action sequence
    # ─────────────────────────────────────────────
    def handle_sequence(self, response: str) -> str | None:
        """
        Extracts and executes ALL actions in order.
        Stops on first failure if stop_on_error=True.
        Returns a string with all results concatenated.
        """
        actions = self.extract_actions(response)
        if not actions:
            return None

        total = len(actions)
        if total == 1:
            return self._dispatch(actions[0])

        print(f"\n📋 Sequence of {total} actions detected")
        for i, action in enumerate(actions, 1):
            print(f"   [{i}/{total}] {action.get('action')} — {action.get('reason', '')}")

        print()
        results = []
        for i, action in enumerate(actions, 1):
            print(f"\n-- Action {i}/{total} ------------------")
            result = self._dispatch(action)

            if result is None:
                result = "Unknown action"

            results.append(f"[{i}/{total}] {action.get('action')}: {result}")

            # If command was cancelled by user, stop the sequence
            if result.startswith("Command cancelled"):
                results.append("Sequence interrupted by user.")
                break

            # If there was an execution error, ask whether to continue
            if "Error" in result or "Exit code: 1" in result:
                print(f"\n⚠️  Error in action {i}. Continue sequence? (y/n): ", end="")
                answer = input().strip().lower()
                if answer != "y":
                    results.append("Sequence interrupted after error.")
                    break

        return "\n\n".join(results)

    # ─────────────────────────────────────────────
    # INDIVIDUAL DISPATCH
    # ─────────────────────────────────────────────
    def _dispatch(self, action: dict) -> str:
        action_type = action.get("action", "")
        reason      = action.get("reason", "no description")

        print(f"\n⚙️  Executing [{action_type}]: {reason}")

        if action_type == "run_command":
            return self._run_command(action)
        elif action_type == "create_file":
            return self._create_file(action)
        elif action_type == "read_file":
            return self._read_file(action)
        else:
            return f"Unknown action: '{action_type}'"

    # ─────────────────────────────────────────────
    # ACTIONS
    # ─────────────────────────────────────────────
    def _run_command(self, action: dict) -> str:
        cmd = action.get("command", "").strip()
        if not cmd:
            return "Error: 'command' field is empty."

        if self._requires_confirmation(cmd):
            if not self._ask_confirmation(cmd):
                return f"Command cancelled by user: {cmd}"

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
            output.append(f"Command: {cmd}")
            output.append(f"Exit code: {result.returncode}")
            if result.stdout.strip():
                output.append(f"stdout:\n{result.stdout.strip()}")
            if result.stderr.strip():
                output.append(f"stderr:\n{result.stderr.strip()}")
            result_str = "\n".join(output)
            print(f"\n{result_str}")
            return result_str

        except subprocess.TimeoutExpired:
            return f"Timeout: '{cmd}' took more than 60s."
        except Exception as e:
            return f"Error executing command: {e}"

    def _create_file(self, action: dict) -> str:
        path    = action.get("path", "").strip()
        content = action.get("content", "")

        if not path:
            return "Error: 'path' field is empty."

        full_path = (
            Path(path) if Path(path).is_absolute()
            else WORKSPACE / path
        )

        try:
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding="utf-8")
            print(f"   📄 Created: {full_path}")
            return f"File created: {full_path} ({len(content)} chars)"
        except Exception as e:
            return f"Error creating file: {e}"

    def _read_file(self, action: dict) -> str:
        path = action.get("path", "").strip()

        if not path:
            return "Error: 'path' field is empty."

        full_path = (
            Path(path) if Path(path).is_absolute()
            else WORKSPACE / path
        )

        if not full_path.exists():
            return f"File not found: {full_path}"

        try:
            content = full_path.read_text(encoding="utf-8")
            print(f"   📖 Read: {full_path}")
            return f"Contents of '{path}':\n{content}"
        except Exception as e:
            return f"Error reading file: {e}"
