"""
bench_runner.py — ollama-bench integration for PandaAgent

Runs ollama-bench as a subprocess and reads the most recent result JSON
to determine the best model per task category (text / code).

Usage (internal):
    from bench_runner import BenchRunner
    runner = BenchRunner()
    result = runner.run()       # runs bench.py and returns parsed summary
    best   = runner.best_models()  # reads latest result without running
"""

import json
import os
import subprocess
import sys
from pathlib import Path

BENCH_DIR    = Path(__file__).parent.parent / "ollama-bench"
RESULTS_DIR  = BENCH_DIR / "results"
BENCH_SCRIPT = BENCH_DIR / "bench.py"


class BenchRunner:

    def run(self, models: list[str] | None = None) -> dict:
        """
        Runs bench.py as a subprocess and returns best_models() after completion.

        Parameters
        ----------
        models : list[str] | None
            Models to benchmark. If None, uses bench.py defaults.

        Returns
        -------
        dict
            {
              "ok": bool,
              "output": str,         # stdout/stderr from bench.py
              "best": {              # best model per category
                "text": str,
                "code": str,
              }
            }
        """
        if not BENCH_SCRIPT.exists():
            return {
                "ok": False,
                "output": f"bench.py not found at {BENCH_SCRIPT}",
                "best": {},
            }

        cmd = [sys.executable, str(BENCH_SCRIPT)]
        if models:
            cmd += ["--models"] + models

        print(f"\n  Running ollama-bench... (this may take a few minutes)")
        print(f"  Command: {' '.join(cmd)}\n")

        try:
            result = subprocess.run(
                cmd,
                capture_output=False,   # let output stream to terminal
                text=True,
                timeout=600,            # 10 min max
            )
            if result.returncode != 0:
                return {
                    "ok": False,
                    "output": f"bench.py exited with code {result.returncode}",
                    "best": {},
                }
        except subprocess.TimeoutExpired:
            return {"ok": False, "output": "Bench timed out after 10 minutes.", "best": {}}
        except Exception as e:
            return {"ok": False, "output": str(e), "best": {}}

        best = self.best_models()
        return {"ok": True, "output": "Bench complete.", "best": best}

    def best_models(self) -> dict:
        """
        Reads the most recent bench result and returns the best model per category
        based on avg_tokens_per_second (primary) and consistency_score (tiebreak).

        Returns
        -------
        dict  { "text": model_name, "code": model_name }
              Empty dict if no results available.
        """
        latest = self._latest_result()
        if not latest:
            return {}

        # Aggregate: category -> model -> list of summaries
        aggregated: dict[str, dict[str, list]] = {}
        for entry in latest.get("results", []):
            model    = entry.get("model", "")
            category = entry.get("category", "")
            summary  = entry.get("summary", {})
            if not model or not category or not summary:
                continue
            aggregated.setdefault(category, {}).setdefault(model, []).append(summary)

        def score(summaries: list) -> float:
            """Combined score: tps * consistency."""
            tps_vals  = [s.get("avg_tokens_per_second",  0) or 0 for s in summaries]
            cons_vals = [s.get("consistency_score",      1) or 1 for s in summaries]
            avg_tps   = sum(tps_vals)  / len(tps_vals)  if tps_vals  else 0
            avg_cons  = sum(cons_vals) / len(cons_vals) if cons_vals else 1
            return avg_tps * avg_cons

        best = {}
        for category, models in aggregated.items():
            ranked = sorted(models.items(), key=lambda kv: score(kv[1]), reverse=True)
            if ranked:
                best[category] = ranked[0][0]

        return best

    def summary_table(self) -> str:
        """
        Returns a human-readable summary table of the latest bench results.
        """
        latest = self._latest_result()
        if not latest:
            return "  No bench results found. Run 'bench' to generate them."

        ts = latest.get("timestamp", "")
        lines = [f"  Last run: {ts}", ""]
        lines.append(f"  {'Model':<42} {'Category':<8} {'tok/s':>7} {'ttft':>7} {'cons':>6}")
        lines.append("  " + "-" * 76)

        for entry in latest.get("results", []):
            model   = entry.get("model", "")
            cat     = entry.get("category", "")
            s       = entry.get("summary", {})
            if not s:
                continue
            tps  = f"{s['avg_tokens_per_second']:.1f}"  if s.get("avg_tokens_per_second")  else "—"
            ttft = f"{s['avg_time_to_first_token_s']:.3f}" if s.get("avg_time_to_first_token_s") else "—"
            cons = f"{s['consistency_score']:.2f}"      if s.get("consistency_score")      else "—"
            lines.append(f"  {model:<42} {cat:<8} {tps:>7} {ttft:>7} {cons:>6}")

        return "\n".join(lines)

    def _latest_result(self) -> dict | None:
        if not RESULTS_DIR.exists():
            return None
        files = sorted(RESULTS_DIR.glob("*.json"), reverse=True)
        files = [f for f in files if f.suffix == ".json"]
        if not files:
            return None
        try:
            with open(files[0], encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
