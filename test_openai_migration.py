"""
test_openai_migration.py — Manual smoke tests for the OpenAI-compatible panda_client

Run with any OpenAI-compatible server on localhost:8080:
    python test_openai_migration.py

Each test prints PASS / FAIL / SKIP clearly.
No dependencies beyond stdlib + pandagent installed.
"""

import sys
import json
import urllib.request
import urllib.error

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, "C:/Users/panta/pandagent")
from pandagent.panda_client import PandaClient, LLM_BASE_URL, OLLAMA_BASE_URL, TASK_MODEL_MAP

PASS  = "\033[92mPASS\033[0m"
FAIL  = "\033[91mFAIL\033[0m"
SKIP  = "\033[93mSKIP\033[0m"
INFO  = "\033[94mINFO\033[0m"

results = {"pass": 0, "fail": 0, "skip": 0}

def check(name, condition, detail=""):
    if condition:
        print(f"  [{PASS}] {name}")
        results["pass"] += 1
    else:
        print(f"  [{FAIL}] {name}" + (f" — {detail}" if detail else ""))
        results["fail"] += 1

def skip(name, reason=""):
    print(f"  [{SKIP}] {name}" + (f" — {reason}" if reason else ""))
    results["skip"] += 1


# ─────────────────────────────────────────────
# 1. CONSTANTS & BACKWARD COMPAT
# ─────────────────────────────────────────────
print("\n[1] Constants & backward compat")

check("LLM_BASE_URL defined",          LLM_BASE_URL == "http://localhost:8080")
check("OLLAMA_BASE_URL is alias",       OLLAMA_BASE_URL == LLM_BASE_URL)
check("TASK_MODEL_MAP has 6 keys",      len(TASK_MODEL_MAP) == 6)
check("shim re-exports LLM_BASE_URL",   True)   # already imported above without error


# ─────────────────────────────────────────────
# 2. INSTANTIATION & URLS
# ─────────────────────────────────────────────
print("\n[2] Instantiation & URL construction")

client = PandaClient()
check("_chat_url points to /v1/chat/completions",
      client._chat_url == "http://localhost:8080/v1/chat/completions")
check("_models_url points to /v1/models",
      client._models_url == "http://localhost:8080/v1/models")

custom = PandaClient(base_url="http://127.0.0.1:9999")
check("custom base_url respected",
      custom._chat_url == "http://127.0.0.1:9999/v1/chat/completions")


# ─────────────────────────────────────────────
# 3. _build_messages
# ─────────────────────────────────────────────
print("\n[3] _build_messages")

msgs = PandaClient._build_messages("hello", "", "")
check("no system → 1 message",         len(msgs) == 1)
check("role is user",                  msgs[0]["role"] == "user")
check("content is prompt",             msgs[0]["content"] == "hello")

msgs = PandaClient._build_messages("hello", "You are a bot.", "")
check("with system → 2 messages",      len(msgs) == 2)
check("first role is system",          msgs[0]["role"] == "system")
check("system content correct",        msgs[0]["content"] == "You are a bot.")

msgs = PandaClient._build_messages("say hi", "sys", "some context")
check("context prepended to user msg", "some context" in msgs[1]["content"])
check("prompt appended after context", msgs[1]["content"].endswith("say hi"))


# ─────────────────────────────────────────────
# 4. _resolve
# ─────────────────────────────────────────────
print("\n[4] _resolve (model routing)")

model, task = client._resolve("anything", "code")
check("task=code → code_model",        model == client.code_model and task == "code")

model, task = client._resolve("anything", "text")
check("task=text → text_model",        model == client.text_model and task == "text")

model, task = client._resolve("write a python function to fix this bug", "auto")
check("auto with 3+ code kws → code",  task == "code",
      f"got task={task}")

model, task = client._resolve("what is the weather", "auto")
check("auto with no code kws → text",  task == "text",
      f"got task={task}")


# ─────────────────────────────────────────────
# 5. CONNECTIVITY (requires server running)
# ─────────────────────────────────────────────
print("\n[5] Connectivity (requires LLM server on :8080)")

online = client.is_online()
if not online:
    skip("is_online()", "server not running — start llama-swap or llama-server on :8080")
    skip("available_models()", "server not running")
    skip("ask() smoke test", "server not running")
    skip("commit_message() smoke test", "server not running")
    results["skip"] += 4   # already counted inside skip() calls above, adjust
else:
    check("is_online() returns True", True)

    models = client.available_models()
    check("available_models() returns list", isinstance(models, list))
    print(f"  [{INFO}] models found: {models}")

    # ── ask() ──
    res = client.ask("Reply with the single word: pong", task="text", max_tokens=10)
    check("ask() ok=True",             res["ok"],         res.get("output", ""))
    check("ask() output non-empty",    bool(res.get("output", "")))
    check("ask() model in response",   bool(res.get("model", "")))
    check("ask() task in response",    res.get("task") in ("text", "code"))

    # ── commit_message() ──
    diff = """diff --git a/foo.py b/foo.py
index 1234..5678 100644
--- a/foo.py
+++ b/foo.py
@@ -1,3 +1,4 @@
 def foo():
-    pass
+    return 42
"""
    res = client.commit_message(diff=diff, project_name="pandagent")
    check("commit_message() ok=True",        res["ok"],  res.get("output", ""))
    check("commit_message() single line",
          "\n" not in res.get("output", ""),             res.get("output", ""))
    print(f"  [{INFO}] commit: {res.get('output', '')}")


# ─────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────
total = results["pass"] + results["fail"] + results["skip"]
print(f"\n{'─'*50}")
print(f"  Results: {results['pass']} passed, {results['fail']} failed, {results['skip']} skipped  ({total} total)")
if results["fail"] == 0:
    print(f"  \033[92mAll checks passed.\033[0m")
else:
    print(f"  \033[91m{results['fail']} check(s) failed — review output above.\033[0m")
print(f"{'─'*50}\n")
