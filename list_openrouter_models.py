import sys
import urllib.request
import json

URL = "https://openrouter.ai/api/v1/models"

try:
    req = urllib.request.Request(URL, headers={"User-Agent": "Nubbix-Triage/1.0"})
    with urllib.request.urlopen(req, timeout=10) as response:
        data = json.loads(response.read().decode("utf-8"))
        
    models = data.get("data", [])
    free_models = []
    
    for m in models:
        model_id = m.get("id", "")
        pricing = m.get("pricing", {})
        prompt_cost = float(pricing.get("prompt", 1.0))
        comp_cost = float(pricing.get("completion", 1.0))
        
        # Filtrar modelos 100% gratuitos (slug :free o costo 0.0)
        if ":free" in model_id or (prompt_cost == 0.0 and comp_cost == 0.0):
            free_models.append(model_id)

    print("\n✅ Modelos 100% GRATUITOS activos en OpenRouter hoy:")
    print("=" * 60)
    for model_id in sorted(free_models):
        print(f"  • {model_id}")
    print("=" * 60)
    print(f"\nTotal de modelos gratuitos encontrados: {len(free_models)}")
    print("Podés usar cualquiera de ellos con:")
    print('  python src/main.py --provider openrouter --model "<MODEL_ID>" --query "..."\n')

except Exception as e:
    print(f"Error al consultar la API de OpenRouter: {e}")
    sys.exit(1)
