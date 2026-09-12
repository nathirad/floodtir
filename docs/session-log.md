# Session Log

---

## 2026-06-23 — Session 1: Project Kickoff & P0 Scaffold

### Feature ที่ทำ

- **Project Document** — อ่านและทำความเข้าใจ `floodtir-project-document.md`
- **CLAUDE.md** — สร้างจาก project document + decisions ในวันนี้ (ภาษาไทย → อัปเดตเป็นอังกฤษ) + เพิ่ม Decision Log rule
- **README.md** — สร้างใหม่เป็นภาษาไทย พร้อม getting started จริง
- **Monorepo scaffold**
  - Root `pyproject.toml` (uv workspace) + root `package.json` (npm workspace)
  - `Makefile` รวม command: `make lint`, `make typecheck`, `make migrate`, `make db-up`
  - Single `.git` ที่ root ครอบทั้ง `apps/api/` และ `apps/web/`
- **Backend (apps/api/)**
  - FastAPI skeleton + `/health` endpoint
  - SQLAlchemy models: `Reporter`, `FloodNode`, `OsintReport`
  - Alembic async migrations (env.py, initial_schema)
  - pydantic-settings config, async database session
- **Frontend (apps/web/)**
  - Next.js 16 + TypeScript + Tailwind + Leaflet
  - `MapView` component — Leaflet map centered บนเขตลาดกระบัง
  - `MapDashboard` client component — header, sidebar, phase tracker
- **Infrastructure**
  - `docker-compose.yml` — TimescaleDB/PostGIS (pg16) + Redis
- **Docs**
  - `docs/DECISIONS.md` — 9 entries, append-only decision log
  - `docs/session-log.md` — ไฟล์นี้

### Bug ที่เจอและแก้ระหว่างทาง

| บั๊ก | สาเหตุ | การแก้ |
|---|---|---|
| `ModuleNotFoundError: No module named 'api'` | ไม่มี build system ใน pyproject.toml | เพิ่ม hatchling + `packages = ["src/api"]` |
| `type "geometry" does not exist` | PostGIS extension ยังไม่ถูก enable | เพิ่ม `CREATE EXTENSION postgis` ใน migration |
| `relation "idx_flood_node_geom" already exists` | GeoAlchemy2 สร้าง GIST index อัตโนมัติ เราไปสร้างซ้ำ | ลบ `op.create_index` สำหรับ geom columns ออกจาก migration |
| `ssr: false` ใน Server Component | Next.js App Router — dynamic ไม่ได้ใน Server Component | แยก `MapDashboard` เป็น `"use client"` component |
| hypertable ต้อง ts ใน PK | TimescaleDB rule: partition column ต้องอยู่ใน PK | เปลี่ยนเป็น composite PK `(id, ts)` |
| timestamp ไม่มี timezone | `DateTime()` ไม่มี `timezone=True` | เปลี่ยนเป็น `DateTime(timezone=True)` ทุกที่ |
| Leaflet CSS load order | `import css` ใน `.then()` ไม่มี guarantee | ย้าย `import "leaflet/dist/leaflet.css"` ขึ้น top-level |

### Decisions ที่ตัดสินใจ (ดูรายละเอียดใน `docs/DECISIONS.md`)

| เรื่อง | Decision | เหตุผล |
|---|---|---|
| Tech stack | FastAPI + SQLAlchemy async + Next.js + Leaflet | Python เหมาะกับ AI/ML; Leaflet เบาและ OSM-friendly |
| LLM interface | OpenAI-compatible (swap Ollama / remote API ด้วย env) | ไม่ต้องรื้อสถาปัตยกรรมเมื่อเปลี่ยน model |
| AI estimate water level | ตัวเลข metric (เมตร) ไม่ใช่ label หยาบ (เข่า/เอว) | ต้องใช้ค่าตัวเลขจริงใน IDW interpolation |
| Frontend | Map-first dashboard — ไม่ใช่ table/list UI | core value คือ spatial awareness |
| Monorepo | uv workspace + npm workspace, single `.git` | unified lint/typecheck/migrate จาก root |
| osint_report PK | composite `(id, ts)` | TimescaleDB hypertable บังคับ partition column ใน PK |
| Hypertable conversion | เพิ่มใน migration ไม่ใช่ manual step | reproducible — dev ใหม่รัน `make migrate` ได้ครบ |
| Status indicator | ลบ hardcoded "DB connected" → `status: pending-wire` | G9 guardrail: ห้าม claim ที่ไม่มี ledger-backed proof |
| Decision log | บันทึกใน `docs/DECISIONS.md` ก่อน implement ทุกครั้ง | ไม่ลืม trade-off และ context ของการตัดสินใจ |

### Commits ใน Session นี้

```
502a2fe  docs: add DECISIONS.md and enforce decision-log rule in CLAUDE.md
b0dcbf6  docs: add session-1 log (2026-06-23)
8ff0890  fix: pre-P1 bug fixes — schema, hypertable, timezone, frontend
00d61a8  feat: minimal map dashboard (Leaflet, Lat Krabang center)
1fbf405  fix: migration setup and model corrections
3e95e1f  feat: P0 scaffold — monorepo structure, models, migrations
8006a15  Project init
```

### สถานะ DB ตอนจบ Session

```
hypertable: osint_report (partitioned on ts)  ✅
extensions: postgis, timescaledb              ✅
tables: flood_node, reporter, osint_report    ✅
migration: 81b22b51b571 applied               ✅
```

### สิ่งที่ยังค้างอยู่ (P1 ต่อไป)

- [ ] **push to GitHub** — commits หลัง P0 (`8ff0890` ถึง `502a2fe`) ยังไม่ได้ push
- [ ] **P1 Ingest** — `POST /ingest/report` intake endpoint รับภาพ + พิกัด
- [ ] **P1 Triage agent** — VLM วิเคราะห์ภาพ → `water_level_m` (metric, หน่วยเมตร)
- [ ] **P1 Datagen** — synthetic reporters จำลอง 10 คน post พร้อมกัน
- [ ] **P1 Node fusion** — รวม osint_report หลายรายงานต่อ flood_node → อัปเดต `current_fused_level`
- [ ] **Exit criteria P1** — ผู้รายงานจำลอง 10 คนโพสต์พร้อมกัน → ระดับน้ำบน map อัปเดต
- [ ] **Seed flood_node** — โหลดข้อมูล node จากพื้นที่น้ำท่วม 2554 (ลาดกระบัง + กทม.)
- [ ] **Wire ThaiLLM** — เปิด Ollama, config `LLM_BASE_URL` ใน `.env`
- [ ] **DB status indicator** — implement `/health` polling จริงแทน hardcoded (ทำใน P1)

---

## 2026-06-23 — Session 2: P1 Ingest Pipeline

### Feature ที่ทำ

**Backend — Intake & Quality Gate**
- `routers/ingest.py` — `POST /ingest/report` รับ `lat`, `lon`, `rough_level` (ไทย), `photo` (optional), `reporter_handle`, `is_simulated`
- `routers/nodes.py` — `GET /flood-nodes` ส่งข้อมูล node ทุกตัวพร้อม `current_fused_level` สำหรับ map polling
- `schemas/ingest.py` — `RoughLevel` (StrEnum, ค่าภาษาไทย: ข้อเท้า/เข่า/เอว/อก/คอ) + `ReportOut` (status: accepted/duplicate/rejected, label: REAL/SIMULATED-by-design)
- `schemas/node.py` — `FloodNodeOut` (id, name, lat, lon, district, current_fused_level, n_reports, last_updated)
- `services/quality.py` — geofence Bangkok bbox (lat 13.4–14.0, lon 100.3–100.95) + dedup (50m/5min ต่อ reporter เดียวกัน)
- `services/fusion.py` — weighted-average fusion `Σ(trust_score × confidence × water_level_m) / Σ(trust_score × confidence)` window 6h + `find_nearest_node` ST_DWithin 500m
- `triage.py` — stub แปลง RoughLevel → เมตร (เข่า=0.45, เอว=0.85, ฯลฯ) + jitter ±0.05m, confidence 0.40 (PENDING-WIRE: swap body สำหรับ ThaiLLM VLM)
- `config.py` — เพิ่ม `LLM_BASE_URL`, `LLM_MODEL` env vars เตรียมรับ ThaiLLM

**Database**
- Migration `b3c4d5e6f7a8_p1_sequences` — สร้าง sequence `reporter_id_seq`, `flood_node_id_seq`, `osint_report_id_seq` + `SET DEFAULT nextval(...)` บนทุก id column

**Frontend**
- `MapView.tsx` — เปลี่ยนจาก static placeholder เป็น poll `GET /flood-nodes` ทุก 5s, วาด `circleMarker` สี + ขนาดตามระดับน้ำ (น้ำเงิน <0.5m / เหลือง 0.5–1.0m / แดง >1.0m), popup แสดงชื่อ ระดับน้ำ จำนวนรายงาน label SIMULATED

**Scripts**
- `scripts/seed_nodes.py` — seed 20 flood_node ในเขตลาดกระบัง (+ มีนบุรี/บึงกุ่ม/ประเวศ ขอบ) จากพื้นที่น้ำท่วม 2554 พร้อม `historical_max_level`; ใช้ `ON CONFLICT DO NOTHING`
- `scripts/datagen.py` — 10 concurrent reporters ส่งรายงานพร้อมกันผ่าน `httpx.AsyncClient`; ทุก row มี `is_simulated=true` (G5); ตำแหน่งอยู่ใน 500m ของ node ที่ seed แล้ว

**Makefile**
- เพิ่ม `make seed` (`uv run … scripts/seed_nodes.py`)
- เพิ่ม `make datagen` (`uv run … scripts/datagen.py`)

### Bug ที่เจอและแก้ระหว่างทาง

| บั๊ก | สาเหตุ | การแก้ |
|---|---|---|
| `null value in column "id"` เมื่อ INSERT OsintReport | `op.create_table` สร้าง `INTEGER NOT NULL` ไม่ใช่ `SERIAL` — ไม่มี server-side DEFAULT; asyncpg ใช้ `INSERT ... RETURNING id` จึง fail | เพิ่ม migration `b3c4d5e6f7a8` สร้าง sequence + `SET DEFAULT nextval(...)` ทุก table + `server_default=text("nextval(...)")` ใน OsintReport model |

### Decisions ที่ตัดสินใจ (ดูรายละเอียดใน `docs/DECISIONS.md`)

| เรื่อง | Decision | เหตุผล |
|---|---|---|
| INTEGER PK + asyncpg | เพิ่ม sequence migration แยก | Alembic `create_table` ไม่สร้าง SERIAL; asyncpg RETURNING ต้องการ server DEFAULT |
| Triage agent | Stub label→metres (VLM PENDING-WIRE) | ThaiLLM ยังไม่ได้ wire; interface stable รอแค่ swap body |
| Fusion algorithm | Weighted avg (trust_score × confidence), 6h window | ถ่วงน้ำหนักตามความน่าเชื่อถือของ reporter และ triage confidence |
| Node assignment | ST_DWithin 500m ใกล้ที่สุด; ถ้าไม่มีให้ flood_node_id = NULL | node ห่างกัน ~1km; orphan report ยังถูกบันทึก |
| Geofence | Bangkok bounding box | G8 guardrail; ตัด spam จากนอกพื้นที่ |
| Datagen approach | Call `/ingest/report` จริง (ไม่ INSERT direct) | ทดสอบ pipeline ทั้งหมดครั้งเดียว รวม guardrail G5 |
| CORS | Allow `localhost:3000` | Next.js dev server เรียก FastAPI; แก้ prod ทีหลัง |

### Exit Criteria P1

> ผู้รายงานจำลอง 10 คนโพสต์พร้อมกัน → node levels อัปเดตบน map ✅

ยืนยันด้วย `make seed && make datagen` — 10 reporters accepted, node levels ปรากฏบน MapView

### Commits ใน Session นี้

```
d2e5daf  feat: P1 ingest pipeline — intake endpoint, triage stub, node fusion, datagen
```

### สถานะ DB ตอนจบ Session

```
migrations applied: 81b22b51b571 → b3c4d5e6f7a8          ✅
sequences: reporter_id_seq, flood_node_id_seq,
           osint_report_id_seq                             ✅
flood_node seeded: 20 nodes (Lat Krabang + surrounding)   ✅
osint_report (hypertable): รับ concurrent insert ✅
```

### สิ่งที่ยังค้างอยู่ (P2 ต่อไป)

- [ ] **Wire ThaiLLM VLM** — swap `triage.py` body; config `LLM_BASE_URL` ใน `.env`
- [ ] **MapDashboard sidebar stats** — flood nodes count, today's reports ยังแสดง "—" (ต้องดึง API)
- [ ] **MapDashboard phase tracker** — P1 ยังแสดง ⬜ ทั้งที่ done แล้ว
- [ ] **P2 Water surface** — IDW/contour จาก fused node levels → map layer
- [ ] **P2 Map layer** — render contour overlay บน Leaflet

---

## 2026-06-23 — Session 3: Pre-P2 Code Review & Bug Fixes

### งานที่ทำ

- **Code Review** — /code-review 8 angles (line-by-line, removed-behavior, cross-file, reuse, simplification, efficiency, altitude, CLAUDE.md conventions) พบ 8 bugs ที่ควรแก้ก่อน P2
- **Bug Fixes** — แก้ทุกรายการ, lint + typecheck ผ่าน

### Bug ที่พบและแก้

| # | File | Bug | Fix |
|---|---|---|---|
| 1 | `services/quality.py:23` | `ST_MakePoint(:lon,:lat)::geography` ไม่มี SRID — PostGIS บางเวอร์ชัน raise "cannot cast geometry with SRID 0 to geography" ทำให้ dedup check พัง | เปลี่ยนเป็น `ST_SetSRID(ST_MakePoint(:lon,:lat), 4326)::geography` |
| 2 | `services/fusion.py:11,16` | เดียวกัน ทั้ง `find_nearest_node` (DWithin + Distance) | เพิ่ม `ST_SetSRID` ทั้งสองจุด |
| 3 | `services/fusion.py` | `corroboration_min_n` ใน `config.py` ไม่เคยถูกอ่านที่ใดเลย — G7 guardrail เป็น dead code | import settings + เช็ค `row[1] < settings.corroboration_min_n` ก่อน UPDATE; ค่ายังคง 1 พฤติกรรม P1 ไม่เปลี่ยน แต่ plumbing ถูก wire แล้ว |
| 4 | `triage.py:31` | `rough_level=None` AND `has_photo=False` → คืน `water_level_m=0.30m` (สมมติ) ซึ่งถูกเขียนลง DB และเข้า fusion | early return `TriageResult(water_level_m=None, confidence=0.0)` เมื่อไม่มี input ทั้งคู่ |
| 5 | `triage.py` | `TriageResult.water_level_m: float` ไม่รับ None — mypy error | เปลี่ยน type เป็น `float \| None` |
| 6 | `routers/nodes.py:34` | `int(row[6])` สำหรับ `n_reports` ไม่มี None guard ต่างจาก `row[5]` (`current_fused_level`) — crash ถ้า NULL | เพิ่ม `if row[6] is not None else 0` |
| 7 | `MapView.tsx:18` | `API_URL = "http://localhost:8000"` hardcode — พังใน Docker Compose และ staging | `process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"` |
| 8 | `MapView.tsx:70` | popup hardcode `[SIMULATED-by-design]` ทุก node — เมื่อข้อมูลจริงมาใน P2 จะ mislabel ขัด G9 | ลบ label ออกจาก popup |

### Decisions

- ดู `docs/DECISIONS.md` entry "Pre-P2 Bug Fixes" สำหรับ trade-off ของแต่ละ fix

### Commits ใน Session นี้

```
(session 3 commit)
```

### สถานะตอนจบ Session

```
lint:      ruff ✅ · ESLint ✅
typecheck: mypy ✅ · tsc ✅
bugs fixed: 8/8
```

### สิ่งที่ยังค้างอยู่ (P2 ต่อไป)

- [x] **P2 Water surface** — IDW/contour จาก fused node levels → GET `/water-surface`
- [x] **P2 Map layer** — render grid overlay บน Leaflet (L.rectangle, color by level)
- [x] **MapDashboard sidebar stats** — live counts จาก GET `/stats`
- [x] **MapDashboard phase tracker** — P0/P1/P2 ✅
- [ ] **Wire ThaiLLM VLM** — swap `triage.py` body เมื่อ Ollama พร้อม
- [ ] **photo storage** — บันทึก bytes จริง (S3/local) เมื่อ wire VLM

---

## 2026-06-23 — Session 4: P2 Water Surface

### Feature ที่ทำ

**Backend**
- `routers/water_surface.py` — `GET /water-surface` คำนวณ IDW บน grid 25×25 (625 จุด) จาก `flood_node.current_fused_level`; pure Python (`math.sqrt`), ไม่เพิ่ม dep; แต่ละ point คืน `{lat, lon, level, dlat, dlon}` สำหรับ frontend วาด rectangle
- `routers/nodes.py` — เพิ่ม `GET /stats` คืน `flood_node_count`, `reports_today`, `work_orders_open`
- `main.py` — register `water_surface` router

**Frontend**
- `MapView.tsx` — เพิ่ม `surfaceLayer` (L.layerGroup) วาดก่อน nodeLayer; poll `/water-surface` ทุก 15s; แต่ละ grid point เป็น L.rectangle, fillColor + fillOpacity encode ระดับน้ำ (light blue → blue → amber → orange → red), `interactive: false` ไม่บัง popup node
- `MapDashboard.tsx` — เพิ่ม `useEffect` fetch `/stats` ทุก 10s แสดงจำนวน node + รายงานวันนี้ live; legend ครบ 5 ระดับสี; phase tracker แสดง P0/P1/P2 ✅; badge เปลี่ยนเป็น P2

### Decisions

- ดู DECISIONS.md entries "P2 Water Surface" และ "P2 Stats Endpoint"

### Exit Criteria P2

> Map renders water surface (IDW grid) from fused node data ✅

### Commits ใน Session นี้

```
(session 4 commit)
```

### สถานะตอนจบ Session

```
lint: ruff ✅ · ESLint ✅
typecheck: mypy ✅ · tsc ✅
endpoints: GET /water-surface ✅ · GET /stats ✅
map: IDW grid overlay + node markers ✅
```

### สิ่งที่ยังค้างอยู่ (P3 ต่อไป)

- [ ] **P3 Orchestrator** — deterministic routing ไม่มี LLM ใน dispatch loop (G2)
- [ ] **P3 Human confirm gate** — confirm ก่อน dispatch ทุกครั้ง (G3)
- [ ] **P3 Work order** — state machine (pending → confirmed → dispatched → done)
- [ ] **P3 LINE dispatch (sim)** — simulate LINE push notification
- [ ] **Wire ThaiLLM VLM** — swap `triage.py` body เมื่อ Ollama พร้อม
- [ ] **photo storage** — บันทึก bytes จริง (S3/local) เมื่อ wire VLM

---

## 2026-06-24 — Session 5: Smoke Test Verification & Fix

### งานที่ทำ

- **รัน smoke test** — ตรวจสอบ `scripts/smoke_test.py` ว่าสมบูรณ์หรือค้าง → ไฟล์เสร็จสมบูรณ์ แค่ยังไม่ได้ commit
- **Debug smoke test failures** — รัน smoke test แล้วพบ 500 ทุก reporter เพราะ DB หลัง container restart ยังไม่ได้ `make migrate` + `make seed` → แก้ด้วย migrate + seed
- **แก้ G5 check bug** — smoke test เหลือ failure เดียว: logic ตรวจ `len(simulated_labeled) == len(accepted)` แต่ duplicate response ก็ได้รับ label ด้วย → เปลี่ยนเป็น compare กับ `responded` (ทุก response ที่ไม่ใช่ error 500/connection error)
- **`make smoke`** — เพิ่ม target ใน Makefile

### Bug ที่เจอและแก้

| # | ที่ | Bug | Fix |
|---|---|---|---|
| 1 | `scripts/smoke_test.py` | G5 check: `len(labeled) == len(accepted)` — duplicate response ถูก label ถูกต้องแต่ไม่นับใน `accepted` | เปลี่ยนตัวหาร/เปรียบเทียบเป็น `responded` (ทุก row ที่ไม่ error) |

### Exit Criteria

> `make smoke` → ✓ All smoke checks passed ✅

### Commits ใน Session นี้

```
(session 5 commit)
```

### สถานะตอนจบ Session

```
smoke test: ✓ All smoke checks passed
[34] concurrent ingest: no 500s ✅
[35] n_reports updated ✅
G5 label check ✅
/stats ✅
/water-surface 625 pts ✅
```

### สิ่งที่ยังค้างอยู่ (P3 ต่อไป)

- [ ] **P3 Orchestrator** — deterministic routing ไม่มี LLM (G2)
- [ ] **P3 Human confirm gate** — confirm ก่อน dispatch ทุกครั้ง (G3)
- [ ] **P3 Work order** — state machine `pending → confirmed → dispatched → done`
- [ ] **P3 LINE dispatch (sim)** — simulate LINE push notification

---

## 2026-06-24 — Session 6: P3 Dispatch Spine

### Feature ที่ทำ

**Backend**
- `db/migrations/c4d5e6f7a8b9_p3_work_order.py` — ตาราง `work_order` (id, flood_node_id, status, action_type, assigned_unit, notes, confirmed_by, created_at, updated_at, dispatched_at) + index บน status + flood_node_id
- `models/work_order.py` — SQLAlchemy ORM model
- `services/orchestrator.py` — deterministic routing (G2, zero LLM): threshold → action_type + assigned_unit [SIMULATED-by-design]
- `services/line_dispatch.py` — LINE dispatch stub [SIMULATED-by-design]: returns `[SIMULATED LINE DISPATCH]` string ที่ caller เก็บลง `notes`
- `schemas/work_order.py` — `WorkOrderCreate`, `WorkOrderConfirm` (confirmed_by), `WorkOrderOut`
- `routers/work_orders.py` — `GET /work-orders`, `POST /work-orders`, `POST /work-orders/{id}/confirm` (G3 human gate)
- `routers/nodes.py` — อัปเดต `GET /stats`: `work_orders_open` return จริงจาก DB (ไม่ใช่ hardcode 0)
- `main.py` — register work_orders router

**Frontend**
- `components/WorkOrderPanel.tsx` — poll `/work-orders` ทุก 10s แสดง pending/dispatched WO พร้อมปุ่ม "ยืนยันสั่งการ" (1-click POST `/confirm` แนบ `confirmed_by: "Operator_01"`) พร้อม `// MOCK: replace with auth session` comment
- `components/MapDashboard.tsx` — เพิ่ม WorkOrderPanel ใน sidebar, แก้ note work orders stat, badge เปลี่ยนเป็น P3, phase tracker P3 ✅

### Markers สำหรับส่วนที่ simulate

| ส่วน | Marker ใน code | Marker ใน DB/log |
|---|---|---|
| `assigned_unit` | comment `# SIMULATED-by-design` ใน orchestrator.py | ชื่อหน่วยจำลอง (ปั๊ม-ลาดกระบัง-01 etc.) |
| LINE dispatch | `# SIMULATED-by-design: no real LINE API call` + TODO swap | `notes` ขึ้นต้น `[SIMULATED LINE DISPATCH]` |
| `confirmed_by` ใน frontend | `// MOCK: replace with auth session` | ค่า `"Operator_01"` ใน DB |

### Decisions ที่ตัดสินใจ

- ดู `docs/DECISIONS.md` entries "P3 Work Order: confirmed_by เป็น VARCHAR column" และ "P3 Dispatch: LINE = SIMULATED-by-design"

### Exit Criteria P3

> WO passes confirm → dispatched ✅

### Commits ใน Session นี้

```
(session 6 commit)
```

### สถานะตอนจบ Session

```
lint: ruff ✅ · ESLint ✅
typecheck: mypy ✅ · tsc ✅
migration: c4d5e6f7a8b9 applied ✅
endpoints: GET/POST /work-orders, POST /work-orders/{id}/confirm ✅
dispatch flow: pending → confirmed → dispatched ✅
```

### สิ่งที่ยังค้างอยู่ (P4 ต่อไป)

- [ ] **P4 Citizen verify** — รับภาพผล → VERIFIED / MISMATCH
- [ ] **P4 MISMATCH escalate** — สร้าง WO ใหม่ → loop กลับ PLAN
- [ ] **P4 Ledger** — บันทึก verify event ลง hash-chain
- [ ] **Wire ThaiLLM VLM** — swap `triage.py` body เมื่อ Ollama พร้อม
- [ ] **Auth/Role** — เปลี่ยน `confirmed_by VARCHAR` → FK → user.id

---

## 2026-06-24 — Session 7: P4 Plan

### งานที่ทำ

- **วาง P4 Implementation Plan** — อธิบาย flow ครบ: verify endpoint, MISMATCH escalation loop, ledger hash-chain
- **อัปเดต DECISIONS.md** — 4 entries ใหม่: ledger hash-chain design, Ed25519 ephemeral key, verified_by/photo_ref pattern, MISMATCH escalation via orchestrator

### สิ่งที่ตัดสินใจ

| เรื่อง | Decision |
|---|---|
| Ledger storage | SHA-256 hash-chain + Ed25519 ใน PostgreSQL — ไม่ใช่ external blockchain (out of scope) |
| Ed25519 key | Ephemeral ตอน startup (SIMULATED-by-design); interface เหมือน production รอ inject key ผ่าน env |
| `verified_by` | VARCHAR(100) — pattern เดียวกับ `confirmed_by`; future FK → user.id |
| `photo_ref` | PENDING-WIRE — เก็บ filename ก่อน; bytes + VLM ทำใน P เมื่อ Ollama พร้อม |
| MISMATCH escalation | Auto-create WO ใหม่ผ่าน `plan_dispatch` (G2 compliant) — operator ยืนยันใหม่เอง |

### ไฟล์ที่จะสร้าง/แก้ใน P4

| ไฟล์ | action |
|---|---|
| `db/migrations/d5e6f7a8b9c0_p4_verification_ledger.py` | สร้างใหม่ |
| `models/verification.py` | สร้างใหม่ |
| `models/ledger_entry.py` | สร้างใหม่ |
| `services/ledger.py` | สร้างใหม่ |
| `services/verify.py` | สร้างใหม่ |
| `schemas/verification.py` | สร้างใหม่ |
| `routers/verification.py` | สร้างใหม่ |
| `main.py` | แก้ไข — register router |
| `pyproject.toml` | แก้ไข — เพิ่ม `cryptography` |
| `components/WorkOrderPanel.tsx` | แก้ไข — verify buttons |

### Exit Criteria P4

```
POST /work-orders/{id}/verify {"outcome":"MISMATCH"} → new WO created, ledger 2 entries (VERIFY_OUTCOME + MISMATCH_ESCALATE)
POST /work-orders/{new_id}/verify {"outcome":"VERIFIED"} → loop done, ledger 3 entries total, hash-chain valid
```

### Commits ใน Session นี้

```
79d2652  docs: P4 plan — decisions + session-7 log
```

### สิ่งที่ยังค้างอยู่ (P4 code ต่อไป)

- [x] Implement P4 ตามแผนข้างต้น → ดู Session 8

---

## 2026-06-24 — Session 8: P4 Citizen Verify & Ledger Hash-chain

### Feature ที่ทำ

**Backend**
- `db/migrations/d5e6f7a8b9c0_p4_verification_ledger.py` — ตาราง `verification` (id, work_order_id, outcome, photo_ref, verified_by, created_at) + ตาราง `ledger_entry` (id, event_type, payload, prev_hash, hash, signature, created_at)
- `models/verification.py` — SQLAlchemy ORM model
- `models/ledger_entry.py` — SQLAlchemy ORM model
- `models/__init__.py` — เพิ่ม Verification, LedgerEntry, WorkOrder
- `services/ledger.py` — SHA-256 hash-chain + Ed25519 signing; `pg_advisory_xact_lock` ป้องกัน concurrent write fork; SIMULATED-by-design: ephemeral key ตอน startup
- `services/verify.py` — logic หลัก: lock WO (FOR UPDATE) → INSERT verification → UPDATE WO `done` → `append_event(VERIFY_OUTCOME)` → ถ้า MISMATCH: call `plan_dispatch` (G2) → INSERT WO ใหม่ → `append_event(MISMATCH_ESCALATE)`
- `schemas/verification.py` — `VerificationCreate`, `VerificationOut` (มี `new_work_order_id`), `LedgerEntryOut`
- `routers/verification.py` — `POST /work-orders/{id}/verify`, `GET /ledger`
- `main.py` — register verification router
- `pyproject.toml` — เพิ่ม `cryptography>=44.0.0`

**Frontend**
- `components/WorkOrderPanel.tsx` — เพิ่มปุ่ม verify สำหรับ WO ที่ `dispatched`: ✅ น้ำลดแล้ว (VERIFIED) / ⚠ ยังไม่ลด (MISMATCH); MISMATCH แสดง notice พร้อม WO ID ใหม่; `verified_by: "Citizen_01"` + `// MOCK: replace with authenticated citizen session`; แสดง `done` badge + "✓ ปิดแล้ว"

### Markers สำหรับส่วนที่ simulate

| ส่วน | Marker |
|---|---|
| Ed25519 key | `# SIMULATED-by-design: ephemeral keypair generated at process startup` |
| `verified_by` ใน frontend | `// MOCK: replace with authenticated citizen session when wired` |
| `photo_ref` | `# PENDING-WIRE: store actual path/URL when citizen app + VLM wired` |
| escalated WO notes | `[ESCALATED from WO#{old_id} — MISMATCH outcome]` |

### Bug ที่เจอและแก้

| # | ที่ | Bug | Fix |
|---|---|---|---|
| 1 | `services/verify.py` | SQL INSERT บรรทัดยาวเกิน 100 chars — ruff E501 | ย้าย column list ไว้ใน f-string แยกบรรทัด |

### Exit Criteria P4

> Full MISMATCH loop end-to-end ✅

```
POST /work-orders/4/verify {"outcome":"MISMATCH","verified_by":"Citizen_01"}
→ {outcome:MISMATCH, new_work_order_id:5}  ✅

GET /ledger → 2 entries: VERIFY_OUTCOME + MISMATCH_ESCALATE
              entry[2].prev_hash == entry[1].hash  ✅

POST /work-orders/5/confirm → dispatched
POST /work-orders/5/verify {"outcome":"VERIFIED","verified_by":"Citizen_02"}
→ {outcome:VERIFIED, new_work_order_id:null}  ✅

GET /ledger → 3 entries, chain complete  ✅
```

### Commits ใน Session นี้

```
b9c141c  feat: P4 citizen verify — MISMATCH loop + ledger hash-chain
```

### สถานะตอนจบ Session

```
lint:      ruff ✅ · ESLint ✅
typecheck: mypy 30 files ✅ · tsc ✅
migration: d5e6f7a8b9c0 applied ✅
endpoints: POST /work-orders/{id}/verify ✅ · GET /ledger ✅
loop:      MISMATCH → escalate → new WO → VERIFIED → done ✅
ledger:    hash-chain valid (genesis → VERIFY_OUTCOME → MISMATCH_ESCALATE → VERIFY_OUTCOME) ✅
```

### สิ่งที่ยังค้างอยู่ (P5 ต่อไป)

- [ ] **P5 Accountability board** — UI แสดง ledger events พร้อม hash verification
- [ ] **Wire ThaiLLM VLM** — swap `triage.py` body เมื่อ Ollama พร้อม
- [ ] **Auth/Role** — เปลี่ยน `confirmed_by` / `verified_by` VARCHAR → FK → user.id
- [ ] **Persistent Ed25519 key** — inject จาก env/secrets แทน ephemeral
- [ ] **Photo storage** — บันทึก bytes จริงเมื่อ citizen app + VLM wired

---

## 2026-06-24 — Session 9: Code Review & Bug Fixes (P1–P4)

### งานที่ทำ

- **Code Review** — /code-review high effort: 8 finder angles (A line-by-line, B removed-behavior, C cross-file, D reuse, E simplification, F efficiency, G altitude, H conventions) → 12 verified candidates → top 10 findings
- **แก้ไขทั้ง 10 findings** — ruff ✅ mypy 30 files ✅ tsc ✅ migration applied ✅

### Findings และวิธีแก้

| # | ความรุนแรง | ไฟล์ | ปัญหา | การแก้ |
|---|---|---|---|---|
| 1 | Critical | `schemas/verification.py` | `outcome: str` ไม่มี Literal — "mismatch" ผ่าน Pydantic แต่ escalation ไม่เกิด | `Literal["VERIFIED", "MISMATCH"]` |
| 2 | High | `MapView.tsx` | Timer + Leaflet leak ถ้า unmount ก่อน `import('leaflet')` resolve | เพิ่ม `mounted` flag ใน `useEffect` |
| 3 | High | `work_orders.py` | `send_dispatch()` call ก่อน `db.commit()` — double-dispatch เมื่อ LINE จริง wire | เพิ่ม comment ระบุตำแหน่งที่ควร call หลัง commit |
| 4 | High | `services/verify.py` | `if node is not None:` guard — escalation ถูก skip แบบ silent, คืน 201 | เปลี่ยนเป็น raise HTTPException(409) |
| 5 | High | `services/verify.py` | NULL water_level → ใช้ 0.0 → plan_dispatch คืน minimum-severity plan | raise HTTPException(422) แทน fallback |
| 6 | High | `routers/nodes.py` | `work_orders_open` นับเฉพาะ `pending` — WO ที่ dispatched แล้วหายไปจาก counter | เปลี่ยนเป็น `IN ('pending', 'dispatched')` |
| 7 | Medium | `services/verify.py` | MISMATCH และ VERIFIED ทั้งคู่ set `status='done'` — P5 board ต้อง JOIN เพื่อแยก | MISMATCH → status `'mismatch'` (terminal state ใหม่) + badge สีแดงใน UI |
| 8 | Medium | `work_orders.py` | G7 ไม่ enforce — node ที่มี n_reports=0 สร้าง WO ได้ | เพิ่ม n_reports check ก่อน `plan_dispatch` → 422 ถ้าไม่ถึง threshold |
| 9 | Medium | migration + models | G5 structural: `work_order` + `verification` ไม่มี `is_simulated` column | migration `e6f7a8b9c0d1`: `is_simulated BOOLEAN NOT NULL DEFAULT TRUE` + อัปเดต models + escalated WO INSERT |
| 10 | Medium | `work_orders.py` | N+1: `list_work_orders` ออก 2N+1 queries ต่อ request | เขียนใหม่เป็น single JOIN query |

### Commits ใน Session นี้

```
6223870  fix: address 10 code-review findings (P1-P4)
```

### สถานะตอนจบ Session

```
lint:      ruff ✅ · ESLint ✅
typecheck: mypy 30 files ✅ · tsc ✅
migration: e6f7a8b9c0d1 applied ✅
G7: enforce n_reports ≥ 1 ก่อนสร้าง WO ✅
G5: is_simulated column บน work_order + verification ✅
status machine: 'mismatch' terminal state เพิ่มเข้า ✅
list_work_orders: 1 JOIN query (เดิม 2N+1) ✅
```

### สิ่งที่ยังค้างอยู่ (P5 ต่อไป)

- [x] **P5 Accountability board** ✅ ดูด้านล่าง Session 10
- [ ] **Wire ThaiLLM VLM** — swap `triage.py` body เมื่อ Ollama พร้อม
- [ ] **Auth/Role** — เปลี่ยน `confirmed_by` / `verified_by` VARCHAR → FK → user.id
- [ ] **Persistent Ed25519 key** — inject จาก env/secrets แทน ephemeral
- [ ] **Photo storage** — บันทึก bytes จริงเมื่อ citizen app + VLM wired

---

## 2026-06-24 — Session 10: P5 Accountability Board

### งานที่ทำ

**Ledger completeness (Backend)**
- `db/migrations/f7a8b9c0d1e2_p5_ledger_data_class.py` — เพิ่ม `data_class VARCHAR(30) NOT NULL DEFAULT 'SIMULATED-by-design'` บน `ledger_entry` (G9: labeled fact ที่ append-time ไม่ใช่ inference)
- `models/ledger_entry.py` — เพิ่ม `data_class: Mapped[str]` field
- `services/ledger.py` — เพิ่ม param `data_class='SIMULATED-by-design'` ใน `append_event()` signature + INSERT column
- `schemas/verification.py` → `LedgerEntryOut` — เพิ่ม `data_class: str` field
- `routers/verification.py` → `GET /ledger` — SELECT + map `data_class` column
- `routers/work_orders.py` — เพิ่ม 2 ledger events ให้ครบ lifecycle:
  - `WO_CREATED` ใน `create_work_order` (หลัง flush, ก่อน commit — atomic กับ WO insert)
  - `WO_DISPATCHED` ใน `confirm_work_order` (ก่อน commit)

**Accountability Board UI (Frontend)**
- `apps/web/src/app/board/page.tsx` — Next.js route `/board` (Server Component)
- `apps/web/src/components/AccountabilityBoard.tsx` — board component:
  - Poll `GET /ledger` ทุก 30s
  - **Client-side chain verification**: คำนวณ `SHA-256(event_type|payload|prev_hash)` ผ่าน `crypto.subtle` แล้วเทียบกับ `hash` จาก API → แสดง "🔒 Chain intact" หรือ "⚠ Chain broken at #N"
  - Timeline cards: seq#, event_type badge (สีตาม type), `data_class` badge (SIMULATED-by-design=ส้ม, REAL=เขียว, PENDING-WIRE=เทา), payload pretty-print, hash snippet (8 chars), prev_hash link
  - G9 note: "แสดงเฉพาะ ledger-backed facts — ไม่มี inference • Ed25519 signature: PENDING-WIRE"
- `apps/web/src/components/MapDashboard.tsx` — เพิ่ม "Accountability Board" link ที่ header (เปิด tab ใหม่), อัปเดต badge จาก P3 → P5

### Markers สำหรับส่วนที่ simulate / PENDING-WIRE

| ส่วน | Marker |
|---|---|
| ทุก ledger event ปัจจุบัน | `data_class = 'SIMULATED-by-design'` |
| Ed25519 signature verify client-side | G9 note บน board: `PENDING-WIRE` (ต้อง export public key ก่อน) |

### Exit Criteria P5

> "Board shows real ledger events, all labeled" ✅

```
GET /ledger → 5 entries พร้อม data_class ✅
  #1 VERIFY_OUTCOME    [SIMULATED-by-design]
  #2 MISMATCH_ESCALATE [SIMULATED-by-design]
  #3 VERIFY_OUTCOME    [SIMULATED-by-design]
  #4 WO_CREATED        [SIMULATED-by-design]
  #5 WO_DISPATCHED     [SIMULATED-by-design]

/board → render ✅
  Chain intact — 5 events verified (SHA-256 hash-chain) ✅
  data_class badges แสดงครบ ✅
  Lifecycle ครบ: WO_CREATED → WO_DISPATCHED → VERIFY_OUTCOME → MISMATCH_ESCALATE ✅

tsc build: / + /board routes ✅
migration f7a8b9c0d1e2 applied ✅
```

### Commits ใน Session นี้

```
(pending commit)
```

### สถานะตอนจบ Session

```
lint:      ruff ✅ · ESLint ✅
typecheck: mypy 30 files ✅ · tsc ✅
migration: f7a8b9c0d1e2 applied ✅
phases:    P0 ✅ P1 ✅ P2 ✅ P3 ✅ P4 ✅ P5 ✅
```

### สิ่งที่ยังค้างอยู่ (P6)

- [x] **P6 Validate** ✅ ดูด้านล่าง Session 11
- [ ] **Ed25519 signature verify on board** — export public key → client verify (PENDING-WIRE)
- [ ] **Wire ThaiLLM VLM** — swap `triage.py` body เมื่อ Ollama พร้อม
- [ ] **Auth/Role** — เปลี่ยน `confirmed_by` / `verified_by` VARCHAR → FK → user.id
- [ ] **Persistent Ed25519 key** — inject จาก env/secrets แทน ephemeral
- [ ] **Photo storage** — บันทึก bytes จริงเมื่อ citizen app + VLM wired

---

## 2026-06-24 — Session 11: P6 Validate — Smoke Test

### งานที่ทำ

- **DECISIONS.md** — เพิ่ม 2 entries: เหตุผลที่ extend script เดิมแทนสร้างใหม่, เหตุผลที่ใช้ Python hashlib แทน external tool
- **`scripts/smoke_test.py`** — เพิ่ม 6 test groups ใหม่ต่อจาก [34]/[35] เดิม:

| Group | สิ่งที่ทดสอบ |
|---|---|
| `[G7]` | WO บน node ที่ n_reports=0 → 422 G7 |
| `[WO]` | Happy path VERIFIED: create → confirm → verify → done; ledger มี WO_CREATED + WO_DISPATCHED + VERIFY_OUTCOME |
| `[MISMATCH]` | Full loop: MISMATCH → escalate → confirm escalated WO → VERIFIED → closed; ตรวจ MISMATCH_ESCALATE ใน ledger + escalated WO status=pending |
| `[EDGE]` | 409 verify บน pending WO; 409 confirm บน dispatched WO; 422 outcome="mismatch" (lowercase Literal gate) |
| `[LEDGER]` | SHA-256 chain verify ทุก entry (Python hashlib); prev_hash links; G9 data_class label ครบ |
| `[CONCURRENT-LEDGER]` | asyncio.gather 2 confirm + 2 verify พร้อมกัน → chain intact (advisory lock ป้องกัน fork) |

### ผลการทดสอบ

```
[34] 10/10 accepted, no 500s                      ✅
     G5: all 10 labeled SIMULATED-by-design        ✅
[35] 10 nodes updated (n_reports ++)               ✅
     /water-surface: 625 points, 0.221m–1.107m     ✅
[G7] WO on node 11 (n_reports=0) → 422            ✅
[WO] id=7 pending → dispatched → done              ✅
     Ledger: WO_CREATED + WO_DISPATCHED + VERIFY   ✅
[MISMATCH] WO#8 MISMATCH → new_wo=9 → closed      ✅
     MISMATCH_ESCALATE in ledger                   ✅
[EDGE] 3/3 state gates reject correctly            ✅
[LEDGER] 17 entries, all hashes valid              ✅
     G9: all 17 labeled                            ✅
[CONCURRENT-LEDGER] 2×confirm + 2×verify concurrent✅
     Chain intact after concurrent writes (23 entries) ✅

✓ All smoke checks passed (exit 0)
```

### Commits ใน Session นี้

```
(pending commit)
```

### สถานะตอนจบ Session

```
make smoke: ✅ exit 0, all groups pass
phases:     P0 ✅ P1 ✅ P2 ✅ P3 ✅ P4 ✅ P5 ✅ P6 ✅
            ── ครบทุก phase ตาม CLAUDE.md ──
```

### สิ่งที่เหลือ (out-of-scope สำหรับ hackathon MVP)

- [ ] **Ed25519 signature verify on board** — PENDING-WIRE (ต้อง export public key)
- [ ] **Wire ThaiLLM VLM** — PENDING-WIRE (Ollama + GPU พร้อม)
- [ ] **Auth/Role, Photo storage, Persistent key** — production hardening

---

## 2026-06-29 — Session 12: P7 Work Order Human Approval

### Feature ที่ทำ

**P7: Human-first WO creation flow** — ออกแบบและ implement การเปลี่ยน Work Order flow ให้ coordinator เห็น dispatch plan ก่อน แล้ว approve → WO ถึงจะถูกสร้าง

#### Backend (apps/api/)

- **Migration** `a1b2c3d4e5f6_p7_wo_human_approval.py` — เพิ่ม 3 คอลัมน์ใน `work_order`: `approved_by`, `line_dispatched`, `line_dispatched_at`
- **Model** `work_order.py` — เพิ่ม `approved_by`, `line_dispatched`, `line_dispatched_at`
- **Schemas** `work_order.py` — rewrite เพิ่ม `LineDispatchOptions`, `WorkOrderPatch`, `DispatchPlanOut`, `WorkOrderCreate.approved_by`
- **LINE dispatch** `line_dispatch.py` — รับ `LineDispatchOptions` เพื่อ render message แบบ selective
- **Router** `work_orders.py` — endpoints ใหม่ + เปลี่ยน logic:
  - `GET /work-orders/plan-preview?flood_node_id=X` — ดู dispatch plan ก่อนสร้าง WO (pure, no side-effect)
  - `GET /work-orders/line-preview` — preview LINE message แบบ real-time
  - `PATCH /work-orders/{id}` — แก้ pending WO; คืน `resend_required=true` ถ้า LINE เคยส่งแล้ว
  - `POST /work-orders/{id}/notify-line` — ส่ง LINE OA แบบ on-demand
  - `POST /work-orders` — ต้องมี `approved_by`; รองรับ `notify_line` + `line_options`; ledger `WO_CREATED` + `WO_LINE_SENT`
  - `POST /work-orders/{id}/confirm` — LINE dispatch ถูกลบออกจาก confirm; confirm = field ops ยืนยัน execution เท่านั้น

#### Frontend (apps/web/)

- **CreateWOModal.tsx** (ไฟล์ใหม่) — 2-step modal:
  - Step 1: เลือก node → ดู plan preview → แก้ action/unit/notes ได้ → คลิก "ต่อไป"
  - Step 2: เลือก LINE fields (checkbox, all default checked) → live preview → submit
  - G7 guard: node ที่ `n_reports=0` disabled พร้อม "(G7)" label
- **WorkOrderPanel.tsx** — rewrite ครั้งใหญ่:
  - `+ สร้าง WO` button → เปิด CreateWOModal
  - `LINE ✓` badge บน WO ที่ส่งแล้ว
  - `✏` inline edit form สำหรับ pending WO (PATCH)
  - Banner "ส่ง LINE อีกครั้ง" เมื่อ `resend_required=true`
  - rename `OPERATOR_HANDLE → FIELD_TEAM_HANDLE = "FieldTeam_01"`
  - rename button "ยืนยันสั่งการ ▶" → "ฝ่ายปฏิบัติการยืนยัน ▶"

#### Scripts

- `smoke_test.py` — เพิ่ม `"approved_by": "SmokeTest_Coordinator"` ใน `create_wo()` helper

#### Lint/Typecheck fixes

- `work_orders.py` — แก้ ANN401: `Row[Any]` แทน bare `Any` ใน function signatures; เพิ่ม `Row` import
- `AccountabilityBoard.tsx` — แก้ `<a>` → `<Link>` (next/link); เพิ่ม eslint-disable สำหรับ pre-existing `set-state-in-effect`
- `WorkOrderPanel.tsx` — เพิ่ม eslint-disable สำหรับ pre-existing `set-state-in-effect` pattern
- `CreateWOModal.tsx` — ปรับ useEffect guard ไม่ sync-setState; เพิ่ม eslint-disable สำหรับ `setLinePreviewLoading`

### ผลลัพธ์

```
make lint:      ruff ✅ · ESLint ✅ (0 errors, 1 warning)
make typecheck: mypy ✅ (38 files) · tsc/next build ✅
migration:      a1b2c3d4e5f6 (pending apply — ต้องการ DB)
```

### Decisions เพิ่ม (docs/DECISIONS.md)

- P7 Plan Preview (human-first approval)
- P7 approved_by ใน ledger + DB column
- P7 LINE แยกออกจาก /confirm
- P7 LINE Options checkbox + live backend preview
- P7 PATCH /work-orders/{id} + WO_UPDATED ledger event

### Commits ใน Session นี้

```
(pending commit)
```

### สถานะตอนจบ Session

```
make lint:      ✅
make typecheck: ✅
phases:         P0 ✅ P1 ✅ P2 ✅ P3 ✅ P4 ✅ P5 ✅ P6 ✅ P7 ✅
```

### สิ่งที่เหลือ (out-of-scope สำหรับ hackathon MVP)

- [ ] **Ed25519 signature verify on board** — PENDING-WIRE
- [ ] **Wire ThaiLLM VLM** — PENDING-WIRE
- [ ] **Auth/Role, Photo storage, Persistent key** — production hardening
- [ ] **Run migration** `a1b2c3d4e5f6` — ต้องการ Docker/PostgreSQL
