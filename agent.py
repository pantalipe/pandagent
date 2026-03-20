"""
PandaAgent v2 — Entry point principal
Uso: python agent.py
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
        print("⚠️  projects.json não encontrado.")
        return {}
    with open(PROJECTS_FILE, encoding="utf-8") as f:
        return json.load(f)


def select_project(data: dict) -> tuple[str, dict] | tuple[None, None]:
    """Exibe menu de projetos e retorna (nome, config) do selecionado."""
    projects = data.get("projects", {})
    keys = list(projects.keys())

    # Agrupa por tipo para exibição organizada
    types = {}
    for key, cfg in projects.items():
        t = cfg.get("type", "other")
        types.setdefault(t, []).append(key)

    type_labels = {
        "contract":   "⛓️  Contratos",
        "frontend":   "🌐 Frontend",
        "automation": "🤖 Automação",
        "tool":       "🔧 Ferramentas",
        "sandbox":    "🧪 Sandbox",
        "other":      "📦 Outros",
    }

    print("\n📁 Projetos disponíveis:")
    print("-" * 50)
    idx = 1
    index_map = {}  # número → chave do projeto

    for type_key, label in type_labels.items():
        group = types.get(type_key, [])
        if not group:
            continue
        print(f"\n  {label}")
        for key in group:
            desc = projects[key].get("description", "")
            # Trunca descrição longa
            if len(desc) > 55:
                desc = desc[:52] + "..."
            print(f"  [{idx:2d}] {key:<15} {desc}")
            index_map[idx] = key
            idx += 1

    print(f"\n  [ 0] Modo geral (sem projeto)")
    print("-" * 50)

    while True:
        try:
            choice = input("Selecione o projeto: ").strip()
            if choice == "0":
                return None, None
            num = int(choice)
            if num in index_map:
                key = index_map[num]
                return key, projects[key]
            print(f"   Opção inválida. Digite um número entre 0 e {idx - 1}.")
        except ValueError:
            # Aceita digitar o nome diretamente também
            if choice in projects:
                return choice, projects[choice]
            print("   Digite o número ou o nome exato do projeto.")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    print("=" * 50)
    print("  🐼 PandaAgent v2")
    print("  phi3 (planejamento) + deepseek-coder (código)")
    print("=" * 50)

    brain    = Brain()
    executor = Executor()
    memory   = Memory()

    if not brain.check_ollama():
        print("\n⚠️  Ollama não detectado.")
        print("   1. Instale: https://ollama.com")
        print("   2. Execute: ollama serve")
        print(f"   3. Baixe modelos:")
        print(f"      ollama pull phi3")
        print(f"      ollama pull deepseek-coder:6.7b-instruct-q4_K_M")
        return

    print(f"\n✅ Ollama online")
    print(f"   Modelo geral:  {brain.GENERAL_MODEL}")
    print(f"   Modelo código: {brain.CODER_MODEL}")

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
        print(f"\n✅ Projeto: {project_name}")
        print(f"   {project_desc}")
        print(f"   Stack: {', '.join(project_stack)}")
        print(f"   Confirmação obrigatória: {', '.join(confirm_cmds)}")
    else:
        indexer = Indexer("")
        print("\n   Modo geral — sem projeto selecionado")

    print(f"\n   Comandos especiais:")
    print(f"   'indexar'    → lê e indexa o projeto atual")
    print(f"   'resumir'    → explica o que o projeto faz (requer indexar)")
    print(f"   'mapa'       → mostra estrutura indexada")
    print(f"   'trocar'     → seleciona outro projeto")
    print(f"   'historico'  → mostra log de conversas")
    print(f"   'limpar'     → reseta histórico da sessão")
    print(f"   'sair'       → encerra\n")

    while True:
        try:
            user_input = input("Você: ").strip()

            if not user_input:
                continue

            # ── Comandos especiais ──────────────────
            if user_input.lower() in ("sair", "exit", "quit"):
                print("Encerrando. Até logo! 🐼")
                break

            if user_input.lower() == "trocar":
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
                    print(f"✅ Trocado para: {project_name} (histórico de sessão limpo)")
                continue

            if user_input.lower() == "indexar":
                if not project_name:
                    print("Nenhum projeto selecionado. Use 'trocar' para selecionar.")
                    continue
                indexer.index()
                stats = indexer.stats()
                print(f"   📊 {stats['arquivos']} arquivos | extensões: {', '.join(stats['extensoes'])}")
                continue

            if user_input.lower() == "resumir":
                if not project_name:
                    print("Nenhum projeto selecionado. Use 'trocar' para selecionar.")
                    continue
                if not indexer._file_index:
                    print("Projeto não indexado. Rode 'indexar' primeiro.")
                    continue
                print(f"\n🔍 Gerando resumo de '{project_name}'...")
                context = indexer.summarize()
                prompt = (
                    f"Analise o projeto '{project_name}' com base nos arquivos abaixo "
                    f"e explique em texto: o que ele faz, como funciona, quais são os "
                    f"arquivos principais e o que cada um faz. "
                    f"Responda APENAS em texto corrido, sem JSON, sem comandos.\n\n{context}"
                )
                # Força modelo general — resumo é sempre explicação, não código
                response = brain._call(brain.GENERAL_MODEL, "general", prompt, memory.get_history())
                short_model = brain.GENERAL_MODEL.split(":")[0]
                print(f"\nAgente [{short_model}]: {response}\n")
                memory.save(f"resumir {project_name}", response, short_model)
                continue

            if user_input.lower() == "mapa":
                indexer.show_map()
                continue

            if user_input.lower() == "historico":
                memory.show()
                continue

            if user_input.lower() == "limpar":
                memory.clear_session()
                print("Histórico de sessão limpo.")
                continue

            # ── Contexto do projeto ─────────────────
            project_context = ""
            if indexer._file_index:
                # Detecta perguntas gerais sobre o projeto
                general_triggers = [
                    "o que", "oque", "explique", "explica", "descreva",
                    "como funciona", "me fala", "me conta", "resumo",
                    "resumir", "overview", "visão geral", "entender",
                    "o projeto", "esse projeto", "este projeto",
                    "para que serve", "qual é", "qual a função",
                ]
                is_general = any(t in user_input.lower() for t in general_triggers)

                if is_general:
                    # Injeta o mapa completo + os 3 arquivos mais relevantes
                    map_content = indexer.map_file.read_text(encoding="utf-8") if indexer.map_file.exists() else ""
                    file_snippet = indexer.search(user_input, max_files=3)
                    project_context = map_content + "\n\n" + file_snippet
                else:
                    project_context = indexer.search(user_input)

            enriched_input = user_input
            if project_context:
                enriched_input = (
                    f"{user_input}\n\n"
                    f"--- Contexto do projeto {project_name} ---\n"
                    f"{project_context}\n"
                    f"------------------------------------------"
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

            print(f"\nAgente [{model_used}]: {final_response}\n")

            memory.save(user_input, final_response, model_used)

        except KeyboardInterrupt:
            print("\n\nInterrompido.")
            break


if __name__ == "__main__":
    main()
