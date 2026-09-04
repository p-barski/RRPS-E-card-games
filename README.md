Unofficial project implementating "Restricted Rock-Paper-Scissors" and "E-card"
from manga/anime _Gambling Apocalypse Kaiji_, playable against
another player (via a shareable room code) or a bot. Django + Channels
backend, React + TypeScript frontend.

## Run locally

**Backend** (Python 3.14):

```bash
cd backend
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py runserver 0.0.0.0:8000
```

**Frontend**:

```bash
cd frontend
npm install
cp .env.local.example .env.local   # if not already present
npm run dev
```

Then open http://localhost:5173.

## Tests

```bash
# backend: unit (pure game logic) + integration (websocket/API, full games)
cd backend && .venv/bin/python -m pytest

# frontend: type-check
cd frontend && npx tsc --noEmit

# frontend: whole-system smoke tests (needs both servers already running)
cd frontend && npm run test:e2e
```

## Layout

- `backend/apps/rps/engine.py`, `backend/apps/ecard/engine.py` — the actual
  game rules, as plain Python with no framework dependencies.
- `backend/apps/games/consumer.py` — the WebSocket game loop (moves, bot
  turns, broadcasting).
- `backend/apps/games/views.py` — room create/join REST endpoints.
- `frontend/src/games/{rps,ecard}/` — the two game screens.
- `frontend/src/shared/useGameSocket.ts` — the WebSocket client hook.
