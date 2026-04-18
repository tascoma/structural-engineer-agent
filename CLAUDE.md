# Structural Engineer AI Agent

An AI-powered web app for structural engineers. Engineers chat with a Claude-backed agent that performs real engineering calculations (wind loads, beam sizing, seismic loads, footing design) using actual code formulas, not LLM guessing. Conversations are persisted in SQLite.

## Tech Stack

- **FastAPI** — web framework (async routes, dependency injection)
- **pydantic-ai** — agent framework wrapping Claude Sonnet 4.6
- **SQLAlchemy** — ORM with SQLite (`structural_engineer.db`)
- **Jinja2** — server-rendered HTML templates
- **uv** — package manager (use `uv add`, not `pip`)

## Commands

```bash
# Run the dev server
uv run python app/main.py
# or
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# Run tests
uv run pytest tests/ -v

# Add a dependency
uv add <package>
uv add --dev <package>
```

## Project Structure

```
app/
├── main.py        # FastAPI app, static files mount, DB startup
├── database.py    # SQLite engine, SessionLocal, get_db() dependency
├── models.py      # ORM: Conversation, Message (1-to-many, cascade delete)
├── schemas.py     # Pydantic I/O schemas
├── agents.py      # pydantic-ai agent + 4 calculation tools
├── routes.py      # All HTTP routes + Jinja2 template rendering
├── templates/
│   ├── base.html  # Layout: sidebar + main area
│   └── index.html # Chat UI; markdown rendered via marked.js CDN
└── static/
    ├── css/style.css  # Dark engineering theme
    └── js/app.js      # Fetch-based chat, optimistic UI, typing indicator
tests/
├── test_calculations.py  # Unit tests for all 4 engineering tools (no LLM)
├── test_database.py      # ORM CRUD tests (in-memory SQLite)
└── test_routes.py        # FastAPI endpoint tests (agent mocked with AsyncMock)
```

## Architecture

Request flow for sending a message:

1. `app.js` POSTs to `/conversations/{id}/messages`
2. `routes.py` loads prior messages from DB, builds pydantic-ai message history
3. `run_agent(user_msg, history)` in `agents.py` calls Claude via pydantic-ai
4. Claude may call any of the 4 `@agent.tool_plain` functions for calculations
5. Both user and AI messages are saved to `messages` table
6. `ChatResponse` JSON is returned; `app.js` appends the AI bubble

## API Routes

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Homepage (Jinja2) |
| GET | `/conversations` | List all conversations (JSON) |
| POST | `/conversations/new` | Create conversation → 303 redirect |
| GET | `/conversations/{id}` | Conversation page (Jinja2) |
| POST | `/conversations/{id}/messages` | Send message, get AI response (JSON) |
| DELETE | `/conversations/{id}` | Delete conversation + messages, 204 |

## Database Schema

**`conversations`** — `id`, `title` (auto-set from first message, max 80 chars), `created_at`, `updated_at`

**`messages`** — `id`, `conversation_id` (FK, cascade delete), `role` (`"user"` or `"assistant"`), `content`, `created_at`

## Engineering Calculation Tools

All four tools are `@agent.tool_plain` functions. They compute exact values from formulas and return structured dicts — the LLM never guesses numerical results.

| Tool | Code Reference | Key Inputs |
|------|---------------|------------|
| `calculate_wind_load` | ASCE 7-22 Ch. 27 | `height_ft`, `basic_wind_speed_mph`, `exposure_category` (B/C/D), `internal_pressure_coefficient` |
| `calculate_beam` | AISC ASD / NDS | `span_ft`, `total_uniform_load_klf`, `material` (steel/wood), `allowable_stress_ksi` |
| `calculate_seismic_load` | ASCE 7-22 §12.8 ELF | `building_weight_kips`, `Ss`, `S1`, `site_class` (A–E), `risk_category` (I–IV) |
| `calculate_footing` | ACI 318-19 Ch. 13 | `column_load_kips`, `allowable_soil_bearing_psf`, `footing_depth_ft` |

**Key formula notes:**
- Wind: `qz = 0.00256 × Kz × Kzt × Kd × Ke × V²`
- Beam: `M = wL²/8`, deflection limit L/360
- Seismic: `SDS = (2/3) × Fa × Ss`, `V = Cs × W` (R=3.5 hardcoded — ordinary steel moment frame)
- Footing: net allowable = gross allowable − overburden; rounds up to nearest 3 inches

## Testing

- **Calculation tests**: call tool functions directly, no API key needed
- **Database tests**: use in-memory SQLite, isolated per test via fixture teardown
- **Route tests**: use FastAPI `TestClient` + `StaticPool` (ensures single shared in-memory connection) + `AsyncMock` to patch `run_agent`

## Environment

Requires `ANTHROPIC_API_KEY` in `.env` at the project root:

```
ANTHROPIC_API_KEY=sk-ant-...
```

## Known Deprecations (non-breaking)

- `app/database.py`: `from sqlalchemy.ext.declarative import declarative_base` — move to `from sqlalchemy.orm import declarative_base`
- `app/main.py`: `@app.on_event("startup")` — migrate to `lifespan` context manager
