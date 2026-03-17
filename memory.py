"""
memory.py — Gerenciamento de histórico de sessão e log persistente

- Histórico em memória: usado como contexto para o LLM
- memory.txt: log persistente de todas as conversas
"""

from datetime import datetime
from pathlib import Path

MEMORY_FILE = Path(__file__).parent / "memory.txt"
MAX_HISTORY = 20  # máximo de turnos no contexto do LLM


class Memory:
    def __init__(self):
        self._session: list[dict] = []
        # Garante que o arquivo existe
        MEMORY_FILE.touch(exist_ok=True)

    # ─────────────────────────────────────────────
    # HISTÓRICO DE SESSÃO (contexto para o LLM)
    # ─────────────────────────────────────────────
    def get_history(self) -> list[dict]:
        """Retorna histórico da sessão atual (últimos MAX_HISTORY turnos)."""
        return self._session[-MAX_HISTORY:]

    def save(self, user: str, agent: str, model: str = ""):
        """Salva um turno de conversa na sessão e no arquivo."""
        entry = {
            "user": user,
            "agent": agent,
            "model": model,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }
        self._session.append(entry)

        # Persiste no arquivo
        self._write_to_file(entry)

    def clear_session(self):
        """Limpa apenas o histórico da sessão atual (não apaga o arquivo)."""
        self._session.clear()

    # ─────────────────────────────────────────────
    # LOG PERSISTENTE (memory.txt)
    # ─────────────────────────────────────────────
    def _write_to_file(self, entry: dict):
        """Escreve uma entrada no arquivo de log."""
        try:
            with open(MEMORY_FILE, "a", encoding="utf-8") as f:
                f.write(f"\n[{entry['timestamp']}] modelo={entry['model']}\n")
                f.write(f"USER:  {entry['user']}\n")
                f.write(f"AGENT: {entry['agent']}\n")
                f.write("-" * 60 + "\n")
        except Exception as e:
            print(f"Aviso: não foi possível salvar no memory.txt — {e}")

    def show(self, last_n: int = 5):
        """Exibe as últimas N entradas do log no terminal."""
        if not MEMORY_FILE.exists() or MEMORY_FILE.stat().st_size == 0:
            print("Histórico vazio.")
            return

        lines = MEMORY_FILE.read_text(encoding="utf-8").strip().split("\n")
        # Pega as últimas linhas
        tail = lines[-min(last_n * 6, len(lines)):]
        print("\n" + "=" * 60)
        print("  HISTÓRICO RECENTE")
        print("=" * 60)
        print("\n".join(tail))
        print("=" * 60 + "\n")

    def load_last_session(self, n: int = 10) -> list[dict]:
        """
        Lê as últimas N entradas do arquivo e retorna como lista.
        Útil para retomar contexto após reiniciar o agente.
        """
        if not MEMORY_FILE.exists():
            return []

        entries = []
        current = {}

        for line in MEMORY_FILE.read_text(encoding="utf-8").splitlines():
            if line.startswith("[") and "modelo=" in line:
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
