"""
memory.py — Session history and persistent log management

- In-memory history: used as context for the LLM
- memory.txt: persistent log of all conversations
"""

from datetime import datetime
from pathlib import Path

MEMORY_FILE = Path(__file__).parent / "memory.txt"
MAX_HISTORY = 20  # maximum turns in the LLM context


class Memory:
    def __init__(self):
        self._session: list[dict] = []
        # Garante que o arquivo existe
        MEMORY_FILE.touch(exist_ok=True)

    # ─────────────────────────────────────────────
    # HISTÓRICO DE SESSÃO (contexto para o LLM)
    # ─────────────────────────────────────────────
    def get_history(self) -> list[dict]:
        """Returns the current session history (last MAX_HISTORY turns)."""
        return self._session[-MAX_HISTORY:]

    def save(self, user: str, agent: str, model: str = ""):
        """Saves a conversation turn to the session and the log file."""
        entry = {
            "user": user,
            "agent": agent,
            "model": model,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }
        self._session.append(entry)

        # Persist to file
        self._write_to_file(entry)

    def clear_session(self):
        """Clears only the current session history (does not delete the file)."""
        self._session.clear()

    # ─────────────────────────────────────────────
    # LOG PERSISTENTE (memory.txt)
    # ─────────────────────────────────────────────
    def _write_to_file(self, entry: dict):
        """Writes an entry to the log file."""
        try:
            with open(MEMORY_FILE, "a", encoding="utf-8") as f:
                f.write(f"\n[{entry['timestamp']}] model={entry['model']}\n")
                f.write(f"USER:  {entry['user']}\n")
                f.write(f"AGENT: {entry['agent']}\n")
                f.write("-" * 60 + "\n")
        except Exception as e:
            print(f"Warning: could not save to memory.txt — {e}")

    def show(self, last_n: int = 5):
        """Displays the last N log entries in the terminal."""
        if not MEMORY_FILE.exists() or MEMORY_FILE.stat().st_size == 0:
            print("History is empty.")
            return

        lines = MEMORY_FILE.read_text(encoding="utf-8").strip().split("\n")
        # Get the last lines
        tail = lines[-min(last_n * 6, len(lines)):]
        print("\n" + "=" * 60)
        print("  RECENT HISTORY")
        print("=" * 60)
        print("\n".join(tail))
        print("=" * 60 + "\n")

    def archive_log(self) -> str:
        """
        Arquiva o memory.txt atual renomeando para memory_YYYY-MM-DD_HHMMSS.txt
        e cria um novo memory.txt vazio.
        Retorna o nome do arquivo gerado.
        """
        if not MEMORY_FILE.exists() or MEMORY_FILE.stat().st_size == 0:
            return ""

        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        archive_name = MEMORY_FILE.parent / f"memory_{timestamp}.txt"
        MEMORY_FILE.rename(archive_name)
        MEMORY_FILE.touch()
        return archive_name.name

    def load_last_session(self, n: int = 10) -> list[dict]:
        """
        Reads the last N entries from the file and returns them as a list.
        Useful for resuming context after restarting the agent.
        """
        if not MEMORY_FILE.exists():
            return []

        entries = []
        current = {}

        for line in MEMORY_FILE.read_text(encoding="utf-8").splitlines():
            if line.startswith("[") and "model=" in line:
                if current:
                    entries.append(current)
                current = {}
            elif line.startswith("USER:  "):
                current["user"] = line[7:]
            elif line.startswith("AGENT: "):
                current["agent"] = line[7:]

        if current:
            entries.append(current)

        return entries[-n:]
