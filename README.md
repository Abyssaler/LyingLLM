# LyingLLM

12-player standard Werewolf LLM simulation and spectating system.

## Quick Start

### Backend

```bash
cd backend
# create venv (use uv or python -m venv)
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
pytest -v
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173, configure 12 seats with the **Mock** provider,
click **Validate** then **Start Game**, and watch the full game unfold in real time.

### API Smoke Test (no browser)

```bash
# 1. create game
curl -X POST http://localhost:8000/api/games \
  -H "Content-Type: application/json" \
  -d '{"players":['$(for i in $(seq 1 12); do printf '{"player_id":%d,"model_config":{"provider_id":"mock","model_id":"mock-default"}}' $i; [ $i -lt 12 ] && echo ','; done)']}'

# 2. start game
curl -X POST http://localhost:8000/api/games/{game_id}/start

# 3. poll status
curl http://localhost:8000/api/games/{game_id}
```

## Architecture

- `backend/app/` — FastAPI app factory only
- `backend/src/lyingllm/domain/` — pure models, enums, rule constants, validators
- `backend/src/lyingllm/engine/` — **only layer that mutates GameState**
- `backend/src/lyingllm/agents/` — prompt building, JSON parsing
- `backend/src/lyingllm/llm/` — provider adapters (Mock + registry)
- `backend/src/lyingllm/services/` — API orchestration
- `backend/src/lyingllm/storage/` — in-memory event log + JSONL hooks
- `frontend/` — React + Vite + TypeScript spectator UI

## Implemented (MVP)

- [x] 12-player fixed role assignment
- [x] Full state machine: SETUP → GAME_END
- [x] Night resolution (guard, wolf kill, witch, seer)
- [x] Death queue, death skills, last words
- [x] Sheriff election (day 1 only)
- [x] Day discussion, vote, tie-break, exile
- [x] Win conditions with night tie-breaker (wolves win first)
- [x] Action validation + default actions
- [x] Event log with visibility layers (public / observer / player / wolves)
- [x] Mock LLM adapter (zero API key needed)
- [x] REST API + WebSocket
- [x] Setup page (provider/model selection + validation)
- [x] Game spectator page (seats, event stream, WS real-time)
- [x] 80 passing tests (unit + integration)

## Known Limitations / TODO

- Self-destruct path not exercised (stub agents never self-destruct)
- Real OpenAI/Claude/Gemini adapter not yet implemented
- Reasoning trace is basic (self_explanation mode only)
- No persistent storage (JSONL stubs present, not wired)
- No MVP referee
- Frontend is minimal styling
