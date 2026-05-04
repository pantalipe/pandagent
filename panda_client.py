"""
panda_client.py — backward-compatibility shim

This file exists so that any code still using the old sys.path import pattern:

    sys.path.insert(0, "C:/Users/panta/pandagent")
    from panda_client import PandaClient

...continues to work without changes.

The real implementation now lives at pandagent/pandagent/panda_client.py.
Install the package properly and use:

    from pandagent import PandaClient
"""

from pandagent.panda_client import (  # noqa: F401
    PandaClient,
    TASK_MODEL_MAP,
    OLLAMA_BASE_URL,
    DEFAULT_TEXT_MODEL,
    DEFAULT_CODE_MODEL,
)
