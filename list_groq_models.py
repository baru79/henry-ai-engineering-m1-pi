import os
import argparse
import sys
from pathlib import Path

# ---- Argument parsing ---------------------------------------------------
parser = argparse.ArgumentParser(description="List Groq models from your account")
parser.add_argument("--env", type=str, default=".env", help="Path to the .env file (default: .env)")
parser.add_argument("--model", type=str, help="Show details for a specific model ID")
parser.add_argument("--json", action="store_true", help="Output the model list as JSON")
parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
args = parser.parse_args()

try:
    from dotenv import load_dotenv
except ImportError:
    import sys
    print("Error: python-dotenv no está instalado.")
    sys.exit(1)

ROOT_DIR = Path(__file__).resolve().parent
import json

# Load environment file (customizable via --env flag)
load_dotenv(args.env)

if args.verbose:
    print(f"[VERBOSE] Using env file: {args.env}")


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
