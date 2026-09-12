# Floodtir

Floodtir is an AI-powered, agentic urban flood intelligence and response platform for Bangkok. Its agentic flow coordinates specialized AI agents, deterministic services, live data pipelines, and human operators across a continuous cycle: **Observe → Analyze → Predict → Plan → Approve → Act → Verify → Learn**.

The platform is designed to combine real-time weather forecasts, rainfall observations, canal and river water levels, drainage infrastructure, citizen reports, and geospatial data. Specialized agents interpret multimodal reports, fuse signals into a shared situation model, estimate localized flood risk, explain why an area is at risk, and prepare response recommendations for human approval.

Beyond prediction and visualization, Floodtir turns verified risk signals into early warnings and traceable response workflows. Once an authorized operator approves a proposed action, deterministic services route the work order to the appropriate team. Field evidence, updated sensor data, and citizen verification then determine whether the intervention reduced flooding. A mismatch automatically reopens the agentic loop for reassessment and a follow-up plan.

Floodtir is agentic by orchestration, not by uncontrolled autonomy: AI agents can observe, analyze, and recommend, but they cannot independently select legal authority, dispatch field operations, or bypass the human approval gate.

**Observe → Coordinate → Verify**

Built for BDI Hackathon 2026 OPEN, Challenge 3: Safety. The current pilot focuses on Lat Krabang District.

## Why Floodtir

Public agencies already collect substantial weather, rainfall, water-level, infrastructure, and geographic data. These sources are often viewed independently, which makes it difficult to recognize a fast-changing local risk, communicate a consistent warning, and coordinate the right response across teams.

Floodtir brings these signals into one geospatial situation model. It helps operators identify where flooding is likely to emerge, understand why an area is considered high risk, and prioritize action using current observations, historical context, and corroborated public reports.

The second gap is operational accountability: an instruction may be issued, but there is often no shared system that can prove who acted, whether the action was completed, and whether conditions actually improved.

Floodtir turns public reports into evidence-backed operational events. Every important transition is recorded in an append-only ledger so that operators and reviewers can reconstruct what happened.

## Agentic Flow

Floodtir operates as a closed-loop agentic system in which each component has a narrow responsibility and passes structured, provenance-aware state to the next step.

| Stage | Agent or service | Responsibility |
|---|---|---|
| Observe | Data workers | Collect weather, rainfall, water-level, citizen, and geospatial signals |
| Analyze | Triage Agent | Validate multimodal reports and convert them into structured observations |
| Predict | Deterministic risk engine | Fuse evidence, calculate risk, and identify high-risk locations |
| Explain | Narrator Agent | Produce grounded situation summaries and response recommendations |
| Approve | Human operator | Confirm authority, responsibility, and operational safety |
| Act | Deterministic orchestrator | Route approved work orders and track execution state |
| Verify | Verification service | Compare field evidence, new observations, and citizen feedback |
| Learn | Situation Model and ledger | Preserve outcomes and provenance for the next assessment cycle |

This division of responsibility provides the adaptability of an agentic workflow while keeping high-impact decisions deterministic, explainable, and human-controlled.

## How It Works

```text
A resident submits a photo and location
  → A Triage Agent validates the report and estimates water depth
  → Data workers fuse reports, sensors, weather, and geospatial context
  → A deterministic risk engine identifies high-risk areas
  → A Narrator Agent prepares an evidence-grounded explanation and proposal
  → A human operator reviews authority, responsibility, and safety
  → Deterministic services dispatch the approved work order
  → The responsible field team submits completion evidence
  → The verification service evaluates new observations and citizen evidence
       ✓ VERIFIED: close the case and record the result
       ✗ MISMATCH: reassess the situation and generate a follow-up plan
  → The Accountability Board presents a ledger-backed event timeline
```

Every stage preserves provenance: where the information came from, who authorized an action, what evidence was returned, and how the case ended.

## Core Features

- Crowd-sourced flood reports with geolocation and image evidence
- Vision-assisted water-depth estimation
- Multi-report corroboration and geospatial flood-surface generation
- Deterministic work-order routing with mandatory human approval
- Citizen verification and automatic mismatch escalation
- Tamper-evident SHA-256 event ledger
- Accountability Board for end-to-end operational review
- Bangkok canal, drainage, district, pump, gate, and water-level datasets
- Legal-responsibility index with explicit candidate and verified states

## Interface Status

The frontend includes a Situation Map, Work Order workflow, and Accountability Board. Image files whose names end in `-preview` are historical design-demo references and should not be treated as authoritative screenshots of the current or production interface.

## Architecture

| Layer | Technology |
|---|---|
| Backend API | Python 3.13, FastAPI, async SQLAlchemy |
| Database | PostgreSQL 16, PostGIS, TimescaleDB, pgvector |
| Frontend | Next.js 16, React, Tailwind CSS, Leaflet |
| AI/LLM | ThaiLLM-compatible instruction model through an OpenAI-compatible API |
| Ledger | SHA-256 hash chain, Ed25519 signatures, append-only PostgreSQL records |
| Queue | Redis; Celery is planned for later phases |

The **Situation Model** is the shared system of record. Every layer reads and writes through it, and every row carries a provenance state such as `REAL`, `SIMULATED`, or `PENDING-WIRE`.

## AI Safety Boundary

AI is limited to three narrow roles:

- **Vision analysis:** estimate water depth from citizen images.
- **Thai-language understanding:** convert reports and operator input into structured data.
- **Narration:** summarize situations and proposed actions for human review.

AI cannot select an agency or pump, change an order status, or dispatch work directly. Every operational dispatch requires human confirmation.

## Requirements

- Docker and Docker Compose
- Python 3.13+
- [uv](https://docs.astral.sh/uv/)
- Node.js 22+

## Quick Start

```bash
# 1. Install Python and Node.js dependencies
make install

# 2. Create the local API environment file
cp apps/api/.env.example apps/api/.env

# 3. Start PostgreSQL and Redis
docker compose up -d

# 4. Apply database migrations
make migrate

# 5. Seed the pilot flood nodes
make seed

# 6. Seed legal responsibility and dispatch-safety data
uv run --package api python scripts/seed_legal_responsibility.py --clear

# 7. Start the API in terminal 1
uv run --package api fastapi dev apps/api/src/api/main.py

# 8. Start the web application in terminal 2
npm run dev:web
```

Open:

- `http://localhost:3000` — Map Dashboard
- `http://localhost:3000/board` — Accountability Board
- `http://localhost:8000/docs` — Swagger API documentation

## Demo Data and Validation

```bash
# Generate simulated reports from 10 reporters over 30 rounds
make datagen

# Exercise the complete ingest, dispatch, verification, and ledger flow
make smoke
```

All simulated records must be marked with `is_simulated = true`.

## Main API Endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/ingest/report` | Ingest, triage, and fuse a citizen report |
| `GET` | `/flood-nodes` | List flood nodes and current water levels |
| `GET` | `/water-surface` | Return the 25×25 IDW grid used by the contour layer |
| `GET` | `/stats` | Return current node, report, and work-order counts |
| `POST` | `/work-orders` | Create a corroborated work order |
| `POST` | `/work-orders/{id}/confirm` | Record human dispatch confirmation |
| `POST` | `/work-orders/{id}/verify` | Record a `VERIFIED` or `MISMATCH` outcome |
| `GET` | `/ledger` | Return the event history and hash chain |

## Legal Responsibility Index

Floodtir loads legal-authority and dispatch-safety data from `Floodtirdatta` into the backend relational model.

| Table | Model | Purpose | Records |
|---|---|---|---:|
| `agency` | `Agency` | Bangkok operational agencies and their hierarchy | 70 |
| `legal_provision` | `LegalProvision` | Legal provisions keyed by `provision_hash` and linked to action codes | 15 |
| `district_authority_candidate` | `DistrictAuthorityCandidate` | Candidate authority assignments for Bangkok's 50 districts | 50 |
| `dispatch_guardrail` | `DispatchGuardrail` | Policy controls that prevent automatic dispatch | 11 |
| `legal_review_task` | `LegalReviewTask` | Human-review queue for authority assignments | 17 |

Candidate assignments remain `candidate_unverified` until supporting appointment documents and human review promote them to `verified`. AI is never allowed to determine legal responsibility, issue operational orders, or bypass approval.

See [README_DATABASE.md](README_DATABASE.md) for detailed data-model and seeding documentation.

## Project Structure

```text
floodtir/
├── apps/
│   ├── api/                 # FastAPI backend and Alembic migrations
│   └── web/                 # Next.js dashboard and Accountability Board
├── Floodtirdatta/           # Bangkok geospatial and responsibility datasets
├── scripts/                 # Seeders, data generator, and smoke tests
├── docs/                    # Architecture decisions and project documentation
├── docker-compose.yml       # PostgreSQL and Redis services
├── Makefile                 # Common development commands
├── package.json             # JavaScript workspace configuration
└── pyproject.toml           # Python workspace and quality configuration
```

## Guardrails

| ID | Rule |
|---|---|
| G2 | The command path is deterministic; no LLM participates in dispatch decisions. |
| G3 | Every dispatch requires human confirmation, without exception. |
| G5 | Every simulated row is explicitly labeled with `is_simulated = true`. |
| G7 | A single report is insufficient; a work order requires at least N corroborating reports. |
| G8 | Crowd-sourced input passes deduplication, geofencing, and prompt-injection screening. |
| G9 | The Accountability Board displays ledger-backed facts only, with no inferred events. |

## Build Status

| Phase | Status | Deliverable |
|---|---|---|
| P0 Scaffold | Complete | Project structure, models, and migrations |
| P1 Ingest | Complete | Intake API, VLM triage, and data generator |
| P2 Water Surface | Complete | IDW grid and map contour overlay |
| P3 Dispatch | Complete | Orchestrator and human confirmation gate |
| P4 Citizen Verify | Complete | Verification, mismatch escalation, and ledger entries |
| P5 Accountability Board | Complete | Ledger timeline and client-side hash-chain verification |
| P6 Validate | Complete | Concurrent ingest and end-to-end smoke tests |

## Operating Principles

- **Constrain the model:** keep AI responsibilities narrow and explicit.
- **Keep commands deterministic:** never place an LLM in the dispatch path.
- **Require a human gate:** a person confirms every dispatch.
- **Label the truth:** simulated and pending data must never be presented as verified reality.
- **Do not overclaim:** the system states what it knows, what it does not know, and why.

## Language Note

Project documentation is written in English for broader collaboration. Thai place names, source records, legal document titles, and selected user-interface text remain in Thai where that language is part of the source data or intended user experience.

## License

No open-source license has been granted yet. Unless a license is added, the repository remains all rights reserved.
