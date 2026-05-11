# pandagent

Local LLM client package for the panda ecosystem. Zero API costs, zero cloud dependency.

## What it does

`pandagent` is an installable Python package that exposes `PandaClient` — a shared
inference client used by every LLM-powered project in the ecosystem. It routes tasks
to the right local model, cleans model output, and provides consistent methods for
commit messages, README generation, script generation, and Hardhat test generation.

Install it once and any project can import it:

```bash
cd C:/Users/panta/pandagent
pip install -e .
```

```python
from pandagent import PandaClient

client = PandaClient()
client.ask("Explain this diff", task="code")
client.commit_message(diff=diff_text, status=status_text, project_name="gitmanager")
client.generate_readme(project_name="myproject", description="...", stack=["python"])
client.generate_script(topic="What is Bitcoin halving?", channel="bitcoinfacil")
client.generate_hardhat_test(function_source="function buyTokens() ...")
client.is_online()          # True if LLM server is reachable
client.available_models()   # list of model IDs reported by the server
```

## LLM server

`PandaClient` targets any OpenAI-compatible server at `http://localhost:8080`.
The ecosystem uses [llama-swap](https://github.com/mostlygeek/llama-swap) or
llama-server as the inference backend.

```
LLM_BASE_URL = "http://localhost:8080"   # configurable via constructor
OLLAMA_BASE_URL                          # backward-compat alias for the same URL
```

## Model routing (TASK_MODEL_MAP)

Each task type is routed to the most appropriate local model:

| Task key | Model | Used by |
|---|---|---|
| `commit` | `deepseek-coder:6.7b-instruct-q4_K_M` | gitmanager |
| `code` | `phi3` | pp-testenv |
| `readme` | `phi3` | gitmanager |
| `script_bitcoinfacil` | `llama3.1:8b` | rotman |
| `script_pandapoints` | `mistral:7b` | rotman |
| `hardhat_test` | `deepseek-coder:6.7b-instruct-q4_K_M` | pp-testenv |

Model IDs must match the aliases registered in llama-swap's config.
Run `client.available_models()` to verify what the server reports.

## Output cleaners

| Method | What it cleans |
|---|---|
| `_clean_commit(raw)` | Extracts the first conventional commit line, strips scope leaks, trims to 72 chars |
| `_clean_markdown_fences(text)` | Strips ` ```markdown ` fences and leading `markdown\n` artifacts from model output |

## Currently used by

| Project | Methods used |
|---|---|
| **gitmanager** | `commit_message()`, `generate_readme()`, `available_models()` |
| **rotman** | `generate_script(channel=)`, `TASK_MODEL_MAP` |
| **pp-testenv** | `generate_hardhat_test(function_source=)`, `is_online()`, `available_models()` |
| **ollama-bench** | `TASK_MODEL_MAP` (for default model list) |

## Structure

```
pandagent/
├── pandagent/
│   ├── __init__.py        # exports PandaClient and TASK_MODEL_MAP
│   └── panda_client.py    # full implementation
├── panda_client.py        # backward-compat shim — re-exports from pandagent package
├── bench_runner.py        # ollama-bench integration helper
├── pyproject.toml         # package metadata for pip install -e .
├── test_openai_migration.py  # 27-check smoke test for the OpenAI endpoint migration
├── projects.json          # project registry (gitignored)
└── README.md
```

## Requirements

Python 3.10+. No external dependencies — uses stdlib `urllib` only.

An OpenAI-compatible LLM server must be running on port 8080 before making inference calls:

```bash
# llama-swap example
llama-swap --config llama-swap.yaml

# llama-server example
llama-server --model phi3.gguf --port 8080
```

## Running the migration test

```bash
python test_openai_migration.py
```

Runs 27 checks across 5 sections: constants, URL construction, `_build_messages`,
model routing, and live connectivity (sections 1–4 run without a server; section 5
requires the server on `:8080`).
