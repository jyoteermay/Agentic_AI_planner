# 🌍 AI Trip Planner

An agentic travel planner built with **LangGraph**, **FastAPI** and **Streamlit**. Ask for a trip, e.g. *"Plan a trip to Goa for 5 days"*, and the agent gathers live data — weather, attractions, restaurants, activities, transport, costs and currency rates — and returns a complete Markdown travel plan with a day-by-day itinerary and a cost breakdown.

## How it works

```
Streamlit UI ──POST /query──▶ FastAPI (main.py) ──▶ LangGraph agent
                                                     │
                                       ┌─────────────┴─────────────┐
                                       ▼                           ▼
                                  LLM (Gemini / Groq)  ◀──────▶  Tools
                                                                 • Weather (OpenWeatherMap)
                                                                 • Places search (Tavily / Google Places)
                                                                 • Expense calculator
                                                                 • Currency converter (ExchangeRate API)
```

The agent loops: the LLM decides which tools to call, the tools run, and the results go back to the LLM until it writes the final plan. The graph is built once at server startup.

## Tech stack

| Layer | Technology |
|---|---|
| LLM | Google Gemini (`gemini-3.1-flash-lite`, default) or Groq (`openai/gpt-oss-120b`) |
| Agent | LangGraph + LangChain tools |
| Backend | FastAPI + Uvicorn |
| Frontend | Streamlit |
| Search / data | Tavily, Google Places (optional), OpenWeatherMap, ExchangeRate API |

## Project structure

```
AI_Trip_Planner/
├── main.py                  # FastAPI app: GET /, POST /query
├── streamlit_app.py         # Streamlit chat UI (calls the API at localhost:8000)
├── agent/
│   └── agentic_workflow.py  # LangGraph agent: LLM node + tools node
├── tools/                   # LangChain tools exposed to the agent
│   ├── weather_info_tool.py
│   ├── place_search_tool.py
│   ├── expense_calculator_tool.py
│   └── currency_conversion_tool.py
├── utils/                   # API clients, model loader, config loader, helpers
├── prompt_library/prompt.py # System prompt for the travel agent
├── config/config.yaml       # LLM model names, timeouts, retries
├── logger/logging.py        # Central logger (console + rotating file)
├── exception/               # Custom exception handling
└── notebook/                # Experiments
```

## Setup

### 1. Clone and create a virtual environment (Python 3.10+)

```bash
git clone <your-repo-url>
cd AI_Trip_Planner
python -m venv env
source env/bin/activate          # Windows: env\Scripts\activate
pip install -r requirements.txt
```

<details>
<summary>Using <code>uv</code> instead</summary>

```bash
pip install uv
uv venv env --python 3.10
source env/bin/activate          # Windows: env\Scripts\activate
uv pip install -r requirements.txt
```
</details>

### 2. Add your API keys

Copy the template and fill in your keys:

```bash
cp .env.name .env
```

| Variable | Required | Used for | Get one at |
|---|---|---|---|
| `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) | Yes, for Gemini | LLM | https://aistudio.google.com/apikey |
| `GROQ_API_KEY` | Only if using Groq | LLM | https://console.groq.com/keys |
| `TAVILY_API_KEY` | Yes | Place search | https://tavily.com |
| `OPENWEATHERMAP_API_KEY` | Yes | Weather | https://openweathermap.org/api |
| `EXCHANGE_RATE_API_KEY` | Yes | Currency conversion | https://www.exchangerate-api.com |
| `GPLACES_API_KEY` | Optional | Google Places (see `USE_GOOGLE_PLACES`) | Google Cloud Console |

> `.env` is git-ignored — never commit real keys.

## Run

Start the backend, then the frontend, in two terminals:

```bash
uvicorn main:app --reload --port 8000
```

```bash
streamlit run streamlit_app.py
```

Open the Streamlit URL (usually http://localhost:8501) and ask for a trip.

### API

- `GET /` — health check, returns the active provider
- `POST /query` — body `{"question": "Plan a trip to Goa for 5 days"}`, returns `{"answer": "<markdown plan>"}`
- `GET /docs` — interactive Swagger UI

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Plan a trip to Goa for 5 days"}'
```

## Configuration

**Models** — `config/config.yaml`:

```yaml
llm:
  gemini:
    model_name: "gemini-3.1-flash-lite"
    timeout: 90          # seconds per LLM call
    max_retries: 2
    thinking_budget: 0   # 0 = fastest; raise for more careful plans
  groq:
    model_name: "openai/gpt-oss-120b"
```

**Environment variables:**

| Variable | Default | Effect |
|---|---|---|
| `MODEL_PROVIDER` | `gemini` | `gemini` or `groq` |
| `USE_GOOGLE_PLACES` | off | `1` = try Google Places first, Tavily as fallback |
| `SAVE_GRAPH_PNG` | off | `1` = save the agent graph diagram to `my_graph.png` at startup |
| `LOG_LEVEL` | `INFO` | `DEBUG` also logs tool outputs |
| `LOG_DIR` | `./logs` | Where `trip_planner.log` is written |

Example: `MODEL_PROVIDER=groq uvicorn main:app --reload --port 8000`


*Travel plans are AI-generated. Verify prices, opening hours and travel requirements before you go.*
