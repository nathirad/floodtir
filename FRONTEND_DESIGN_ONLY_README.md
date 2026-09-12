# Floodtir — Frontend-Only Design Package

This package supports frontend design and review without requiring the FastAPI backend, database, migrations, Docker services, or Python tooling.

## Start the Design Demo

1. Read `CLAUDE_DESIGN_BRIEF.md`.
2. Install the frontend dependencies.
3. Start the Next.js development server.

```bash
npm ci --workspace=apps/web
npm run dev:web
```

Open the routes in this order:

- `/design` — system overview and design scope
- `/` — Situation Map and Work Order flow
- `/board` — Accountability Board

## Demo Data Contract

- When `NEXT_PUBLIC_API_URL` is unset, the frontend uses `/api/demo`.
- Every record returned by the demo API is `SIMULATED-by-design`.
- The mock API exists only to demonstrate layout and interaction behavior.
- Frontend-only design changes should remain inside `apps/web`.

## Connecting the Backend Later

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev:web
```

The frontend API contract is designed so that the real backend can replace the mock API without a UI rewrite.
