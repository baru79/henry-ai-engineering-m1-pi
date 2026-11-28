# Guía técnica y decisiones de arquitectura

> Documento de onboarding para Nubbix Triage AI.
> Audiencia: personas que ven el repositorio por primera vez y necesitan entenderlo, ejecutarlo y extenderlo sin romper el contrato del producto.

---

## 1. Para qué sirve este documento

El `README.md` explica **qué hace el producto** y cómo usarlo. Este documento explica **cómo está construido por dentro**, qué responsabilidad tiene cada archivo y por qué se tomaron las decisiones técnicas principales.

La idea es que una persona nueva pueda responder estas preguntas en menos de una hora:

1. ¿Cuál es el camino que sigue un ticket desde la CLI hasta el JSON final?
2. ¿Dónde se cambia de proveedor de LLM?
3. ¿Dónde se define el contrato de salida?
4. ¿Cómo se protegen las entradas y las salidas?
5. ¿Cómo se mide accuracy, latencia y costo?
6. ¿Qué partes son deliberadamente simples y cuáles son deuda técnica?

---

## 2. Modelo mental

Nubbix Triage AI es un **CLI síncrono** que procesa un ticket de soporte por ejecución. No es una API web ni un servicio con base de datos: es un MVP reproducible, pensado para demostrar el pipeline completo y para correr evaluaciones empíricas contra proveedores gratuitos.

El pipeline completo, con todos sus componentes, se describe en [Arquitectura del Sistema](README.md#-arquitectura-del-sistema) del README.

La regla de diseño más importante es: **la lógica de negocio no conoce ningún SDK de LLM**. `TriageService` orquesta interfaces; los adaptadores concretos viven en `src/llm/`.

---

## 3. Flujo completo de una consulta

### 3.1 Entrada

`src/main.py` usa `argparse` para leer:

- `--query` / `-q`: texto del ticket.
- `--provider` / `-p`: `groq`, `gemini` u `openrouter`.
- `--model` / `-m`: modelo específico.
- `--prompt-version` / `-v`: `v1_zero_shot` o `v2_few_shot`.
- `--no-cache`: desactiva la caché para esa ejecución.

Si no se pasa `--query`, la CLI pide el texto de forma interactiva. El JSON del contrato se imprime por `stdout`; el resumen de métricas se imprime por `stderr` para no contaminar el JSON cuando se usa una pipe como `jq`.

### 3.2 Guardrail de entrada

`InputGuard.validate()` revisa:

- que el texto no esté vacío;
- que tenga al menos 3 caracteres y no más de 2500;
- que no coincida con patrones conocidos de prompt injection, jailbreak, exfiltración, SQL injection, comandos o XSS.

Si la entrada se rechaza, se devuelve un `TriageResponse` válido con `confidence: 0.0`, `category: "other"` y acciones de auditoría. **No se llama al LLM**, por lo que el costo es cero.

### 3.3 Caché

`MD5ResponseCache` normaliza la consulta (minúsculas y espacios colapsados) y calcula:

```text
MD5(prompt_version + ":" + normalized_query)
```

La versión del prompt forma parte de la clave para que un cambio de prompt no devuelva respuestas viejas. Si hay hit, se devuelve la respuesta guardada y se registra una métrica con `cached: true`, cero tokens y costo cero.

### 3.4 Carga del prompt

`PromptLoader.load()` lee `prompts/<version>.yaml`, valida que exista y construye un `PromptTemplate` con:

- `version`;
- `description`;
- `system_prompt`;
- `user_template`.

El render es deliberadamente simple: `user_template.replace("{query}", query.strip())`. No se usa Jinja ni un motor de templates para mantener el proyecto liviano y auditable.

### 3.5 Selección del proveedor

`LLMFactory.create()` busca el proveedor en un registro interno:

```python
{
    "groq": GroqProvider,
    "gemini": GeminiProvider,
    "openrouter": OpenRouterProvider,
}
```

Antes de instanciar, valida que exista la API key correspondiente en `Settings`. Si no se especifica modelo, se usa el modelo configurado en `.env`; si tampoco existe, cada proveedor usa su `get_default_model()`.

### 3.6 Llamada al LLM y retry

Cada proveedor hereda de `LLMProvider` e implementa `_call_api()`, que devuelve:

```python
(texto_generado, prompt_tokens, completion_tokens)
```

`LLMProvider.generate()` mide la latencia, suma tokens y devuelve un `LLMResponse` uniforme. `TriageService` intenta validar la respuesta con Pydantic. Si el modelo devuelve markdown, JSON inválido o un schema incorrecto, se reintenta con un mensaje adicional que incluye el error exacto. El máximo de intentos es `MAX_RETRIES + 1` (por defecto, 3 intentos).

Los errores de API no se reintentan: se consideran irrecuperables en este MVP y se propagan como `LLMProviderError`.

### 3.7 Guardrail de salida

`OutputGuard.validate()` revisa `answer` y `actions`:

- si detecta patrones de API keys (`gsk_`, `sk-`, `AIzaSy`), reemplaza toda la respuesta por una respuesta segura y genera acciones de alerta;
- si detecta frases internas del system prompt, reemplaza la respuesta por una versión neutral y baja la confianza;
- si no detecta nada, deja la respuesta intacta.

### 3.8 Observabilidad

`MetricsLogger.log_request()` calcula el costo con `PricingCalculator`, crea un `MetricRecord` y agrega una línea JSON a `data/metrics.jsonl`. El timestamp se genera en UTC.

### 3.9 Salida

La CLI imprime el `TriageResponse` serializado con `model_dump()` y un resumen de métricas. El contrato de salida es siempre el mismo, incluso cuando el ticket fue bloqueado o cuando el LLM falló después de los reintentos.

---

## 4. Mapa del repositorio

```text
PI/
├── ARCHITECTURE.md              # Este documento
├── README.md                    # Documentación de producto, uso y resultados
├── requirements.txt             # Dependencias mínimas
├── .env.example                 # Plantilla de configuración, sin secretos
├── .gitignore                   # Exclusión de credenciales, entorno y datos locales
├── data/
│   ├── metrics.jsonl            # Evidencia de observabilidad versionada (append-only)
│   └── cache.json               # Caché local generada; ignorada por Git
├── evals/
│   ├── dataset.jsonl            # 32 casos etiquetados, 8 por categoría
│   ├── adversarial.jsonl        # 10 ataques documentados
│   └── runner.py                # Runner de benchmark, comparación y adversarial
├── prompts/
│   ├── v1_zero_shot.yaml        # Baseline sin ejemplos
│   └── v2_few_shot.yaml         # Prompt productivo con few-shot y reglas
└── src/
    ├── __init__.py              # Marca el paquete src
    ├── main.py                  # CLI y orquestador TriageService
    ├── config.py                # Configuración centralizada
    ├── models.py                # Contratos Pydantic
    ├── cache.py                 # Caché MD5 persistente
    ├── prompt_loader.py         # Carga de prompts YAML
    ├── guardrails/
    │   ├── __init__.py          # Exporta los guards
    │   ├── input_guard.py       # Seguridad de entrada
    │   └── output_guard.py      # Seguridad de salida
    ├── llm/
    │   ├── __init__.py          # Exporta la interfaz y la factory
    │   ├── base.py              # ABC LLMProvider y LLMResponse
    │   ├── factory.py           # Registro y creación de proveedores
    │   ├── groq_provider.py     # Adaptador Groq
    │   ├── gemini_provider.py   # Adaptador Google AI Studio
    │   └── openrouter_provider.py # Adaptador OpenRouter
    └── observability/
        ├── __init__.py          # Exporta logger y pricing
        ├── logger.py            # Escritura JSONL
        └── pricing.py           # Cálculo de costos estimados
```

Archivos locales que existen en una máquina de desarrollo pero **no forman parte del repositorio**:

- `.env`: secretos reales; ignorado.
- `.venv/`: entorno virtual; ignorado.
- `.vscode/settings.json`: configuración local del editor; ignorado.
- `data/cache.json`: caché generada por ejecuciones; ignorada.
- `scripts_locales/`: utilidades auxiliares del autor; ignoradas.
- `enunciado/`: material original del challenge; ignorado.
- `.DS_Store`: basura de macOS; ignorada.

---

## 5. Guía archivo por archivo

### 5.1 Raíz del repositorio

#### `README.md`

Es la puerta de entrada al proyecto. Contiene:

- contexto de negocio de Nubbix y objetivos;
- arquitectura visual en Mermaid;
- estructura del repositorio;
- instalación, configuración y ejemplos de CLI;
- comparación empírica de prompts v1 vs v2;
- explicación de evals, guardrails, observabilidad y caché;
- checklist de cumplimiento.

Es la fuente de verdad para usuarios y evaluadores. Si cambia una decisión de producto, una ruta o un comando, este archivo debe actualizarse.

#### `ARCHITECTURE.md`

Este documento. No reemplaza al README: lo complementa con el detalle interno, las decisiones y las limitaciones.

#### `requirements.txt`

Declara las dependencias mínimas:

- `pydantic`: contrato y validación;
- `python-dotenv`: carga de `.env`;
- `pyyaml`: lectura de prompts;
- `groq`: SDK de Groq;
- `google-genai`: SDK oficial de Gemini;
- `openai`: SDK usado contra el endpoint compatible de OpenRouter.

No incluye `pytest`, `fastapi`, `langchain` ni frameworks de agentes porque el proyecto se resolvió con la biblioteca estándar y SDKs directos.

#### `.env.example`

Plantilla de configuración. Documenta:

- proveedor y modelo por defecto;
- las tres API keys gratuitas;
- versión de prompt;
- reintentos;
- caché;
- ruta de métricas.

Nunca contiene secretos reales. El archivo `.env` se crea a partir de esta plantilla y está ignorado por Git.

#### `.gitignore`

Protege el repositorio de:

- entornos virtuales y bytecode;
- `.env` con credenciales;
- `data/cache.json`;
- logs y `.DS_Store`;
- configuración local de IDE;
- `scripts_locales/` y `enunciado/`.

`data/metrics.jsonl` se versiona a propósito como evidencia de observabilidad.

### 5.2 Datos y evaluaciones

#### `data/metrics.jsonl`

Log append-only en formato JSONL. Cada línea es un `MetricRecord` serializado. Se usa para auditar latencia, tokens, costo, proveedor, modelo, caché y estado.

Al momento de escribir esta guía hay 207 registros de ejemplo y de corridas de prueba. **No es una base de datos**: no tiene índices, rotación ni bloqueo entre procesos. Las corridas de `evals/runner.py` también escriben aquí porque usan `TriageService`.

#### `data/cache.json`

Caché local generada automáticamente. No se versiona. Su estructura es:

```json
{
  "<hash_md5>": {
    "query": "texto original",
    "prompt_version": "v2_few_shot",
    "response": { "...": "TriageResponse serializado" }
  }
}
```

Se puede borrar sin romper nada: la próxima ejecución la reconstruye.

#### `evals/dataset.jsonl`

Dataset balanceado de 32 casos: 8 de `billing`, 8 de `technical`, 8 de `account` y 8 de `other`. Cada línea tiene:

- `id`: identificador;
- `query`: entrada;
- `expected_category`: etiqueta esperada;
- `notes`: justificación o aclaración del caso.

Es un dataset curado para el challenge, no una muestra estadística de producción.

#### `evals/adversarial.jsonl`

10 casos maliciosos con:

- `id`;
- `attack_type`;
- `query`;
- `expected_behavior`.

Cubre prompt injection directa e indirecta, DAN, exfiltración de credenciales, SQL injection, command injection, roleplay de autoridad, generación de malware, fuga por traducción y XSS.

#### `evals/runner.py`

Runner ejecutable sin framework de testing. Funciones principales:

- `load_jsonl()`: carga datasets.
- `run_benchmark()`: corre todos los casos con un prompt y proveedor; calcula accuracy global y por categoría, latencia promedio, tokens y costo.
- `run_adversarial_suite()`: corre los 10 ataques y decide si fueron mitigados.
- `print_report()`: imprime el reporte estándar.
- `print_comparison()`: compara v1 vs v2.

Flags:

- `--prompt-version`;
- `--provider`;
- `--model`;
- `--dataset`;
- `--run-adversarial`;
- `--compare-prompts`.

El runner no usa mocks: llama al LLM real. Por eso requiere red, API key y puede costar tiempo/dinero. Es una evaluación empírica end-to-end, no un test unitario.

### 5.3 Prompts

#### `prompts/v1_zero_shot.yaml`

Baseline. Define el rol de soporte N1, las cuatro categorías y el contrato JSON, pero no incluye ejemplos. Se usa para medir el efecto de agregar context engineering.

#### `prompts/v2_few_shot.yaml`

Prompt productivo. Agrega:

- definiciones más precisas de cada categoría;
- regla crítica para separar `technical` de `billing` cuando hay pasarelas de pago o APIs;
- regla de licencias: comprar cupos es `account`, no `other`;
- regla anti-alucinación para no inventar precios ni descuentos;
- blindaje contra jailbreaks;
- cuatro ejemplos canónicos (uno por categoría);
- contrato JSON explícito.

La decisión de usar v2 se justifica con evals: 100% de accuracy frente a 96.88% de v1, a costa de más latencia y tokens.

### 5.4 Código fuente

#### `src/__init__.py`

Marca `src` como paquete Python. No contiene lógica.

#### `src/main.py`

Es el corazón del proyecto y el mejor punto de entrada para leer el código. Contiene dos responsabilidades:

1. `TriageService`: orquesta el pipeline completo y puede ser reutilizado por la CLI o por `evals/runner.py`.
2. `main()`: define la CLI, parsea argumentos, pide la query si falta, imprime JSON y métricas.

Métodos importantes de `TriageService`:

- `_extract_json_block()`: elimina bloques de código markdown etiquetados como JSON si el modelo los agrega.
- `_parse_and_validate()`: parsea JSON y valida con `TriageResponse`.
- `process_ticket()`: ejecuta guardrail, caché, prompt, LLM, retry, output guard, caché y logging.

`main.py` también inserta la raíz del proyecto en `sys.path` para permitir `python src/main.py` sin instalar el paquete.

#### `src/config.py`

Centraliza la configuración:

- rutas de `prompts/`, `data/` y `evals/`;
- proveedor y modelo;
- API keys;
- versión de prompt;
- reintentos;
- caché;
- ruta de métricas.

`load_dotenv()` se ejecuta al importar el módulo. `Settings` es una clase simple con atributos de clase; no usa `pydantic-settings` para mantener la dependencia al mínimo.

`get_api_key()` y `validate_provider_keys()` evitan que la factory intente usar un proveedor sin credenciales.

#### `src/models.py`

Define los contratos:

- `TicketCategory`: `Literal["billing", "technical", "account", "other"]`.
- `TriageResponse`: `answer`, `confidence` (0.0 a 1.0), `category`, `actions` (mínimo una).
- `MetricRecord`: timestamp, query, provider, model, tokens, latencia, costo, cached y status.

Este archivo es la frontera entre el LLM y el resto del sistema. Si el modelo devuelve algo que no cumple, Pydantic lanza `ValidationError` y se activa el retry.

#### `src/cache.py`

Implementa `MD5ResponseCache`:

- normaliza la query;
- genera la clave con `prompt_version + ":" + query`;
- carga y persiste `data/cache.json`;
- expone `get()`, `set()` y `clear()`;
- crea una instancia singleton `response_cache`.

Decisiones:

- MD5 es suficiente como clave de búsqueda, no como mecanismo de seguridad.
- La versión del prompt está en la clave para invalidar respuestas viejas.
- No hay TTL ni límite de tamaño: se priorizó simplicidad para el MVP.
- La persistencia reescribe el JSON completo y silencia errores; no es apta para escritura concurrente.

#### `src/prompt_loader.py`

Define `PromptTemplate` y `PromptLoader`.

- `PromptTemplate` valida los campos del YAML.
- `render_user_prompt()` reemplaza `{query}`.
- `PromptLoader.list_available_prompts()` lista los YAML disponibles.
- `PromptLoader.load()` carga el archivo pedido o el configurado por defecto.

Si la versión no existe, el error incluye las versiones disponibles. Es una decisión de DX: el usuario no tiene que adivinar qué prompts hay.

#### `src/guardrails/__init__.py`

Exporta `InputGuard`, `InputGuardResult`, `OutputGuard` y `OutputGuardResult` para que `main.py` importe desde un solo lugar.

#### `src/guardrails/input_guard.py`

Contiene `InputGuardResult` e `InputGuard`.

`InputGuard` es heurístico y determinista:

- longitud mínima y máxima;
- patrones regex para ataques conocidos;
- bloqueo antes de gastar tokens;
- respuesta segura que mantiene el contrato.

No pretende ser un detector semántico perfecto. Su objetivo es frenar los ataques documentados y dar una primera capa de defensa a costo cero.

#### `src/guardrails/output_guard.py`

Contiene `OutputGuardResult` y `OutputGuard`.

Revisa `answer` y `actions`:

- patrones de credenciales;
- firmas de frases internas del prompt.

Si detecta un problema, reemplaza la respuesta completa por una versión segura. Es una decisión conservadora: se prioriza no filtrar datos antes que preservar la respuesta original.

#### `src/llm/__init__.py`

Exporta `LLMProvider`, `LLMResponse`, `LLMProviderError` y `LLMFactory`.

#### `src/llm/base.py`

Define el contrato de los proveedores:

- `LLMResponse`: respuesta normalizada.
- `LLMProviderError`: error de proveedor.
- `LLMProvider`: clase abstracta con `get_default_model()`, `provider_name`, `_call_api()` y `generate()`.

`generate()` es el punto donde se mide latencia y se normalizan tokens. Gracias a esto, `TriageService` no sabe si el proveedor es Groq, Gemini u OpenRouter.

#### `src/llm/factory.py`

Implementa el patrón Factory con un registro de proveedores. Responsabilidades:

- resolver el nombre del proveedor;
- validar que exista;
- validar la API key;
- instanciar el adaptador con el modelo elegido.

Agregar un proveedor nuevo requiere tocar este registro y crear el adaptador.

#### `src/llm/groq_provider.py`

Adaptador de Groq. Usa `Groq` SDK, `temperature=0.0`, `max_tokens=600` y `response_format={"type": "json_object"}`. El límite de 600 tokens evita problemas de preasignación de cuota y es suficiente para el contrato.

Modelo por defecto: `openai/gpt-oss-120b`.

#### `src/llm/gemini_provider.py`

Adaptador de Google AI Studio con el SDK `google-genai`. Usa `system_instruction`, `response_mime_type="application/json"` y `temperature=0.0`. Incluye un mapeo de nombres legados (`gemini-1.5-flash`, `gemini-2.0-flash`) a modelos actuales.

Modelo por defecto en código: `gemini-3.8-flash`. El README recomienda `gemini-3.1-flash-lite` o `gemini-3.5-flash-lite`, y `.env.example` menciona `gemini-3.8-flash`; esta diferencia se documenta en la sección de deuda técnica.

#### `src/llm/openrouter_provider.py`

Adaptador de OpenRouter usando el SDK de OpenAI contra `https://openrouter.ai/api/v1`. Agrega headers `HTTP-Referer` y `X-Title`, que OpenRouter usa para atribución. Modelo por defecto: `openrouter/free`, el meta-router gratuito.

La lista de modelos gratuitos cambia con el tiempo; el docstring y el README documentan los verificados al momento de la entrega.

#### `src/observability/__init__.py`

Exporta `PricingCalculator`, `MODEL_PRICING_PER_MILLION` y `MetricsLogger`.

#### `src/observability/pricing.py`

Tabla de tarifas por millón de tokens y cálculo:

```text
costo = (prompt_tokens * input_rate + completion_tokens * output_rate) / 1_000_000
```

Si `cached=True`, devuelve 0.0. Si el modelo no está en la tabla, usa la tarifa `default` (`0.10 / 0.30` por millón). Es una estimación auditable, no una factura real.

#### `src/observability/logger.py`

`MetricsLogger.log_request()`:

- crea el directorio si no existe;
- calcula el costo;
- arma el `MetricRecord`;
- agrega una línea JSON al archivo;
- devuelve el registro.

`load_metrics()` permite leer y validar los registros existentes. No hay rotación ni bloqueo de archivo.

### 5.5 Configuración local

#### `.vscode/settings.json`

Archivo local que apunta el intérprete de Python a `.venv/bin/python`. Está ignorado por Git y no afecta la ejecución del proyecto.

#### `scripts_locales/`

Utilidades del autor para listar modelos y probar proveedores. No se publican porque dependen de APIs externas cambiantes y no son necesarias para ejecutar el servicio.

#### `enunciado/`

Material original del challenge. Se mantiene fuera del repositorio para no mezclar consigna con implementación.

---

## 6. Contratos de datos

### 6.1 `TriageResponse`

```json
{
  "answer": "string",
  "confidence": 0.0,
  "category": "billing | technical | account | other",
  "actions": ["string"]
}
```

Reglas:

- `answer` es obligatorio;
- `confidence` está entre 0.0 y 1.0;
- `category` es un `Literal`, no un string libre;
- `actions` debe tener al menos un elemento.

### 6.2 `MetricRecord`

```json
{
  "timestamp": "ISO 8601 UTC",
  "query": "string",
  "provider": "groq | gemini | openrouter | guardrail",
  "model": "string",
  "prompt_tokens": 0,
  "completion_tokens": 0,
  "total_tokens": 0,
  "latency_seconds": 0.0,
  "cost_usd": 0.0,
  "cached": false,
  "status": "success | retry_success | blocked | invalid_input"
}
```

`total_tokens` se calcula como `prompt_tokens + completion_tokens`. `cost_usd` se redondea a 7 decimales.

### 6.3 `LLMResponse`

Contrato interno que devuelve cualquier proveedor:

- `content`;
- `prompt_tokens`;
- `completion_tokens`;
- `total_tokens`;
- `latency_seconds`;
- `model`;
- `provider`.

### 6.4 `InputGuardResult` y `OutputGuardResult`

`InputGuardResult`:

- `is_valid`;
- `sanitized_query`;
- `is_adversarial`;
- `reason`.

`OutputGuardResult`:

- `is_safe`;
- `sanitized_response`;
- `reason`.

### 6.5 `PromptTemplate`

- `version`;
- `description`;
- `system_prompt`;
- `user_template`.

---

## 7. Decisiones técnicas y por qué

### 7.1 CLI síncrona en lugar de API web

**Decisión:** el producto se entrega como CLI ejecutable y no como servicio HTTP.

**Motivo:** el challenge prioriza el pipeline de triage, la calidad del prompt, las evals y la observabilidad. Una CLI elimina autenticación, despliegue, concurrencia y infraestructura, y hace que cualquier evaluador pueda correr el proyecto en segundos.

**Trade-off:** no hay endpoint HTTP, ni cola, ni procesamiento batch. Para 400 tickets/día habría que agregar una capa de servicio, concurrencia y control de rate limits.

### 7.2 Pydantic como contrato ejecutable

**Decisión:** toda salida del LLM se valida con `TriageResponse`; las métricas también son un modelo Pydantic.

**Motivo:** el contrato JSON es parte central del producto. Pydantic permite validar tipos, rangos y categorías permitidas, y produce errores claros que alimentan el retry.

**Trade-off:** un LLM puede devolver JSON semánticamente correcto pero inválido para el schema; en ese caso se reintenta o se cae a una respuesta defensiva.

### 7.3 Arquitectura en capas y principio Open/Closed

**Decisión:** separar orquestación, contrato, prompting, proveedores, guardrails, caché y observabilidad.

**Motivo:** permitir cambiar un proveedor o un prompt sin tocar la lógica de negocio. `TriageService` depende de abstracciones, no de SDKs.

**Trade-off:** hay más archivos y algo de indirección. Para un script de 100 líneas sería excesivo; para un proyecto que debe evaluar varios proveedores y sobrevivir a cambios de free tiers, es la opción correcta.

### 7.4 Patrón Factory para proveedores

**Decisión:** `LLMFactory` mantiene un registro de adaptadores y valida la API key antes de instanciar.

**Motivo:** agregar un proveedor nuevo es una operación localizada. La CLI y las evals no necesitan conocer los detalles.

**Trade-off:** el registro es estático; un proveedor nuevo requiere editar código, no solo configuración.

### 7.5 Prompts versionados en YAML

**Decisión:** los prompts viven en `prompts/*.yaml`, no hardcodeados en Python.

**Motivo:** permiten comparar versiones, auditar cambios y cambiar el prompt sin recompilar lógica. El formato YAML es legible y no requiere dependencias pesadas.

**Trade-off:** el render es un simple `replace`, sin condicionales ni loops. Si el prompting se vuelve más complejo, habría que evaluar Jinja2 o un motor de templates.

### 7.6 Baseline zero-shot y versión final few-shot

**Decisión:** mantener `v1_zero_shot` como baseline y usar `v2_few_shot` como versión productiva.

**Motivo:** la comparación empírica muestra que v2 pasa de 96.88% a 100% de accuracy, corrigiendo el caso de licencias que v1 clasificaba como `other`. Además, v2 incorpora reglas de desambiguación, anti-alucinación y seguridad.

**Trade-off:** v2 consume más tokens y tarda más (6.810 s vs 2.139 s de promedio en la corrida documentada). El costo por ticket sigue siendo bajo, pero no es gratis en latencia.

### 7.7 Retry con feedback correctivo

**Decisión:** reintentar solo ante errores de parsing o validación, agregando el error exacto al prompt.

**Motivo:** es la falla más común de los LLMs en un contrato JSON. El feedback correctivo aumenta la probabilidad de que el segundo intento cumpla el schema.

**Trade-off:** cada reintento cuesta tokens y latencia. Los errores de API no se reintentan para no multiplicar fallas de cuota o autenticación.

### 7.8 Defensa en capas

**Decisión:** combinar guardrail de entrada, reglas en el prompt, guardrail de salida y suite adversarial.

**Motivo:** ninguna capa es suficiente por sí sola. El guardrail de entrada bloquea ataques conocidos a costo cero; el prompt contiene comportamientos no capturados por regex; el guardrail de salida actúa como última barrera; la suite adversarial mide el resultado.

**Trade-off:** los regex pueden generar falsos positivos y falsos negativos. No hay un clasificador semántico ni un LLM juez.

### 7.9 Caché exacta MD5, no caché semántica

**Decisión:** cachear por hash exacto de la consulta normalizada y la versión del prompt.

**Motivo:** el 60% de los tickets son repetitivos y la caché exacta es determinista, barata y fácil de auditar. No requiere embeddings, base vectorial ni umbral de similitud.

**Trade-off:** dos consultas equivalentes con distinta redacción no comparten caché. No hay TTL ni límite de tamaño. MD5 no es criptográfico, pero se usa solo como clave.

### 7.10 Observabilidad con JSONL y tabla de precios

**Decisión:** registrar cada request en `data/metrics.jsonl` y calcular costo con una tabla local.

**Motivo:** no hace falta una base de datos para el MVP. JSONL es legible, versionable y fácil de procesar con `jq` o Python. La tabla de precios hace el costo reproducible y auditable.

**Trade-off:** no hay dashboard, índice, rotación ni agregaciones en tiempo real. La tarifa es una estimación; los free tiers reales pueden ser cero o cambiar.

### 7.11 Evals como script end-to-end

**Decisión:** usar `evals/runner.py` en lugar de pytest con mocks.

**Motivo:** lo que se quiere medir es el comportamiento real de un LLM con un prompt y un proveedor, no una función determinista. El runner devuelve accuracy, latencia, tokens y costo.

**Trade-off:** las evals requieren API key, red y tiempo. No son deterministas al 100%, y no reemplazan tests unitarios de parsing, caché o guardrails.

### 7.12 Proveedores gratuitos y modelos verificados

**Decisión:** soportar Groq, Gemini y OpenRouter; usar Groq como default por velocidad.

**Motivo:** el proyecto debía ser reproducible sin costo de infraestructura. Groq ofrece baja latencia; Gemini ofrece free tier; OpenRouter da acceso a modelos open source gratuitos y un meta-router.

**Trade-off:** los modelos gratuitos cambian de disponibilidad y rate limits. Por eso el README documenta modelos verificados y el proveedor de OpenRouter advierte que la lista puede cambiar.

### 7.13 Temperatura 0 y `max_tokens=600`

**Decisión:** usar `temperature=0.0` y limitar la generación a 600 tokens.

**Motivo:** temperatura 0 reduce variabilidad en evals y clasificación. El límite de 600 tokens alcanza para el contrato y evita problemas de preasignación de cuota en Groq.

**Trade-off:** respuestas complejas podrían truncarse. Si el contrato crece, hay que revisar el límite.

### 7.14 Configuración por entorno y secretos fuera del código

**Decisión:** leer todo desde `.env` y `.env.example`, con `.gitignore` para `.env`.

**Motivo:** evitar credenciales en el repositorio y permitir cambiar proveedor/modelo sin tocar código.

**Trade-off:** `Settings` no valida tipos complejos al arrancar; por ejemplo, un `MAX_RETRIES` no numérico falla al importar. No hay recarga en caliente: cambiar `.env` requiere un proceso nuevo.

### 7.15 Documentación visual con Mermaid

**Decisión:** incluir un diagrama Mermaid en el README.

**Motivo:** GitHub lo renderiza nativamente y permite que una persona nueva vea el pipeline sin abrir el código.

**Trade-off:** GitHub aplica su propio tema y no permite personalizar el fondo de las etiquetas; el diagrama se adapta al tema claro/oscuro del visor, no al branding del proyecto.

---

## 8. Alternativas descartadas

| Alternativa                      | Por qué no se usó                                                                                                |
| -------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| API con FastAPI                  | Agrega autenticación, despliegue y concurrencia que el MVP no necesita.                                          |
| LangChain o framework de agentes | Oscurece el control del prompt, los tokens y los errores. Los SDKs directos son más auditables.                  |
| Base de datos para métricas      | JSONL es suficiente para el volumen y la evidencia del challenge.                                                |
| Caché semántica con embeddings   | Agrega complejidad, costo y un umbral difícil de calibrar; la caché exacta cubre el caso de consultas repetidas. |
| pytest con mocks de LLM          | No mide el comportamiento real del modelo; se prefirió una suite empírica end-to-end.                            |
| Prompts hardcodeados             | Impiden comparar versiones y auditar cambios con claridad.                                                       |
| Reintentos para errores de API   | Pueden multiplicar fallas de cuota y ocultar problemas de configuración.                                         |
| Streaming de respuestas          | La CLI necesita el JSON completo para validar con Pydantic.                                                      |

---

## 9. Cómo extender el proyecto

### 9.1 Agregar un proveedor

1. Crear `src/llm/nuevo_provider.py` heredando de `LLMProvider`.
2. Implementar `get_default_model()`, `provider_name` y `_call_api()`.
3. Registrar la clase en `LLMFactory._REGISTRY`.
4. Agregar la API key en `src/config.py` y `.env.example`.
5. Agregar tarifas en `src/observability/pricing.py`.
6. Actualizar README y ejecutar evals.

### 9.2 Agregar un prompt

1. Crear `prompts/v3_xxx.yaml` con `version`, `description`, `system_prompt` y `user_template`.
2. Ejecutar `python evals/runner.py --prompt-version v3_xxx`.
3. Comparar contra v2 con `--compare-prompts` o con corridas separadas.
4. Si se adopta, cambiar `PROMPT_VERSION` en `.env.example` y en la documentación.

### 9.3 Agregar una categoría

1. Actualizar `TicketCategory` en `src/models.py`.
2. Actualizar categorías, reglas y ejemplos en los prompts.
3. Agregar casos al dataset y a `category_stats` del runner.
4. Revisar guardrails y acciones.
5. Invalidar caché cambiando la versión del prompt.

### 9.4 Agregar un guardrail

1. Crear el resultado y la clase en `src/guardrails/`.
2. Exportarlo en `src/guardrails/__init__.py`.
3. Integrarlo en `TriageService.process_ticket()`.
4. Agregar casos a `evals/adversarial.jsonl`.
5. Documentar la decisión y el trade-off.

### 9.5 Agregar una métrica

1. Agregar el campo a `MetricRecord`.
2. Pasarlo desde `MetricsLogger.log_request()`.
3. Actualizar los llamados de `TriageService`.
4. Actualizar README y el ejemplo de JSONL.

---

## 10. Limitaciones conocidas y deuda técnica

Estas limitaciones son conscientes y no impiden la entrega, pero deben tenerse en cuenta antes de llevar el proyecto a producción.

1. **Escritura no concurrente.** `data/cache.json` se reescribe completo y `data/metrics.jsonl` se abre en modo append sin lock. Con múltiples procesos pueden perderse actualizaciones o intercalarse líneas. Para producción: cola, base de datos o escritura atómica con archivo temporal.
2. **Métricas contaminadas por evals.** `evals/runner.py` usa `TriageService`, que registra en `data/metrics.jsonl`. El archivo versionado tiene 207 registros de ejemplo y pruebas. En producción conviene separar el logger o usar un flag `--no-metrics`.
3. **Caché sin TTL ni límite.** Un cambio de prompt invalida la caché, pero no hay expiración por tiempo ni límite de tamaño. Tampoco hay normalización de acentos, puntuación ni semántica.
4. **Guardrails heurísticos.** Los regex cubren los ataques documentados, no todos los posibles. Pueden producir falsos positivos y falsos negativos. La "sanitización" de entrada es principalmente `strip()`; el bloqueo es la defensa real.
5. **OutputGuard conservador.** Si detecta una firma, reemplaza toda la respuesta; no hace redacción parcial. Puede degradar respuestas legítimas que mencionen términos internos.
6. **Precios estimados.** La tabla de precios puede quedar desactualizada. Gemini 3.x no está en la tabla y cae en la tarifa fallback. Los free tiers reales pueden ser $0, pero la estimación usa una tarifa de referencia para comparabilidad.
7. **Errores de API sin retry.** Un 429, 503 o timeout se propaga como error fatal. No hay backoff ni fallback automático a otro proveedor.
8. **Sin tests unitarios ni CI.** Las evals son empíricas y dependen de red/API. Faltan tests deterministas para parsing, caché, pricing y guardrails.
9. **Sin empaquetado.** No hay `pyproject.toml`; se ejecuta desde la raíz con `.venv/bin/python` y `sys.path` manual. Es suficiente para el challenge, no para distribución como paquete.
10. **Inconsistencias de documentación.** El README menciona `gemini-3.1-flash-lite`/`3.5`, el código usa `gemini-3.8-flash` por defecto y `.env.example` también menciona `3.8`. El docstring de `gemini_provider.py` dice SDK `google-genai >= 3.0`, pero `requirements.txt` declara `>=0.1.1`. El ejemplo de caché del README muestra `model: cache-md5`, pero el código actual registra el proveedor/modelo configurado con `cached: true`. El badge de licencia apunta a `LICENSE`, que no existe en el repositorio.
11. **Sin LICENSE.** Si el repositorio se publica, conviene agregar el archivo MIT que el badge declara.
12. **Diagrama Mermaid dependiente de GitHub.** GitHub ignora directivas de tema y aplica su propio estilo; no se puede garantizar un fondo transparente ni un color exacto en el README renderizado por GitHub.

---

## 11. Guía de lectura recomendada

Si tenés 5 minutos:

1. `README.md` (contexto y uso).
2. `src/main.py` (`TriageService.process_ticket`).
3. `src/models.py` (contrato).

Si tenés 20 minutos, seguí con:

4. `src/config.py`.
5. `src/prompt_loader.py`.
6. `src/llm/base.py` y `src/llm/factory.py`.
7. Un proveedor, por ejemplo `src/llm/groq_provider.py`.

Si tenés 45 minutos, completá con:

8. `src/guardrails/input_guard.py`.
9. `src/guardrails/output_guard.py`.
10. `src/cache.py`.
11. `src/observability/logger.py` y `pricing.py`.
12. `evals/runner.py`.
13. `prompts/v2_few_shot.yaml`.

Si vas a cambiar algo, empezá por el archivo que corresponde a la decisión:

- ¿Nuevo proveedor? `src/llm/`.
- ¿Nuevo prompt? `prompts/` y `src/prompt_loader.py`.
- ¿Nuevo campo del contrato? `src/models.py`, prompts y README.
- ¿Nueva protección? `src/guardrails/` y `evals/adversarial.jsonl`.
- ¿Nueva métrica? `src/models.py`, `src/observability/logger.py` y `pricing.py`.

---

## 12. Glosario

- **Triage:** clasificación y priorización inicial de un ticket.
- **Guardrail:** control de seguridad que bloquea o sanitiza una entrada/salida.
- **Prompt versionado:** archivo YAML identificado por versión, usado para comparar y auditar.
- **Few-shot:** técnica de incluir ejemplos en el prompt para guiar al modelo.
- **Provider:** proveedor de LLM (Groq, Gemini, OpenRouter).
- **Adapter:** clase que traduce la interfaz común `LLMProvider` al SDK de un proveedor.
- **Factory:** clase que crea el adapter correcto según configuración.
- **Cache hit:** consulta que ya estaba cacheada y no invoca al LLM.
- **JSONL:** formato de una línea JSON por registro.
- **Adversarial:** entrada diseñada para romper las reglas o extraer información interna.
- **Fallback:** respuesta o tarifa de respaldo cuando no hay una opción específica.
