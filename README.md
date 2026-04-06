# pandagent

Local AI development assistant powered by Ollama. Zero API costs, zero cloud dependency.

## What it does

A modular AI agent that runs entirely on your machine. It routes tasks between two local models — one for planning, one for code generation — and can execute actions directly on your filesystem based on the model's responses.

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

## Structure

```
panda_agent/
├── agent.py        # entry point — orchestrates everything
├── brain.py        # model routing + Ollama calls
├── executor.py     # action parser + system execution
├── indexer.py      # codebase reader + relevance search
├── memory.py       # session history + persistent log
├── memory.txt      # conversation log (auto-generated)
└── projects.json   # project registry
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
