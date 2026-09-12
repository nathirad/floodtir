# Floodtir — Frontend Design Handoff

## Objective

Review and improve the frontend experience so that the complete operational loop is easy to understand: situational awareness, human confirmation, dispatch, outcome verification, and evidence recording.

This is a design demo. The interface must not imply that every backend integration is production-ready.

## Facts That Must Remain True

- The frontend is in `apps/web` and uses Next.js 16, React, Tailwind CSS, and Leaflet.
- The FastAPI backend is in `apps/api`, but it is not required for a frontend-only design session.
- When `NEXT_PUBLIC_API_URL` is unset, the frontend uses `/api/demo`.
- Every `/api/demo` record must be labeled `SIMULATED-by-design`.
- Repository GeoJSON layers may be used for geographic context.
- Mock data must never appear to be live data from PostGIS, ThaiWater, LINE, or real officials.
- Set `NEXT_PUBLIC_API_URL=http://localhost:8000` to reconnect the real API without redesigning the UI.

## Primary Routes

- `/design` — System Storyboard and frontend/backend boundaries
- `/` — Situation Map and Work Orders
- `/board` — Accountability Board and SHA-256 event chain

## Story the Demo Must Communicate

1. Multiple citizen reports are fused into a Flood Node.
2. The map presents water depth and risk.
3. The system proposes a deterministic Work Order.
4. A human must confirm the order before dispatch under guardrail G3.
5. Field evidence and citizen feedback produce a `VERIFIED` or `MISMATCH` result.
6. A `MISMATCH` creates a follow-up Work Order so the loop cannot end silently.
7. Every event presented as fact is backed by a ledger entry.

## Review Priorities

1. Test whether a user can understand the current situation within 10 seconds.
2. Make `REAL`, `SIMULATED-by-design`, and `PENDING-WIRE` immediately distinguishable.
3. Make the human confirmation gate prominent without overloading the dashboard.
4. Review responsive behavior at 1440 px desktop and 1024 px tablet widths.
5. Preserve the existing API contract when recommending component or state changes.
6. Never give AI the visual or functional authority to select agencies or dispatch work automatically.

## Ready-to-Use Review Prompt

```text
Act as a senior product designer and frontend reviewer for Floodtir. Read
CLAUDE_DESIGN_BRIEF.md, README.md, and the code under apps/web first.

This is a design demo. Treat every response from /api/demo as
SIMULATED-by-design and do not interpret mock data as production data.

Open /design to understand the system, then review / and /board. Evaluate:
1. Can the user understand the flood situation within 10 seconds?
2. Is the human-confirmation and VERIFIED/MISMATCH loop clear?
3. Are REAL, SIMULATED-by-design, and PENDING-WIRE labels honest and visible?
4. Which areas are cluttered, repetitive, or competing for attention?
5. Which improvements can be implemented in apps/web without apps/api?

After the review, modify frontend files only and summarize the before/after.
Do not remove guardrails G3, G7, or G9, and never enable AI auto-dispatch.
```

## Run the Frontend-Only Demo

```bash
npm ci --workspace=apps/web
npm run dev:web
```

Open `http://localhost:3000` or the port reported by Next.js.
