# Structural Engineer AI Agent

An AI-powered web app for structural engineers. Engineers chat with a Claude-backed agent that performs **real engineering calculations** — wind loads, beam sizing, seismic base shear, and spread footing sizing — using actual code formulas from ASCE 7-22, AISC, and ACI 318, not LLM guessing. Conversations are persisted in SQLite.

## Features

- **Chat interface** — server-rendered Jinja2 UI with a dark engineering theme and markdown rendering
- **Exact calculations** — the agent calls typed Python tools for numerical results; it never approximates numbers itself
- **Code-referenced results** — every tool returns the applicable code section (e.g. `ASCE 7-22 Chapter 27`) alongside the computed values
- **Persistent conversations** — SQLite-backed history; conversation titles auto-generated from the first message
- **Fully tested** — unit tests for each calculation tool, ORM tests against in-memory SQLite, and FastAPI route tests with the agent mocked

## Engineering Calculations

| Tool | Code Reference | Key Inputs |
|------|---------------|------------|
| `calculate_wind_load` | ASCE 7-22 Ch. 27 (Directional Procedure) | height, wind speed, exposure category, GCpi |
| `calculate_beam` | AISC ASD / NDS | span, uniform load, material, allowable stress |
| `calculate_seismic_load` | ASCE 7-22 §12.8 ELF | building weight, Ss, S1, site class, risk category |
| `calculate_footing` | ACI 318-19 Ch. 13 | column load, allowable soil bearing, footing depth |

Formulas implemented include `qz = 0.00256 · Kz · Kzt · Kd · Ke · V²` for wind velocity pressure, `M = wL²/8` with an L/360 deflection check for beams, `SDS = ⅔ · Fa · Ss` with `V = Cs · W` for seismic base shear, and net-allowable-bearing sizing with a 3-inch footing increment for spread footings.

## Tech Stack

- **FastAPI** — async web framework
- **pydantic-ai** — agent framework wrapping Claude Sonnet 4.6
- **SQLAlchemy 2** — ORM over SQLite
- **Jinja2** — server-rendered templates
- **uv** — package manager

## Quick Start

### Prerequisites

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/) installed
- An Anthropic API key

### Setup

```bash
# Clone the repository
git clone https://github.com/<your-user>/structural-engineer-agent.git
cd structural-engineer-agent

# Install dependencies
uv sync

# Configure your API key
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env
```

### Run the dev server

```bash
uv run python app/main.py
# or, with auto-reload
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open http://127.0.0.1:8000 and start chatting.

### Run the tests

```bash
uv run pytest tests/ -v
```

## Project Structure

```
app/
├── main.py        FastAPI app, static mount, DB startup
├── database.py    SQLite engine, SessionLocal, get_db dependency
├── models.py      ORM: Conversation, Message (1-to-many, cascade delete)
├── schemas.py     Pydantic I/O schemas
├── agents.py      pydantic-ai agent + 4 calculation tools
├── routes.py      HTTP routes + Jinja2 rendering
├── templates/     base.html, index.html
└── static/        CSS + JS
tests/
├── test_calculations.py   tool-level unit tests (no LLM)
├── test_database.py       ORM CRUD against in-memory SQLite
└── test_routes.py         FastAPI TestClient + mocked agent
```

## Request Flow

1. Browser POSTs to `/conversations/{id}/messages`
2. `routes.py` loads prior messages and builds pydantic-ai message history
3. `run_agent(user_msg, history)` invokes Claude
4. Claude calls one or more `@agent.tool_plain` functions for precise numerical results
5. User and assistant messages are persisted to the `messages` table
6. Response JSON is returned; the frontend appends the assistant bubble

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Homepage |
| `GET` | `/conversations` | List all conversations (JSON) |
| `POST` | `/conversations/new` | Create conversation, redirect |
| `GET` | `/conversations/{id}` | Conversation page |
| `POST` | `/conversations/{id}/messages` | Send message, receive AI reply |
| `DELETE` | `/conversations/{id}` | Delete conversation + messages |

## Disclaimer

This tool is intended as an engineering assistant for preliminary calculations and code-reference lookups. All results must be independently verified by a licensed professional engineer before use in design. The seismic tool, for example, assumes `R = 3.5` (ordinary steel moment frame); the footing tool sizes for bearing only and does not include reinforcement or punching-shear design.

## License

MIT
