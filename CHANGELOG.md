# Changelog

All notable changes to pandagent are documented here.

---

## [Unreleased]

### Added
- Auto-translation of non-English user input before routing (via Ollama phi3)
- Translated input is displayed in the console when a change is detected

---

## [2.2] — 2026-04-07

### Changed
- Full source translation from Portuguese to English — all terminal output, prompts, commands, docstrings, and inline comments
- Special commands renamed: `indexar` → `index`, `resumir` → `summarize`, `mapa` → `map`, `trocar` → `switch`, `historico` → `history`, `limpar` → `clear`, `limpar_log` → `clear_log`, `sair` → `quit`
- `brain.py` system prompts rewritten in English for better model instruction-following
- Keyword lists (`CODE_KEYWORDS`, `GENERAL_KEYWORDS`) cleaned up and translated to English-only
- `memory.txt` log format updated: `modelo=` → `model=`
- README special commands table updated to reflect new command names

### Removed
- External `requests` dependency from `brain.py` — migrated to Python stdlib `urllib`

---

## [2.1] — 2026-04-06

### Added
- `clear_log` command: archives `memory.txt` with a timestamp suffix (`memory_YYYY-MM-DD_HHMMSS.txt`) and starts a fresh log
- `memory_*.txt` pattern added to `.gitignore` to cover archived log files

---

## [2.0]

### Changed
- Migrated HTTP calls in `brain.py` from `requests` to `urllib` (Python stdlib)
- Zero external dependencies — no `pip install` required

---

## [1.0]

### Added
- Modular local AI agent running entirely via Ollama
- Model routing: `phi3` for planning/analysis, `deepseek-coder` for code generation
- Project registry via `projects.json` — loads path, stack, and description into system prompt at startup
- `indexer.py` — reads codebase and builds relevance-scored index for context injection
- `executor.py` — parses JSON action blocks from model responses and executes them locally
  - Supported actions: `create_file`, `run_command`, `read_file`
  - Sequential action lists supported
  - Confirmation required for commands matching the project's `require_confirmation` list
- `memory.py` — in-memory session history + persistent `memory.txt` log
- Special commands: `index`, `summarize`, `map`, `switch`, `history`, `clear`, `clear_log`, `quit`