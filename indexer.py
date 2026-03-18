"""
indexer.py — Indexador inteligente de codebase

Duas camadas:
  1. index()      → lê todos os arquivos e gera project_map.txt (estrutura compacta)
  2. search()     → dado um objetivo, retorna só os arquivos mais relevantes

Uso no agent.py:
    from indexer import Indexer
    indexer = Indexer("C:/Users/panta/pandapoints")
    indexer.index()                          # roda uma vez / quando atualizar
    snippet = indexer.search("carteira sem extensão")
    # snippet vai como contexto extra pro brain.think()
"""

import os
import re
from pathlib import Path
from datetime import datetime

# ─────────────────────────────────────────────
# CONFIGURAÇÃO
# ─────────────────────────────────────────────

# Extensões que valem a pena ler
READABLE_EXTENSIONS = {
    ".js", ".jsx", ".ts", ".tsx",   # Next.js / React
    ".sol",                          # Solidity
    ".py",                           # Python
    ".json",                         # configs (package.json, hardhat, etc)
    ".env.example",                  # variáveis (nunca .env real)
    ".md",                           # docs
    ".toml", ".yaml", ".yml",        # configs extras
}

# Pastas para ignorar completamente
IGNORE_DIRS = {
    "node_modules", ".git", ".next", "out", "dist",
    "build", "__pycache__", ".cache", "coverage",
    "artifacts", "cache",            # hardhat
    "typechain-types",               # gerado automaticamente
}

# Arquivos para ignorar
IGNORE_FILES = {
    ".env",                          # nunca ler .env com secrets
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
}

# Tamanho máximo de arquivo para incluir no contexto (bytes)
MAX_FILE_SIZE = 15_000   # ~300 linhas

# Máximo de chars do snippet final enviado ao LLM
MAX_CONTEXT_CHARS = 6_000


class Indexer:
    def __init__(self, project_path: str):
        self.root = Path(project_path)
        self.map_file = Path(__file__).parent / "project_map.txt"
        self._file_index: dict[str, str] = {}  # path → conteúdo

    # ─────────────────────────────────────────────
    # 1. INDEXAÇÃO — gera project_map.txt
    # ─────────────────────────────────────────────
    def index(self) -> str:
        """
        Lê o codebase e salva um mapa compacto em project_map.txt.
        Retorna o mapa como string.
        """
        if not self.root.exists():
            return f"ERRO: Pasta não encontrada: {self.root}"

        print(f"\n📂 Indexando: {self.root}")
        self._file_index = {}
        lines = [
            f"# PandaAgent — Mapa do Projeto",
            f"# Gerado em: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"# Raiz: {self.root}",
            "=" * 60,
            "",
        ]

        file_count = 0
        skipped = 0

        for file_path in sorted(self.root.rglob("*")):
            # Ignora diretórios
            if file_path.is_dir():
                continue

            # Ignora pastas proibidas
            if any(part in IGNORE_DIRS for part in file_path.parts):
                continue

            # Ignora arquivos proibidos
            if file_path.name in IGNORE_FILES:
                continue

            # Filtra por extensão
            suffix = file_path.suffix.lower()
            if suffix not in READABLE_EXTENSIONS:
                # Aceita .env.example especificamente
                if file_path.name != ".env.example":
                    continue

            # Ignora arquivos grandes demais
            try:
                size = file_path.stat().st_size
                if size > MAX_FILE_SIZE:
                    skipped += 1
                    rel = file_path.relative_to(self.root)
                    lines.append(f"[GRANDE] {rel}  ({size // 1000}kb — ignorado)")
                    continue
            except Exception:
                continue

            # Lê o arquivo
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            rel = str(file_path.relative_to(self.root))
            self._file_index[rel] = content
            file_count += 1

            # Adiciona resumo compacto ao mapa
            summary = self._summarize(file_path, content)
            lines.append(f"📄 {rel}")
            if summary:
                lines.append(f"   {summary}")
            lines.append("")

        lines.append("=" * 60)
        lines.append(f"Total: {file_count} arquivos indexados, {skipped} ignorados por tamanho.")

        map_content = "\n".join(lines)
        self.map_file.write_text(map_content, encoding="utf-8")
        print(f"   ✅ {file_count} arquivos | mapa salvo em project_map.txt")
        return map_content

    def _summarize(self, path: Path, content: str) -> str:
        """Gera uma linha de resumo por tipo de arquivo."""
        ext = path.suffix.lower()
        name = path.name

        if name == "package.json":
            # Extrai nome e dependências principais
            try:
                import json
                data = json.loads(content)
                deps = list(data.get("dependencies", {}).keys())[:6]
                return f"deps: {', '.join(deps)}"
            except Exception:
                return ""

        if ext == ".sol":
            # Extrai nome do contrato e funções públicas
            contracts = re.findall(r'contract\s+(\w+)', content)
            funcs = re.findall(r'function\s+(\w+)\s*\(', content)
            pub_funcs = funcs[:5]
            parts = []
            if contracts:
                parts.append(f"contract: {', '.join(contracts)}")
            if pub_funcs:
                parts.append(f"funcs: {', '.join(pub_funcs)}")
            return " | ".join(parts)

        if ext in (".ts", ".tsx", ".js", ".jsx"):
            # Extrai exports e componentes React
            exports = re.findall(r'export\s+(?:default\s+)?(?:function|const|class)\s+(\w+)', content)
            hooks = re.findall(r'const\s+(use\w+)\s*=', content)
            parts = []
            if exports:
                parts.append(f"exports: {', '.join(exports[:5])}")
            if hooks:
                parts.append(f"hooks: {', '.join(hooks[:3])}")
            return " | ".join(parts)

        if ext == ".py":
            funcs = re.findall(r'def\s+(\w+)\s*\(', content)
            classes = re.findall(r'class\s+(\w+)', content)
            parts = []
            if classes:
                parts.append(f"classes: {', '.join(classes[:3])}")
            if funcs:
                parts.append(f"funcs: {', '.join(funcs[:5])}")
            return " | ".join(parts)

        if ext == ".md":
            first_line = content.strip().splitlines()[0] if content.strip() else ""
            return first_line[:80]

        return ""

    # ─────────────────────────────────────────────
    # 2. BUSCA — retorna arquivos relevantes
    # ─────────────────────────────────────────────
    def search(self, query: str, max_files: int = 4) -> str:
        """
        Dado um objetivo/query, retorna o conteúdo dos arquivos
        mais relevantes como string para injetar no prompt.
        """
        if not self._file_index:
            # Tenta carregar do disco se não indexou ainda nesta sessão
            if self.map_file.exists():
                print("   ℹ️  Usando índice existente (rode indexer.index() para atualizar)")
                # Re-indexa silenciosamente para popular _file_index
                self.index()
            else:
                return "⚠️  Projeto não indexado. Rode: indexer.index()"

        # Pontua cada arquivo por relevância à query
        query_terms = query.lower().split()
        scores: list[tuple[float, str]] = []

        for rel_path, content in self._file_index.items():
            score = 0.0
            path_lower = rel_path.lower()
            content_lower = content.lower()

            for term in query_terms:
                # Termo no caminho do arquivo vale mais
                if term in path_lower:
                    score += 3.0
                # Termo no conteúdo
                score += content_lower.count(term) * 0.5

            # Bonus por tipo de arquivo
            if rel_path.endswith(".sol"):
                score += 1.0       # contratos sempre relevantes
            if "wallet" in path_lower or "carteira" in path_lower:
                score += 5.0
            if "auth" in path_lower or "account" in path_lower:
                score += 2.0
            if "hook" in path_lower:
                score += 1.5
            if "api" in path_lower:
                score += 1.0

            if score > 0:
                scores.append((score, rel_path))

        # Ordena por score e pega os top N
        scores.sort(reverse=True)
        top_files = scores[:max_files]

        if not top_files:
            return "Nenhum arquivo relevante encontrado para essa query."

        # Monta o snippet de contexto
        parts = [
            f"# Arquivos relevantes do projeto PandaPoints ({len(top_files)} de {len(self._file_index)} total)",
            "",
        ]
        total_chars = 0

        for score, rel_path in top_files:
            content = self._file_index[rel_path]
            header = f"### {rel_path}  (relevância: {score:.1f})"
            block = f"{header}\n```\n{content[:2000]}\n```\n"  # max 2000 chars por arquivo

            if total_chars + len(block) > MAX_CONTEXT_CHARS:
                parts.append(f"### {rel_path}  [truncado por limite de contexto]")
                break

            parts.append(block)
            total_chars += len(block)

        return "\n".join(parts)

    # ─────────────────────────────────────────────
    # UTILITÁRIOS
    # ─────────────────────────────────────────────
    def show_map(self):
        """Imprime o mapa no terminal."""
        if self.map_file.exists():
            print(self.map_file.read_text(encoding="utf-8"))
        else:
            print("Mapa não gerado ainda. Rode indexer.index()")

    def stats(self) -> dict:
        """Retorna estatísticas do índice."""
        return {
            "arquivos": len(self._file_index),
            "extensoes": list({Path(p).suffix for p in self._file_index}),
            "tamanho_total": sum(len(c) for c in self._file_index.values()),
        }

    def summarize(self, max_chars: int = 8000) -> str:
        """
        Monta um contexto amplo com o máximo de arquivos possível
        para o comando 'resumir'. Prioriza arquivos menores e mais
        centrais (arquivos na raiz antes de subpastas).
        """
        if not self._file_index:
            return "⚠️  Projeto não indexado. Rode: indexar"

        # Ordena: arquivos na raiz primeiro, depois por tamanho crescente
        sorted_files = sorted(
            self._file_index.items(),
            key=lambda x: (x[0].count("/") + x[0].count("\\"), len(x[1]))
        )

        parts = [
            f"# Contexto completo do projeto para resumo",
            f"# {len(self._file_index)} arquivos indexados",
            "",
        ]

        # Sempre inclui o mapa completo
        if self.map_file.exists():
            parts.append("## Estrutura do projeto")
            parts.append(self.map_file.read_text(encoding="utf-8"))
            parts.append("")

        parts.append("## Arquivos de código")
        total_chars = sum(len(p) for p in parts)

        included = 0
        skipped = []

        for rel_path, content in sorted_files:
            # Limita cada arquivo a 1500 chars para caber mais arquivos
            snippet = content[:1500]
            block = f"### {rel_path}\n```\n{snippet}\n```\n"

            if total_chars + len(block) > max_chars:
                skipped.append(rel_path)
                continue

            parts.append(block)
            total_chars += len(block)
            included += 1

        if skipped:
            parts.append(f"\n# {len(skipped)} arquivo(s) omitido(s) por limite de contexto:")
            for p in skipped:
                parts.append(f"#   {p}")

        return "\n".join(parts)
