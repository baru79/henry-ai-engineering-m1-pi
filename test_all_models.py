"""
Script de verificación: prueba main.py con todos los modelos de texto de cada proveedor.
Uso: python test_all_models.py
"""
import subprocess
import json
import sys
from pathlib import Path

CWD = Path(__file__).resolve().parent
PYTHON = str(CWD / ".venv" / "bin" / "python")
QUERY = "Quiero agregar un usuario de solo lectura"

# ── Modelos a probar ────────────────────────────────────────────────────────
GROQ_MODELS = [
    "allam-2-7b",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "openai/gpt-oss-safeguard-20b",
    "qwen/qwen3.8-27b",
]

GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.5-pro",
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.6-flash",
    "gemini-3.7-flash",
    "gemini-3.8-flash",
    "gemini-4-argon",
    "gemini-4-carbon",
    "gemini-4-hydrogen",
    "gemini-4-neon",
    "gemma-4-26b-a4b-it",
    "gemma-4-31b-it",
]

# Excluimos los modelos de audio de OpenRouter (lyria, nemotron-super-vl que es multimodal puro)
OPENROUTER_MODELS = [
    "baidu/ernie-5.5-flash-preview:free",
    "dots-studio/dots-3-note-preview:free",
    "google/gemma-4-26b-a4b-it:free",
    "google/gemma-4-31b-it:free",
    "inclusionai/ling-3.2-flash:free",
    "liquid/lfm-3-1.7b:free",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "nvidia/nemotron-3.5-lightning:free",
    "particle-ai/particle-1:free",
    "recursive/flint-v1.0:free",
]

# ── Ejecutar prueba ─────────────────────────────────────────────────────────
def test(provider: str, model: str) -> dict:
    cmd = [
        PYTHON, "src/main.py",
        "--provider", provider,
        "--model", model,
        "--query", QUERY,
        "--no-cache",
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=CWD)
        stdout = r.stdout.strip()
        stderr = r.stderr.strip()

        if "[ERROR FATAL]" in stderr:
            detail = stderr.split("[ERROR FATAL]:")[-1].strip()[:160]
            return {"status": "❌ FAIL", "detail": detail}

        try:
            json.loads(stdout)
            return {"status": "✅ OK", "detail": ""}
        except json.JSONDecodeError:
            return {"status": "⚠️  BAD JSON", "detail": stdout[:100]}

    except subprocess.TimeoutExpired:
        return {"status": "⏱️  TIMEOUT", "detail": ">60s"}
    except Exception as e:
        return {"status": "❌ ERROR", "detail": str(e)[:160]}


# ── Correr todos ─────────────────────────────────────────────────────────────
all_tests = (
    [("groq", m) for m in GROQ_MODELS]
    + [("gemini", m) for m in GEMINI_MODELS]
    + [("openrouter", m) for m in OPENROUTER_MODELS]
)

results = []
for provider, model in all_tests:
    print(f"  Testing {provider:12s} | {model} ...", end=" ", flush=True)
    res = test(provider, model)
    print(res["status"])
    results.append({"provider": provider, "model": model, **res})

# ── Reporte final ─────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print(f"{'PROVIDER':<12} {'MODEL':<45} {'STATUS'}")
print("=" * 70)
for r in results:
    line = f"{r['provider']:<12} {r['model']:<45} {r['status']}"
    if r["detail"]:
        line += f"\n{'':>12}   ↳ {r['detail']}"
    print(line)
print("=" * 70)

ok = sum(1 for r in results if r["status"] == "✅ OK")
fail = len(results) - ok
print(f"\n✅ OK: {ok}  |  ❌/⚠️/⏱️: {fail}  |  Total: {len(results)}\n")
