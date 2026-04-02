"""
PandaAgent v2 — Main entry point
Usage: python agent.py
"""

import json
from pathlib import Path
from brain import Brain
from executor import Executor
from memory import Memory
from indexer import Indexer

PROJECTS_FILE = Path(__file__).parent / "projects.json"


# ─────────────────────────────────────────────
# SELEÇÃO DE PROJETO
# ─────────────────────────────────────────────
def load_projects() -> dict:
    if not PROJECTS_FILE.exists():
        print("⚠️  projects.json not found.")
        return {}
    with open(PROJECTS_FILE, encoding="utf-8") as f:
        return json.load(f)


def select_project(data: dict) -> tuple[str, dict] | tuple[None, None]:
    """Displays project menu and returns (name, config) of selected project."""
    projects = data.get("projects", {})
    keys = list(projects.keys())

    # Group by type for organized display
    types = {}
    for key, cfg in projects.items():
        t = cfg.get("type", "other")
        types.setdefault(t, []).append(key)

    type_labels = {
        "contract":   "⛓️  Contracts",
        "frontend":   "🌐 Frontend",
        "automation": "🤖 Automation",
        "tool":       "🔧 Tools",
        "sandbox":    "🧪 Sandbox",
        "other":      "📦 Other",
    }

    print("\n📁 Available projects:")
    print("-" * 50)
    idx = 1
    index_map = {}  # number → project key

    for type_key, label in type_labels.items():
        group = types.get(type_key, [])
        if not group:
            continue
        print(f"\n  {label}")
        for key in group:
            desc = projects[key].get("description", "")
            # Truncate long description
            if len(desc) > 55:
                desc = desc[:52] + "..."
            print(f"  [{idx:2d}] {key:<15} {desc}")
            index_map[idx] = key
            idx += 1

    print(f"\n  [ 0] General mode (no project)")
    print("-" * 50)

    while True:
        try:
            choice = input("Select project: ").strip()
            if choice == "0":
                return None, None
            num = int(choice)
            if num in index_map:
                key = index_map[num]
                return key, projects[key]
            print(f"   Invalid option. Enter a number between 0 and {idx - 1}.")
        except ValueError:
            # Also accepts typing the name directly
            if choice in projects:
                return choice, projects[choice]
            print("   Enter the number or the exact project name.")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    print("=" * 50)
    print("  🐼 PandaAgent v2")
    print("  phi3 (planning) + deepseek-coder (code)")
    print("=" * 50)

    brain    = Brain()
    executor = Executor()
    memory   = Memory()

    if not brain.check_ollama():
        print("\n⚠️  Ollama not detected.")
        print("   1. Install: https://ollama.com")
        print("   2. Run: ollama serve")
        print(f"   3. Pull models:")
        print(f"      ollama pull phi3")
        print(f"      ollama pull deepseek-coder:6.7b-instruct-q4_K_M")
        return

    print(f"\n✅ Ollama online")
    print(f"   General model: {brain.GENERAL_MODEL}")
    print(f"   Coder model:   {brain.CODER_MODEL}")

    # ── Seleção de projeto ──────────────────────
    data = load_projects()
    project_name, project_cfg = select_project(data) if data else (None, None)

    if project_name and project_cfg:
        project_path = project_cfg.get("path", "")
        project_desc = project_cfg.get("description", "")
        project_stack = project_cfg.get("stack", [])
        confirm_cmds = project_cfg.get(
            "require_confirmation",
            data.get("settings", {}).get("default_confirmation", [])
        )
        indexer = Indexer(project_path)
        executor.set_confirmation_rules(confirm_cmds)
        brain.set_project_context(project_name, project_desc, project_stack)
        print(f"\n✅ Project: {project_name}")
        print(f"   {project_desc}")
        print(f"   Stack: {', '.join(project_stack)}")
        print(f"   Requires confirmation: {', '.join(confirm_cmds)}")
    else:
        indexer = Indexer("")
        print("\n   General mode — no project selected")

    print(f"\n   Special commands:")
    print(f"   'index'      → read and index the current project")
    print(f"   'summarize'  → explain what the project does (requires index)")
    print(f"   'map'        → show indexed structure")
    print(f"   'switch'     → select another project")
    print(f"   'history'    → show conversation log")
    print(f"   'clear'      → reset session history")
    print(f"   'clear_log'  → archive memory.txt and start fresh")
    print(f"   'quit'       → exit\n")

    while True:
        try:
            user_input = input("You: ").strip()

            if not user_input:
                continue

            # ── Comandos especiais ──────────────────
            if user_input.lower() in ("quit", "exit"):
                print("Shutting down. Goodbye! 🐼")
                break

            if user_input.lower() == "switch":
                project_name, project_cfg = select_project(data)
                if project_name and project_cfg:
                    project_path = project_cfg.get("path", "")
                    project_desc = project_cfg.get("description", "")
                    project_stack = project_cfg.get("stack", [])
                    confirm_cmds = project_cfg.get(
                        "require_confirmation",
                        data.get("settings", {}).get("default_confirmation", [])
                    )
                    indexer = Indexer(project_path)
                    executor.set_confirmation_rules(confirm_cmds)
                    brain.set_project_context(project_name, project_desc, project_stack)
                    memory.clear_session()
                    print(f"✅ Switched to: {project_name} (session history cleared)")
                continue

            if user_input.lower() == "index":
                if not project_name:
                    print("No project selected. Use 'switch' to select one.")
                    continue
                indexer.index()
                stats = indexer.stats()
                print(f"   📊 {stats['arquivos']} files | extensions: {', '.join(stats['extensoes'])}")
                continue

            if user_input.lower() == "summarize":
                if not project_name:
                    print("No project selected. Use 'switch' to select one.")
                    continue
                if not indexer._file_index:
                    print("Project not indexed. Run 'index' first.")
                    continue
                print(f"\n🔍 Generating summary for '{project_name}'...")
                context = indexer.summarize()
                prompt = (
                    f"Analyze the project '{project_name}' based on the files below "
                    f"and explain in plain text: what it does, how it works, what the "
                    f"main files are and what each one does. "
                    f"Respond ONLY in plain text, no JSON, no action blocks.\n\n{context}"
                )
                # Force general model — summary is always explanation, not code
                response = brain._call(brain.GENERAL_MODEL, "general", prompt, memory.get_history())
                short_model = brain.GENERAL_MODEL.split(":")[0]
                print(f"\nAgent [{short_model}]: {response}\n")
                memory.save(f"summarize {project_name}", response, short_model)
                continue

            if user_input.lower() == "map":
                indexer.show_map()
                continue

            if user_input.lower() == "history":
                memory.show()
                continue

            if user_input.lower() == "clear":
                memory.clear_session()
                print("Session history cleared.")
                continue

            if user_input.lower() == "clear_log":
                archived = memory.archive_log()
                if archived:
                    memory.clear_session()
                    print(f"✅ Log archived as '{archived}' and session cleared.")
                else:
                    print("   memory.txt is already empty, nothing to archive.")
                continue

            # ── Contexto do projeto ─────────────────
            project_context = ""
            if indexer._file_index:
                # Detect general questions about the project
                general_triggers = [
                    "what", "explain", "describe", "how does", "overview",
                    "summarize", "summary", "understand", "the project",
                    "this project", "what does", "what is", "purpose",
                ]
                is_general = any(t in user_input.lower() for t in general_triggers)

                if is_general:
                    # Inject full map + 3 most relevant files
                    map_content = indexer.map_file.read_text(encoding="utf-8") if indexer.map_file.exists() else ""
                    file_snippet = indexer.search(user_input, max_files=3)
                    project_context = map_content + "\n\n" + file_snippet
                else:
                    project_context = indexer.search(user_input)

            enriched_input = user_input
            if project_context:
                enriched_input = (
                    f"{user_input}\n\n"
                    f"--- Project context: {project_name} ---\n"
                    f"{project_context}\n"
                    f"--------------------------------------"
                )

            # ── Brain pensa ─────────────────────────
            model_used, response = brain.think(enriched_input, memory.get_history())

            # ── Executor age ────────────────────────
            action_result = executor.handle_sequence(response)

            if action_result:
                final_response = brain.interpret_result(
                    user_input, response, action_result, memory.get_history()
                )
            else:
                final_response = response

            print(f"\nAgent [{model_used}]: {final_response}\n")

            memory.save(user_input, final_response, model_used)

        except KeyboardInterrupt:
            print("\n\nInterrupted.")
            break


if __name__ == "__main__":
    main()
