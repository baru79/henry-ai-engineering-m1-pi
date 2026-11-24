import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    print("Error: python-dotenv no está instalado. Ejecutá: pip install python-dotenv")
    sys.exit(1)

# Cargar variables de entorno desde .env
ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR / ".env")

try:
    from google import genai
except ImportError:
    print("Error: la librería 'google-genai' no está instalada en tu entorno.")
    print("Ejecutá: pip install google-genai")
    sys.exit(1)

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("Error: No se encontró GEMINI_API_KEY en el archivo .env")
    sys.exit(1)

try:
    client = genai.Client(api_key=api_key)
    models_page = client.models.list()

    # Filtrar solo modelos que soporten generateContent (texto/chat)
    text_models = []
    for m in models_page:
        name = m.name  # ej: "models/gemini-3.8-flash"
        # Excluir modelos de embedding y de investigación (no sirven para generateContent)
        if any(skip in name for skip in ["embedding", "deep-research", "antigravity"]):
            continue
        text_models.append(name.replace("models/", ""))  # quitar prefijo "models/"

    text_models_sorted = sorted(text_models)

    print("\n✅ Modelos disponibles en tu cuenta de Gemini (Google AI Studio):")
    print("=" * 60)
    for model_id in text_models_sorted:
        print(f"  • {model_id}")
    print("=" * 60)
    print(f"\nTotal de modelos encontrados: {len(text_models_sorted)}")
    print("Podés usar cualquiera de ellos con:")
    print('  python src/main.py --provider gemini --model "<MODEL_ID>" --query "..."\n')

except Exception as e:
    print(f"Error al consultar la API de Gemini: {e}")
    sys.exit(1)
