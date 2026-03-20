# FinCampaign — Enhancement Roadmap
> POC orientado a demostrar capacidades agénticas + Vertex AI en campañas financieras.
> Prioridad actual: **orquestación nativa y funcionamiento agéntico con Google ADK**.
> Actualizar el estado de cada ítem al ejecutarlo.

---

## Estado: `⬜ PENDING` | `🔄 IN PROGRESS` | `✅ DONE` | `⏭ SKIPPED`

---

## FASE A — Performance (fundacional) ✅ COMPLETADA

> Antes: ~600 RAG calls por batch de 100 clientes. Después: ~25.

| ID | Mejora | Feature | Estado |
|----|--------|---------|--------|
| A1 | **RAG in-process cache** — `_rag_cache` dict en `retriever.py`, limpiado al inicio de cada batch | Vertex AI Search | ✅ DONE |
| A2 | **Singleton SearchServiceClient** — cliente reutilizado en lugar de uno nuevo por llamada | Vertex AI Search SDK | ✅ DONE |
| A3 | **httpx persistent client** — `httpx.Client` con connection pooling para Gemini REST | Gemini REST API | ✅ DONE |
| A4 | **Semaphore 5→10** — 2x throughput paralelo inmediato | asyncio | ✅ DONE |

---

## FASE E — Google ADK Migration 🔴 PRIORIDAD MÁXIMA

> **Descubrimiento 2025-2026:** Google lanzó ADK (Agent Development Kit) en Cloud NEXT 2025.
> Es el framework oficial de Google para orquestación multi-agente nativa en Vertex AI.
> Reemplaza ~1,000 líneas de Python manual con primitivas declarativas.
>
> **Refs:** [ADK Docs](https://google.github.io/adk-docs/) | [Workflow Agents](https://google.github.io/adk-docs/agents/workflow-agents/) | [Multi-agent](https://google.github.io/adk-docs/agents/multi-agents/) | [Agent Engine](https://docs.cloud.google.com/agent-builder/agent-engine/overview)
>
> **Alineación con [Agent Starter Pack](https://github.com/GoogleCloudPlatform/agent-starter-pack) (verificado 2026-03-18):**
> ✅ Correcto: `LlmAgent`, `SequentialAgent`, `LoopAgent`, `VertexAiSearchTool`, `output_key`, `exit_loop`
> ⚠️ Ajuste aplicado: modelo como `Gemini(retry_options=...)` en lugar de string — resiliencia + retry
> ⚠️ Ajuste aplicado: `App(root_agent=...)` wrapper — requisito para Agent Engine (E8)

### Qué reemplaza ADK vs código actual

| Código actual | Líneas | ADK nativo | Líneas ADK |
|--------------|--------|-----------|-----------|
| `orchestrator.py` (routing + pipeline + loop) | 542 | `SequentialAgent` + `LoopAgent` + `LlmAgent` | ~40 |
| `retriever.py` (RAG manual) | 173 | `VertexAiSearchTool` | 3 |
| `customer_memory.py` (memoria custom) | 151 | `VertexAiMemoryBankService` | ~10 |
| `risk_analyst.py` + `campaign_generator.py` + `compliance_checker.py` | 579 | `LlmAgent(name, model, instruction, tools)` | ~20 c/u |
| **TOTAL** | **~1,445** | | **~200** |

### Arquitectura objetivo ADK

```
FinCampaignOrchestrator  ←── LlmAgent (decide la ruta, llama transfer_to_agent)
│  tools: [customer_history_tool, memory_load_tool]
│  memory: VertexAiMemoryBankService
│
├── EducationalPipeline       ←── LlmAgent + VertexAiSearchTool
│     (score < 550 / mora severa)
│
├── PremiumPipeline           ←── SequentialAgent
│   ├── RiskAgent             ←── LlmAgent + VertexAiSearchTool (output_key="risk")
│   └── ComplianceAgent       ←── LlmAgent + google_search grounding
│         (score > 720, sin loop)
│
├── ConditionalPipeline       ←── SequentialAgent
│   ├── RiskAgent             ←── LlmAgent + VertexAiSearchTool
│   └── ConditionalOfferAgent ←── LlmAgent + VertexAiSearchTool
│         (DTI 43-60%, oferta condicional)
│
└── StandardPipeline          ←── SequentialAgent
    ├── RiskAgent             ←── LlmAgent + VertexAiSearchTool (output_key="risk")
    └── CorrectionLoop        ←── LoopAgent (max_iterations=3)
        ├── CampaignAgent     ←── LlmAgent + VertexAiSearchTool (output_key="draft")
        └── ComplianceAgent   ←── LlmAgent + google_search + state["draft"]
```

### Patrones agénticos demostrados con ADK

| Patrón | ADK Primitive | Valor POC |
|--------|--------------|-----------|
| Orquestación declarativa | `SequentialAgent(sub_agents=[...])` | Pipeline legible, sin código imperativo |
| Retry / auto-corrección | `LoopAgent(max_iterations=3)` | Correction loop nativo, no `while` manual |
| Routing dinámico por LLM | `LlmAgent` + `transfer_to_agent()` | **El LLM DECIDE la ruta**, no un if/elif |
| Tool use nativo | `LlmAgent(tools=[vertex_search])` | Gemini decide cuándo llamar RAG |
| RAG enterprise | `VertexAiSearchTool(data_store_id=...)` | PDFs privados en Vertex AI Search |
| Grounding en vivo | `google_search` built-in tool | Normativas regulatorias reales |
| Memoria long-term | `VertexAiMemoryBankService` | Historial de cliente gestionado por Google |
| ReAct automático | `LlmAgent` por defecto | Thought→Action→Observation sin prompting manual |
| Fan-out / fan-in | `ParallelAgent(sub_agents=[...])` | 3 variantes de campaña en paralelo |
| Deploy gestionado | `vertexai.agent_engines.create()` | Runtime serverless, sin FastAPI batch |

### Items E — Migración incremental

| ID | Mejora | ADK Feature | Impacto showcase | Estado |
|----|--------|-------------|-----------------|--------|
| E1 | **ADK Foundation** — instalar `google-adk`, convertir `RiskAnalyst` a `LlmAgent` + `VertexAiSearchTool`. Prueba local con `adk web`. | `LlmAgent`, `VertexAiSearchTool` | Validar framework, base para todo | ✅ DONE |
| E2 | **SequentialAgent Pipeline** — Risk→Campaign→Compliance como `SequentialAgent`. Cada agente pasa su output en `session.state` al siguiente. | `SequentialAgent`, `output_key` | Orquestación declarativa visible | ✅ DONE |
| E3 | **LoopAgent Correction** — Campaign↔Compliance correction loop reemplazado por `LoopAgent(max_iterations=3)`. Compliance escribe `escalate=True` cuando APPROVED. | `LoopAgent`, escalation condition | Retry nativo sin `while` manual | ✅ DONE |
| EA1 | **Gemini() con retry_options** *(ajuste ASP)* — todos los agentes usan `Gemini(model=..., retry_options=HttpRetryOptions(attempts=3))` en lugar de string. Retry automático en fallas transientes. | `google.adk.models.Gemini` | Resiliencia production-grade | ✅ DONE |
| EA2 | **App wrapper** *(ajuste ASP)* — `App(root_agent=standard_pipeline)` en `__init__.py`. Requisito para Agent Engine (E8), habilita plugins (BigQuery Analytics, Context Cache). | `google.adk.apps.App` | Base para E8 deploy | ✅ DONE |
| E5 | **VertexAiSearchTool built-in** — ya implementado en E1–E3. `retriever.py` manual reemplazado en capa ADK. | `VertexAiSearchTool` | Elimina RAG manual, tool use real | ✅ DONE |
| E4 | **LlmAgent Routing con transfer_to_agent** — eliminar if/elif en `orchestrator.py`. El Orchestrator `LlmAgent` lee el perfil y llama `transfer_to_agent("StandardPipeline")`. El LLM DECIDE la ruta. | `LlmAgent`, `AgentTool`, `transfer_to_agent` | 🔥🔥🔥 THE SHOWCASE — routing agéntico real | ✅ DONE |
| E5 | **VertexAiSearchTool built-in** — eliminar `retriever.py` (173 líneas). Cada `LlmAgent` recibe `VertexAiSearchTool(data_store_id=...)`. Gemini decide cuándo llamar RAG. | `VertexAiSearchTool` | Elimina RAG manual, tool use real | ⬜ PENDING |
| E6 | **Google Search Grounding** — `ComplianceAgent` agrega `google_search` tool. Valida contra SFC Colombia / CFPB en vivo, no solo PDFs. | `google_search` built-in | Conocimiento regulatorio dinámico | ✅ DONE |
| E7 | **VertexAiMemoryBankService** — reemplazar `customer_memory.py` + tablas PostgreSQL memory por `VertexAiMemoryBankService`. `PreloadMemory` + `LoadMemory` tools nativos. | `VertexAiMemoryBankService` | Memoria long-term gestionada por GCP | ✅ DONE |
| E8 | **Deploy a Agent Engine** — `vertexai.agent_engines.create(agent, requirements=["google-adk"])`. Runtime serverless, sin FastAPI batch manual. | `Agent Engine` | POC production-grade en GCP | ⬜ PENDING |

### Secuencia recomendada Fase E

```
E1  (ADK foundation — un LlmAgent, valida setup, ~2h)
 ↓
E5  (VertexAiSearchTool — elimina retriever.py, ~1h, mejor hacerlo junto a E1)
 ↓
E2  (SequentialAgent pipeline — Risk→Campaign→Compliance, ~3h)
 ↓
E3  (LoopAgent correction loop — reemplaza while manual, ~2h)
 ↓
E4  (LlmAgent routing con transfer_to_agent — THE SHOWCASE, ~4h)
 ↓
E6  (google_search grounding en Compliance, ~1h)
 ↓
E7  (VertexAiMemoryBankService — reemplaza customer_memory.py, ~3h)
 ↓
E8  (Deploy a Agent Engine, ~2h)
```

### Items supersedidos por ADK

| Item anterior | Motivo |
|--------------|--------|
| B1 — Function Calling manual | `LlmAgent` lo hace por defecto. ADK genera `function_call` nativo para tools y routing. |
| B2 — Google Search Grounding manual | Absorbido por E6 (`google_search` built-in en ADK). |
| C2 — ReAct prompting manual | `LlmAgent` ejecuta Thought→Action→Observation automáticamente. |

---

## FASE B — Vertex AI API Features (selectivas)

> B1 y B2 supersedidos por ADK. Quedan los items de optimización de costo y UX.

| ID | Mejora | Vertex AI Feature | Estado |
|----|--------|------------------|--------|
| B3 | **Gemini Streaming** — stream de tokens al frontend en tiempo real. Requiere `streamGenerateContent` + SSE en FastAPI. | Streaming API | ⬜ PENDING |
| B4 | **Gemini Context Caching** — cachear system prompt + contexto RAG en Vertex AI por TTL. ~75% reducción en tokens de input para mismo segmento. | Context Caching API | ⬜ PENDING |
| B5 | **Model Routing automático** — DTI borderline (43–53%) o confidence < 0.65 escalan a Gemini 2.5 Pro. Se configura por `model=` en cada `LlmAgent`. | Multi-model | ⬜ PENDING |
| ~~B1~~ | ~~Gemini Function Calling~~ | — | ⏭ SKIPPED (E4) |
| ~~B2~~ | ~~Google Search Grounding~~ | — | ⏭ SKIPPED (E6) |

---

## FASE C — Patrones Agénticos Avanzados

> Con ADK, C1/C3/C4 se implementan como `LlmAgent` adicionales en el pipeline.
> C2 es automático en `LlmAgent`.

| ID | Mejora | ADK Pattern | Estado |
|----|--------|------------|--------|
| C1 | **Evaluator Agent** — 6to `LlmAgent` que puntúa la campaña (claridad, CTA, tono) score 1–10 antes de Compliance. Si score < 7 → `LoopAgent` regenera. | `LlmAgent` + `LoopAgent` condition | ⬜ PENDING |
| C3 | **A/B Campaign Variants** — `ParallelAgent` lanza 3 `CampaignAgent` (tono formal / amigable / urgencia) en paralelo; `EvaluatorAgent` elige la mejor. | `ParallelAgent` + fan-in | ✅ DONE |
| C4 | **Explainability Agent** — `LlmAgent` ligero genera explicación para el cliente final: por qué calificó, por qué ese producto. | `LlmAgent` en pipeline | ✅ DONE |
| ~~C2~~ | ~~ReAct reasoning manual~~ | — | ⏭ SKIPPED (ADK nativo) |

---

## FASE D — Analytics y Evaluación

| ID | Mejora | Vertex Feature | Estado |
|----|--------|---------------|--------|
| D1 | **Vertex AI Evaluation (RAGAS)** — evaluar calidad del RAG post-batch: faithfulness, answer relevancy, context recall | Vertex AI Evaluation Service | ⬜ PENDING |
| D2 | **Embeddings segmentación semántica** — `text-embedding-004` para vectores de perfil y clustering semántico | Vertex AI Text Embeddings API | ⬜ PENDING |

---

## Secuencia global recomendada

```
✅ FASE A (Performance) — COMPLETADA
      ↓
🔴 FASE E (ADK Migration) — PRIORIDAD MÁXIMA
   E1+E5 → E2 → E3 → E4 → E6 → E7 → E8
      ↓
   FASE C (Evaluator + A/B con ADK)
   C1 → C3 → C4
      ↓
   FASE B selectiva (B5 → B4 → B3)
      ↓
   FASE D (Analytics)
   D1 → D2
```

---

## Log de ejecución

| Fecha | Items ejecutados | Notas |
|-------|-----------------|-------|
| 2026-03-18 | A2, A3, A4, A1 | Singleton RAG client + httpx pooling + Semaphore(10) + in-process RAG cache. `clear_rag_cache()` llamado al inicio de cada batch run en `_execute_campaign_run`. |
| 2026-03-18 | Roadmap E | Research ADK 2025-2026. Diseño arquitectura objetivo con LlmAgent + SequentialAgent + LoopAgent + VertexAiSearchTool + MemoryBankService + Agent Engine. |
| 2026-03-18 | E1 | google-adk 1.27.2 instalado. `backend/agents_adk/risk_analyst.py` — LlmAgent(model=gemini-2.0-flash, tools=[VertexAiSearchTool(bypass_multi_tools=True)]). `adk web agents_adk` desde backend/. |
| 2026-03-18 | E2 | `standard_pipeline.py` — SequentialAgent(sub_agents=[Risk, Campaign, Compliance]). State flow via output_key: risk_assessment → campaign → compliance_result. root_agent actualizado. |
| 2026-03-18 | E3 | `correction_loop.py` — LoopAgent(max_iterations=3, sub_agents=[CampaignCorrector, ComplianceGate]). ComplianceGate llama exit_loop() cuando APPROVED. StandardPipeline actualizado a [RiskAnalyst, CorrectionLoop]. |
| 2026-03-18 | EA1+EA2 | Alineación Agent Starter Pack. Todos los agentes usan Gemini(model="gemini-2.0-flash", retry_options=HttpRetryOptions(attempts=3)). App(name="FinCampaignAgent", root_agent=standard_pipeline) añadido en __init__.py. |
| 2026-03-18 | E4 | orchestrator.py (ADK) — LlmAgent con transfer_to_agent a 4 rutas. fincampaign_pipeline.py — SequentialAgent([RiskAnalyst, Orchestrator]) como nuevo root. 4 pipelines: Educational, Premium (SequentialAgent), Conditional, CorrectionLoop. |
| 2026-03-18 | E6 | compliance_gate.py + premium_pipeline.py — `google_search` added to ComplianceGateAgent tools=[VertexAiSearchTool, GoogleSearchTool, exit_loop] and PremiumComplianceAgent tools=[VertexAiSearchTool, GoogleSearchTool]. Instructions updated to search SFC Colombia + CFPB live regulations in Step 2. |
| 2026-03-18 | E7 | memory_service.py — exports InMemoryMemoryService (local) or VertexAiMemoryBankService (when VERTEX_AI_MEMORY_AGENT_ENGINE_ID set). risk_analyst.py — added load_memory tool; Step 1 recalls past customer interactions before credit assessment. __init__.py — exports memory_service for custom Runner wiring. Replaces 151-line customer_memory.py + PostgreSQL memory tables. |
| 2026-03-19 | C3 | campaign_variants.py — ParallelAgent([FormalCampaignAgent, FriendlyCampaignAgent, UrgentCampaignAgent]). campaign_evaluator.py — LLM-as-Judge: scores 3 variants, writes best to output_key="campaign". correction_loop.py — reemplaza CampaignCorrectorAgent con CampaignVariantStep(SequentialAgent([variants, evaluator])). Patrones: fan-out/fan-in + LLM-as-Judge. |
| 2026-03-19 | C4 | explainability_agent.py — LlmAgent sin tools (lee risk_assessment+campaign desde state). 4 escenarios: EDUCATIONAL (mejora crediticia), PREMIUM (perfil excelente), CONDITIONAL (brecha exacta), STANDARD (calificó). Output JSON: headline+body+next_steps+tone → output_key="explanation". fincampaign_pipeline.py — agregado como Step 3 final. |
| 2026-03-19 | T1+T2+T3 | T1: run_adk.ps1 — lanza adk web con --session_service_uri sqlite:///./sessions.db (sesiones persistentes entre reinicios). T2: __init__.py — App(plugins=[ReflectAndRetryToolPlugin(max_retries=2), DebugLoggingPlugin()]). T3: risk_analyst.py — load_memory reemplazado por preload_memory (PreloadMemoryTool): inyección automática de historial del cliente sin llamada explícita. |
