import os
import sys
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR / ".env")

try:
    from groq import Groq
except ImportError:
    print("Error: la librería 'groq' no está instalada en tu entorno.")
    sys.exit(1)

api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    print("Error: No se encontró GROQ_API_KEY en el archivo .env")
    sys.exit(1)

try:
    client = Groq(api_key=api_key)
    models = client.models.list()
    print("\n✅ Modelos disponibles en tu cuenta de Groq:")
    for m in sorted(models.data, key=lambda x: x.id):
        print(f"  • {m.id}")
    print("\nPodés configurar cualquiera de estos en tu archivo .env en LLM_MODEL o con --model <nombre>\n")
except Exception as e:
    print(f"Error al consultar la API de Groq: {e}")
