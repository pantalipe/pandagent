# Changelog

All notable changes to pandagent are documented here.

---

## [Unreleased]

---

## [2.4] — 2026-05-09

### Changed
- `pandagent/panda_client.py` migrated from Ollama's native `/api/generate` to the
  OpenAI-compatible `/v1/chat/completions` endpoint
- `LLM_BASE_URL` replaces `OLLAMA_BASE_URL` as the primary constant, targeting
  `http://localhost:8080` (llama-swap / llama-server); `OLLAMA_BASE_URL` kept as a
  backward-compat alias pointing to the same URL
- `_build_prompt()` replaced by `_build_messages()` — returns a proper
  `[{role, content}]` array for the OpenAI messages format
- `_generate_url` / `_tags_url` replaced by `_chat_url` / `_models_url`
- `available_models()` now parses `data[].id` from `/v1/models` instead of
  `models[].name` from `/api/tags`
- Model IDs in `TASK_MODEL_MAP` verified against llama-swap `/v1/models` — all aliases
  match without changes required

### Added
- `test_openai_migration.py` — 27-check smoke test covering constants, URL construction,
  `_build_messages`, `_resolve` routing, and live connectivity against the
  `/v1/chat/completions` endpoint; sections 1–4 run offline
- `sys.stdout.reconfigure(encoding="utf-8")` in test file — prevents cp1252 crash on
  Windows when printing Unicode characters in test names

### Removed
- Dead agent architecture files: `agent.py`, `agent.py.old`, `agent.py.old2`,
  `brain.py`, `brain.py.old`, `executor.py`, `executor.py.old`, `indexer.py`,
  `memory.py`
- Stale text artifacts: `memory.txt`, `memory copy.txt`, `memory copy 2.txt`,
  `memory_2026-03-29_100522.txt`, `project_map.txt`

---

## [2.3] — 2026-05-04

### Added
- `pandagent/` package directory with `__init__.py` and `panda_client.py` — converts
  the project into an installable package (`pip install -e .`)
- `pyproject.toml` — package metadata and entry point definition
- `generate_hardhat_test(function_source)` — generates a Hardhat/ethers v6 test block
  for a given Solidity function source; used by `pp-testenv/gen_tests.py`
- `function_source` parameter on `generate_hardhat_test()` — injects the actual
  Solidity function body into the prompt for context-aware test generation
- `TASK_MODEL_MAP` — exported dict that routes task keys to specific models;
  consumed by rotman and ollama-bench for consistent model selection across the ecosystem
- `channel` parameter on `generate_script()` — selects model via `TASK_MODEL_MAP`
  based on channel slug (`bitcoinfacil` → `llama3.1:8b`, `pandapoints` → `mistral:7b`)
- `bench` and `bench_run` command support — enables ollama-bench integration

### Changed
- Root `panda_client.py` converted to a backward-compatibility shim that re-exports
  `PandaClient` and `TASK_MODEL_MAP` from the `pandagent` package — existing
  `sys.path`-based imports continue to work without changes
- Preferred import pattern is now `from pandagent import PandaClient` after
  `pip install -e .`

---

## [2.2] — 2026-04-21

### Changed
- Full source translation from Portuguese to English — all terminal output, prompts,
  commands, docstrings, and inline comments
- Special commands renamed: `indexar` → `index`, `resumir` → `summarize`,
  `mapa` → `map`, `trocar` → `switch`, `historico` → `history`, `limpar` → `clear`,
  `limpar_log` → `clear_log`, `sair` → `quit`
- `brain.py` system prompts rewritten in English for better model instruction-following
- Keyword lists (`CODE_KEYWORDS`, `GENERAL_KEYWORDS`) cleaned up and translated
- `memory.txt` log format updated: `modelo=` → `model=`

### Removed
- External `requests` dependency from `brain.py` — migrated to Python stdlib `urllib`

---

## [2.1] — 2026-04-06

### Added
- `clear_log` command: archives `memory.txt` with a timestamp suffix and starts a
  fresh log
- `memory_*.txt` pattern added to `.gitignore`

---

## [2.0]

### Changed
- Migrated HTTP calls in `brain.py` from `requests` to `urllib` (Python stdlib)
- Zero external dependencies

---

## [1.0]

### Added
- Modular local AI agent running entirely via Ollama
- Model routing: `phi3` for planning/analysis, `deepseek-coder` for code generation
- Project registry via `projects.json`
- `indexer.py`, `executor.py`, `memory.py` — codebase indexing, action execution,
  session history
- Special commands: `index`, `summarize`, `map`, `switch`, `history`, `clear`,
  `clear_log`, `quit`
