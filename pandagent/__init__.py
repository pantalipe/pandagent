"""
pandagent — Shared Ollama client for the PandaEcosystem.

Install once in dev mode:
    pip install -e C:/Users/panta/pandagent

Then import from any project:
    from pandagent import PandaClient, TASK_MODEL_MAP
    from pandagent.panda_client import PandaClient  # also works
"""

from pandagent.panda_client import (
    PandaClient,
    TASK_MODEL_MAP,
    OLLAMA_BASE_URL,
    DEFAULT_TEXT_MODEL,
    DEFAULT_CODE_MODEL,
)

__version__ = "1.0.0"

__all__ = [
    "PandaClient",
    "TASK_MODEL_MAP",
    "OLLAMA_BASE_URL",
    "DEFAULT_TEXT_MODEL",
    "DEFAULT_CODE_MODEL",
]
