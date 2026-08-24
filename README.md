# Magicpin AI Challenge — Vera

> **Vera**: A stateful, grounded AI merchant/customer engagement bot engineered for local commerce and the magicpin automated judging evaluation system.

---

## 1. Project Overview

Vera is designed to ingest multi-tier business contexts, detect high-impact commercial and operational moments ("triggers"), and compose timely, personalized, factual messages while avoiding hallucinations and spam. 

The system implements the **4-Context Grounded Framework**:
1. **Category Context**: Industry voice tone, allowed vocabulary, taboos, peer benchmarks, seasonal beats, and research digest items.
2. **Merchant Context**: Business identity, locality, verified GBP status, performance metrics (views, calls, CTR, 7d deltas), active offers, and aggregate customer retention.
3. **Trigger Context**: Reason *why now* (e.g. research digests, regulatory deadlines, match night footfall surges, sudden performance drops, batch recalls, or upcoming renewals).
4. **Customer Context** *(Optional)*: Customer profile, visit cadence, preferred slots, channel, language preference (English, Hindi, Hinglish), and explicit opt-in consent scope.

---

## 2. System Architecture

```
                                  +-----------------------+
                                  |     Automated Judge   |
                                  +-----------+-----------+
                                              |
                     +------------------------+------------------------+
                     |                        |                        |
             GET /v1/healthz            POST /v1/context          POST /v1/tick
             GET /v1/metadata                                     POST /v1/reply
                     |                        |                        |
                     v                        v                        v
+---------------------------------------------------------------------------------------+
|                                    FastAPI Service                                    |
|                                                                                       |
|  +---------------------+   +-----------------------+   +---------------------------+  |
|  | Context Store       |   | Trigger Selector      |   | Conversation Store        |  |
|  | - (scope, id) index |   | - Expiry Filter       |   | - Multi-turn state (1-5)  |  |
|  | - Atomic upsert     |   | - Urgency & Rank      |   | - Intent State Machine    |  |
|  | - Stale rejection   |   | - Suppression Engine  |   | - Auto-reply Dedup Loop   |  |
|  +----------+----------+   +-----------+-----------+   +-------------+-------------+  |
|             |                          |                             |                |
|             +--------------------------+-----------------------------+                |
|                                        |                                              |
|                                        v                                              |
|                        +-------------------------------+                              |
|                        |      Engagement Composer      |                              |
|                        | - 4-Context Grounded Synthesis|                              |
|                        | - Multi-LLM Provider Engine   |                              |
|                        |   (OpenAI / Gemini / Rule)    |                              |
|                        +---------------+---------------+                              |
|                                        |                                              |
|                                        v                                              |
|                        +-------------------------------+                              |
|                        |   Hallucination Guard Layer   |                              |
|                        | - Fact & Price Verification   |                              |
|                        | - Length & Jargon Sanitation  |                              |
|                        +-------------------------------+                              |
+---------------------------------------------------------------------------------------+
```

---

## 3. Directory Structure

```
magicpin-vera/
├── app/
│   ├── main.py                 # FastAPI application entrypoint & middleware
│   ├── config.py               # Pydantic Settings & environment config
│   ├── api/
│   │   ├── health.py           # GET  /v1/healthz
│   │   ├── metadata.py         # GET  /v1/metadata
│   │   ├── context.py          # POST /v1/context
│   │   ├── tick.py             # POST /v1/tick
│   │   └── reply.py            # POST /v1/reply
│   ├── models/
│   │   ├── contexts.py         # 4-Context schema definitions
│   │   ├── requests.py         # Inbound HTTP request models
│   │   └── responses.py        # Outbound HTTP action & health models
│   ├── services/
│   │   ├── context_store.py    # Thread-safe in-memory versioned store
│   │   ├── conversation_store.py # Multi-turn state & auto-reply tracker
│   │   ├── suppression.py      # Suppression key & body deduplication
│   │   ├── trigger_selector.py # Trigger evaluation, consent check & ranking
│   │   ├── intent_detector.py  # Regex & semantic intent classifier
│   │   ├── composer.py         # Grounded message synthesizer
│   │   ├── llm.py              # LLM provider abstraction & retry/fallback
│   │   └── validator.py        # Hallucination guard & fact verification
│   ├── prompts/
│   │   ├── composer.py         # Grounded proactive prompt templates
│   │   └── reply.py            # Grounded multi-turn reply prompt templates
│   └── utils/
│       ├── logging.py          # Structured JSON logger
│       └── timing.py           # Uptime & latency tracker
├── categories/                 # Category context specifications (5 categories)
├── tests/                      # Full pytest test suite (21+ criteria)
├── judge/
│   └── judge_simulator.py      # Automated benchmark & scoring simulator
├── Dockerfile                  # Container definition listening on 0.0.0.0:8080
├── requirements.txt            # Python dependencies
├── .env.example                # Sample environment configuration
└── generate_dataset.py         # Synthetic benchmark dataset expander
```

---

## 4. Required HTTP APIs

### 1. `GET /v1/healthz`
Returns real-time service health, uptime, and dynamic context counts.
```json
{
  "status": "ok",
  "uptime_seconds": 3600,
  "contexts_loaded": {
    "category": 5,
    "merchant": 50,
    "customer": 200,
    "trigger": 100
  }
}
```

### 2. `GET /v1/metadata`
Returns metadata regarding team, approach, model, and submission version.
```json
{
  "team_name": "Team Antigravity",
  "team_members": ["Lead AI Engineer"],
  "model": "gpt-4o-mini",
  "approach": "4-Context Grounded Composition Engine with Intent State Machine, Dynamic Versioning & Hallucination Guard",
  "contact_email": "team@magicpin.in",
  "version": "1.0.0",
  "submitted_at": "2026-04-26T00:00:00Z"
}
```

### 3. `POST /v1/context`
Pushes category, merchant, customer, or trigger contexts with atomic versioning.
- **New Context / Higher Version**: Stored/upgraded atomically (`accepted: true`).
- **Same Version**: Idempotent accept (`accepted: true`).
- **Lower Version**: Rejected as stale (`accepted: false, reason: "stale_version", current_version: N`).

### 4. `POST /v1/tick`
Evaluates active triggers, checks expiry and customer consent, filters suppressed candidates, and generates ranked proactive actions.
```json
{
  "actions": [
    {
      "conversation_id": "conv_trg_001_m_001",
      "merchant_id": "m_001_drmeera_dentist_delhi",
      "customer_id": null,
      "send_as": "vera",
      "trigger_id": "trg_001_research_digest_dentists",
      "template_name": "vera_research_digest_v1",
      "template_params": ["Dr. Meera", "JIDA Fluoride Study", "dentists"],
      "body": "Dr. Meera, JIDA Fluoride Recall Study (Oct 2025) landed. Relevant to your patients — 2,100-patient trial showed 3-month fluoride recall cuts caries recurrence 38% better than 6-month in high-risk adults. Worth a look? I can pull the abstract and draft a patient-ed WhatsApp.",
      "cta": "open_ended",
      "suppression_key": "research:dentists:2026-W17",
      "rationale": "Shared relevant industry digest 'JIDA Fluoride Study' with Dr. Meera"
    }
  ]
}
```

### 5. `POST /v1/reply`
Processes merchant and customer replies up to 5 turns.
- **Intent Transition**: When merchant says *"Okay, let's do it"*, switches immediately to action without asking redundant qualification questions.
- **Auto-Reply Loop Breaker**: Detects repeated canned messages and terminates loop gracefully (`action: "end"` or `"wait"`).
- **Off-Topic / Boundary Guard**: Stays polite and on-mission (e.g. declines GST filing requests without hallucinating fake capabilities).

---

## 5. Five Evaluation Dimensions

1. **Specificity**: Injects verifiable numerical facts (30-day views, 7-day delta percentages, trial results, affected batch numbers, slot times).
2. **Category Fit**: Adapts tone to category expectations (Dentists: clinical/peer; Salons: aesthetic/warm; Restaurants: high-velocity operator; Gyms: coaching/motivational; Pharmacies: precise/compliant).
3. **Merchant Fit**: Personalizes using owner name, locality, verified GBP status, and active offers.
4. **Trigger Relevance**: Clearly states *why* Vera is reaching out right now.
5. **Engagement Compulsion**: Keeps messages concise (2-4 sentences) with a single, clear, low-friction next step.

---

## 6. Local Setup & Quickstart

### Prerequisites
- Python 3.10+ (or Python 3.11/3.12)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Generate Dataset
```bash
python generate_dataset.py --seed-dir . --out ./expanded
```

### 3. Run Automated Unit & Integration Tests
```bash
pytest -v tests/
```

### 4. Start the Application Server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

### 5. Run the Automated Judge Simulator
In another terminal:
```bash
python judge/judge_simulator.py --bot-url http://127.0.0.1:8080 --dataset ./expanded
```

---

## 7. Docker Deployment

### Build Container
```bash
docker build -t magicpin-vera .
```

### Run Container
```bash
docker run -d -p 8080:8080 --name vera-service magicpin-vera
```

---

## 8. Environment Variables

| Variable | Default | Description |
| :--- | :--- | :--- |
| `LLM_PROVIDER` | `rule_engine` | LLM provider: `openai`, `gemini`, or `rule_engine` |
| `LLM_API_KEY` | `""` | API key for LLM provider (optional) |
| `LLM_MODEL` | `gpt-4o-mini` | LLM model identifier |
| `PORT` | `8080` | Port for the HTTP server |
| `HOST` | `0.0.0.0` | Host binding address |
| `TEAM_NAME` | `Team Antigravity` | Metadata team name |
| `BOT_VERSION` | `1.0.0` | Bot release version |

---

## 9. Security & Safety

- No API keys or credentials committed to source.
- Context payload size limits and schema validation via Pydantic.
- Thread-safe in-memory state tracking.
- Hallucination guard sanitizing all outgoing messages against internal system terms or ungrounded statistics.
