# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Decision Log — Required Before Implementation

**Before implementing any non-trivial change**, append a new entry to `docs/DECISIONS.md`.

Rules:
- **Never overwrite or delete existing entries** — append only, newest at the bottom
- Format: `## YYYY-MM-DD — <short title>` followed by `- เหตุผล:` and `- trade-off:`
- Log every architectural choice, tech selection, schema design decision, or guardrail interpretation
- If reversing a previous decision, add a new entry referencing the old one — do not edit the old entry

---

## Project

**Floodtir** — Bangkok flood coordination platform that closes the loop: detect → command → prove it happened.
BDI Hackathon 2026 OPEN, Safety track — pilot district: Lat Krabang.

The problem is not lack of data. The gap is an **unclosed loop**: orders are issued but there is no system that proves action was taken and outcomes verified. See `docs/floodtir-project-document.md` for full spec.

---

## Repository Layout

```
floodtir/
├── apps/
│   ├── api/              # Python + FastAPI (uv managed)
│   │   ├── src/api/      # Application source
│   │   │   ├── main.py
│   │   │   ├── config.py
│   │   │   ├── database.py
│   │   │   └── models/   # SQLAlchemy ORM models
│   │   ├── db/migrations/ # Alembic (async)
│   │   └── pyproject.toml
│   ├── web/              # Next.js 16 + TypeScript + Tailwind + Leaflet
│   └── worker/           # Celery workers (ETL, early-warning) — P1+
├── agents/
│   ├── triage/           # LLM+VLM: photo analysis → water_level_m (metric)
│   ├── narrator/         # RAG+LLM: Thai-language situation narration
│   └── orchestrator/     # Deterministic command routing — no LLM
├── mcp/                  # MCP tools server (read-only + confirm-gated propose)
├── ledger/               # hash-chain + Ed25519 module
├── rag/                  # pgvector pipeline + SOP documents
├── shared/               # Shared types and utilities
└── docs/
```

---

## Dev Commands

All commands run from the **monorepo root** unless noted.

### Setup
```bash
make install          # uv sync --all-packages + npm install
docker compose up -d  # start PostgreSQL/PostGIS/TimescaleDB + Redis
make migrate          # apply Alembic migrations
```

### Running services
```bash
uv run --package api fastapi dev apps/api/src/api/main.py   # API (hot reload)
npm run dev:web                                              # Next.js frontend
```

### Lint & type check
```bash
make lint         # ruff (Python) + ESLint (Next.js)
make lint-fix     # ruff --fix (Python only)
make typecheck    # mypy (Python) + tsc via next build
```

### Migrations
```bash
make migrate                  # alembic upgrade head
make migration name="<msg>"   # generate new revision
```

### Per-package (when needed)
```bash
cd apps/api && uv run alembic upgrade head   # alembic must run from apps/api/ (alembic.ini location)
cd apps/web && npm run dev                   # or: npm run dev:web from root
```

---

## Architecture

### Situation Model — Single Source of Truth
All layers read/write through **Situation Model** (PostGIS + TimescaleDB + pgvector). Every row carries provenance.

Three data classes — all must be labeled:
- `REAL` — verified observations (sensors, crowdsourced + corroborated)
- `SIMULATED-by-design` — edge-IoT, LINE dispatch, synthetic reporters
- `PENDING-WIRE` — ThaiLLM, RAG, MCP (not yet connected)

Every event is appended to the **Ledger** (hash-chain + Ed25519). Immutable by design.

### Workflow Phases
```
Citizen photo + coordinates
  → triage agent [VLM] → water_level_m (float, metres)
  → quality check (dedup / geofence / anti-injection)
  → osint_report → fuse N reports per flood_node
  → water surface (IDW/contour) → map layer
  → early-warning score → human confirm
  → work order → dispatch → field photo back
  → verify → VERIFIED or MISMATCH → ledger
       MISMATCH → escalate → new WO → loop
```

---

## Key Tables

| Table | Purpose |
|---|---|
| `reporter` | Citizen / OSINT source with `trust_score` and `is_simulated` flag |
| `osint_report` | TimescaleDB hypertable — photo ref, PostGIS point, `water_level_m` (AI metric), `confidence` |
| `flood_node` | Sampling nodes seeded from 2554 flood extent — holds `current_fused_level`, `last_updated` |
| `water_surface` | **ไม่มี DB table** — คำนวณ IDW on-the-fly ใน `GET /water-surface` (P2) |
| `work_order` | Command + state machine — **P3** |
| `verification` | VERIFIED / MISMATCH outcome — **P4** |
| `ledger` | Append-only hash-chain event log — **P5** |

Both `flood_node` and `osint_report` have GIST spatial indexes on their `geom` column.

---

## Agent Roles — Do Not Mix

| Agent | Input → Output | Hard constraint |
|---|---|---|
| `triage` | Photo + coords → VLM → `water_level_m` (metres) + quality gate | Must not create or update work orders |
| `narrator` | Situation + SOP (RAG) → Thai-language summary / proposal | Proposes only — never dispatches |
| `orchestrator` | Confirmed intent → PostGIS routing → dispatch | Fully deterministic — zero LLM calls |

**LLM is allowed to:** parse Thai text · analyse images (VLM) · narrate/summarise.
**LLM must never:** select units/pumps · change task state · judge mismatches · dispatch autonomously.

---

## Guardrails

- **G2** — Command path is always deterministic (no LLM in the dispatch loop).
- **G3** — Human confirmation required before every dispatch. No exceptions.
- **G5** — Every simulated data row must carry `is_simulated = true`.
- **G7** — A single report never triggers action alone. Corroboration ≥ N required.
- **G8** — All crowdsourced input passes dedup + geofence + anti-injection before ingest.
- **G9** — Accountability board shows only ledger-backed, labeled facts. No inference.

---

## LLM Configuration

- Model: **ThaiLLM 30B instruct** — ThaiLLM NSTDA 30B or Typhoon 2.5 30B-A3B
- Interface: OpenAI-compatible. Swap between Ollama and remote API via env — no architecture change.
- Adaptation: RAG + prompt only. Do not fine-tune the base model.
- All credentials via env (see `apps/api/.env.example`).

---

## Build Phases

| Phase | Goal | Exit Criteria |
|---|---|---|
| **P0** ✅ | Scaffold: project structure, models, migrations | Repo initialised, models type-check clean |
| **P1** ✅ | Ingest: intake endpoint + triage (VLM) + datagen | 10 simulated reporters posting concurrently → node levels update |
| **P2** ✅ | Water surface: IDW/contour + map layer | Map renders contour from fused node data |
| **P3** | Dispatch: orchestrator + human confirm gate + LINE (sim) | WO passes confirm → dispatched |
| **P4** | Citizen verify: result photo → MISMATCH → escalate → ledger | Full MISMATCH loop end-to-end |
| **P5** | Accountability board: ledger-backed UI | Board shows real ledger events, all labeled |
| **P6** | Validate: smoke test concurrent ingest + MISMATCH | Concurrent + edge cases covered |

---

## Out of Scope (Do Not Build Now)

- CCTV / zero-shot video analysis
- Hydraulic simulation
- Full tide / upstream model
- LLM base model fine-tuning
- Blockchain (hash-chain in PostgreSQL is sufficient)
