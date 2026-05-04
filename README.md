# pandagent

Local AI development assistant powered by Ollama. Zero API costs, zero cloud dependency.

## What it does

A modular AI agent that runs entirely on your machine. It routes tasks between two local models — one for planning, one for code generation — and can execute actions directly on your filesystem based on the model's responses.

It also exposes `panda_client.py` — a shared Ollama client that any project in the ecosystem can import to access LLM functionality without duplicating Ollama call logic.

## How it works

```
User input
    ↓
brain.py — routes to the right model
    ↓
Ollama (local LLM)
    ↓
executor.py — detects JSON actions and runs them
    ↓
memory.py — saves session history
```

## Model routing

| Model | Role |
|-------|------|
| `phi3` | Planning, architecture, general questions |
| `deepseek-coder:6.7b-instruct-q4_K_M` | Code generation, file creation, debugging |

The router scores the user input against keyword lists and picks the most appropriate model automatically.

## Actions

When the model responds with a JSON action block, `executor.py` handles it:

```json
{ "action": "create_file", "path": "hello.py", "content": "print('hello')", "reason": "..." }
{ "action": "run_command", "command": "pip install requests", "reason": "..." }
{ "action": "read_file", "path": "main.py", "reason": "..." }
```

Commands matching the confirmation list (e.g. `git push`, `git reset`) require explicit approval before execution.

## Project context

Projects are registered in `projects.json`. When a project is selected at startup, the agent loads its path, stack and description into the system prompt — so the model already knows what it's working on before you type anything.

The `indexer.py` module reads the codebase and builds a relevance-scored index. For each user message, it injects only the most relevant files into the prompt, staying within the model's context window.

## panda_client — shared Ollama client

`pandagent` is an installable package. Install it once in editable mode and any project
in the ecosystem can import it directly — no `sys.path` hacks needed:

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
client.is_online()          # True if Ollama is reachable
client.available_models()   # list of installed model names
```

### Model routing (TASK_MODEL_MAP)

Each task type is routed to the most appropriate local model:

| Task key | Model | Used by |
|---|---|---|
| `commit` | `deepseek-coder` | gitmanager |
| `code` | `phi3` | pp-testenv |
| `script_bitcoinfacil` | `llama3.1:8b` | rotman |
| `script_pandapoints` | `mistral:7b` | rotman |

Currently used by: **gitmanager** (commit suggestions, README generation), **rotman** (script generation per channel), and **pp-testenv** (Hardhat test generation).

## Structure

```
pandagent/
├── agent.py               # entry point — orchestrates everything
├── brain.py               # model routing + Ollama calls
├── executor.py            # action parser + system execution
├── indexer.py             # codebase reader + relevance search
├── memory.py              # session history + persistent log
├── panda_client.py        # backward-compat shim → re-exports from pandagent package
├── pyproject.toml         # package definition for pip install -e .
├── pandagent/
│   ├── __init__.py        # exports PandaClient and TASK_MODEL_MAP
│   └── panda_client.py    # full implementation of the shared Ollama client
├── memory.txt             # conversation log (auto-generated, gitignored)
└── projects.json          # project registry (gitignored)
```

## Requirements

No external dependencies. Uses Python standard library only.

[Ollama](https://ollama.com) must be running with at least one model pulled:

```bash
ollama serve
ollama pull phi3
ollama pull deepseek-coder:6.7b-instruct-q4_K_M
```

## Usage

```bash
python agent.py
```

Select a project from the menu or choose general mode. Type `index` to index the selected project before asking code-related questions.

## Special commands

| Command | Action |
|---------|--------|
| `index` | Index the current project |
| `summarize` | Explain what the project does (requires `index`) |
| `map` | Show the project file map |
| `switch` | Switch to another project |
| `history` | Show conversation log |
| `clear` | Clear session history |
| `clear_log` | Archive `memory.txt` with timestamp and start fresh |
| `quit` | Exit |

## Hardware

Tested on 8GB RAM with CPU-only inference. Recommended: 16GB RAM for running both models without swap.
