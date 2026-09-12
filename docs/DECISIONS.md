# Decision Log

บันทึกการตัดสินใจทางสถาปัตยกรรมและ design ทุกรายการ
**ห้าม overwrite log เดิม — append เท่านั้น**

---

## 2026-06-23 — Tech Stack: Python + FastAPI สำหรับ Backend

- เหตุผล: Python เหมาะกับ AI/ML integration (VLM, LLM, embedding) ที่เป็นหัวใจของระบบ FastAPI รองรับ async และมี OpenAPI docs built-in
- trade-off: Node.js จะ share language กับ frontend แต่ ecosystem สำหรับ GeoAlchemy/PostGIS/pgvector ใน Python สมบูรณ์กว่ามาก

## 2026-06-23 — Tech Stack: Next.js + Leaflet สำหรับ Frontend

- เหตุผล: Next.js App Router รองรับ Server/Client Component แยกชัด ไม่ต้อง config SSR เอง Leaflet เบา ฟรี tile จาก OpenStreetMap เหมาะ pilot
- trade-off: deck.gl render performance ดีกว่าเมื่อ point count สูงมาก แต่ learning curve สูงกว่าและ overkill สำหรับ pilot 1 เขต

## 2026-06-23 — Database: TimescaleDB + PostGIS บน PostgreSQL เดียวกัน

- เหตุผล: ลด infrastructure complexity — ได้ทั้ง time-series (hypertable, chunk pruning) และ spatial (PostGIS, ST_DWithin) ใน connection เดียว
- trade-off: ถ้า scale ต้องแยก อาจต้องย้าย time-series ออก แต่ hackathon scope ไม่ถึง

## 2026-06-23 — LLM Interface: OpenAI-compatible (Ollama-swappable)

- เหตุผล: ไม่ผูกกับ vendor ใด เปลี่ยนระหว่าง Ollama local, ThaiLLM API, หรือ OpenAI ได้ด้วย env variable ไม่ต้องรื้อ code
- trade-off: ต้อง normalize response format เอง ถ้า provider มี API quirk

## 2026-06-23 — AI Water Level: ตัวเลข metric (เมตร) ไม่ใช่ label หยาบ

- เหตุผล: ค่าตัวเลขจริงจำเป็นสำหรับ IDW interpolation และ fusion หาก VLM ส่งแค่ "เข่า/เอว" ไม่สามารถคำนวณ water surface ได้
- trade-off: VLM ประมาณค่าตัวเลขจากภาพมี error margin สูง ต้องใช้ confidence score ประกอบและต้อง corroborate ≥ N รายงาน

## 2026-06-23 — Frontend: Map-first Dashboard

- เหตุผล: Core value ของ Floodtir คือ spatial awareness — รู้ว่าน้ำอยู่ที่ไหน ระดับเท่าไหร่ สั่งงานที่ไหน table/list UI ไม่ตอบโจทย์นี้
- trade-off: map component ซับซ้อนกว่า ต้อง handle SSR (Leaflet ไม่รัน server-side)

## 2026-06-23 — Monorepo: uv workspace + npm workspace, single git root

- เหตุผล: lint/typecheck/migrate รันจาก root ด้วย `make` คำสั่งเดียว shared ruff/mypy config ไม่ต้อง duplicate ต่อ package
- trade-off: developer ต้อง familiar กับ uv workspace concept เพิ่มขึ้นเล็กน้อย

## 2026-06-23 — osint_report Primary Key: Composite (id, ts)

- เหตุผล: TimescaleDB บังคับให้ partition column (`ts`) ต้องอยู่ใน primary key หรือ unique constraint ก่อน `create_hypertable` จะสำเร็จ
- trade-off: FK reference จาก table อื่นต้องระบุทั้ง `id` และ `ts` ซับซ้อนขึ้นเล็กน้อย

## 2026-06-23 — hypertable ใน Migration ไม่ใช่ Manual Step

- เหตุผล: `SELECT create_hypertable(...)` อยู่ใน Alembic migration ทำให้ `make migrate` ครั้งเดียวได้ DB ครบ reproducible สำหรับ dev ใหม่และ CI
- trade-off: migration file ผูกกับ TimescaleDB — รัน offline บน vanilla PostgreSQL ไม่ได้

## 2026-06-23 — Status Indicator: ลบ hardcoded "DB connected"

- เหตุผล: G9 guardrail ระบุว่าห้าม claim ที่ไม่มี ledger-backed proof แสดง green dot ตลอดเวลาโดยไม่มี health check จริงเป็นการ mislead โดยเฉพาะต่อหน้า judge
- trade-off: ต้อง implement `/health` API polling แยกต่างหากใน P1+ เพื่อให้ status indicator มีความหมายจริง

## 2026-06-23 — P1 Migration: Sequences สำหรับ INTEGER PK

- เหตุผล: `op.create_table` ใน Alembic สร้าง `INTEGER NOT NULL` ไม่ใช่ `SERIAL` — ไม่มี server-side sequence; SQLAlchemy async (asyncpg) ใช้ `INSERT ... RETURNING id` ซึ่งต้องการ DEFAULT บนคอลัมน์ ถ้าไม่มีจะ fail ด้วย null violation
- trade-off: migration เพิ่มเติม 1 ไฟล์; ถ้า Alembic version ใหม่สร้าง SERIAL อยู่แล้ว ก็เป็น no-op เพราะใช้ `IF NOT EXISTS`

## 2026-06-23 — P1 Triage Agent: Stub Label→Metres (VLM PENDING-WIRE)

- เหตุผล: ThaiLLM 30B ยังไม่ได้ wire; ต้องการ metric value (เมตร) สำหรับ fusion/IDW; stub maps label หยาบ (เข่า/เอว/ข้อเท้า/อก/คอ) → float metres พร้อม jitter เล็กน้อยเพื่อความสมจริง; interface เหมือนกันทุกอย่าง เมื่อ wire VLM แค่แทน function body
- trade-off: confidence stub คงที่ที่ 0.40-0.45; ค่าตัวเลขไม่แม่นยำ แต่เพียงพอสำหรับ fusion ใน P1

## 2026-06-23 — P1 Node Fusion: Weighted Average (trust_score × confidence), 6h Window

- เหตุผล: การ fuse หลายรายงานต่อ flood_node ด้วย weighted average ถ่วงน้ำหนักด้วย trust_score ของ reporter และ confidence ของ triage ให้ผลที่สมเหตุสมผลกว่า simple average; 6h window เพราะสถานการณ์น้ำท่วมเปลี่ยนแปลงในระดับชั่วโมง
- trade-off: IDW spatial interpolation (P2) แม่นยำกว่าสำหรับ water surface แต่ต้องการ node หลายตัว; P1 ใช้ weighted avg ต่อ node ได้ก่อน

## 2026-06-23 — P1 Node Assignment: ST_DWithin 500m ใกล้ที่สุด

- เหตุผล: รายงานต้องผูกกับ flood_node เพื่อให้ fusion ทำงานได้; 500m เหมาะสำหรับ node spacing ในเขตเมือง (node ห่างกันประมาณ 1km); ถ้าไม่มี node ใน 500m รายงานยังถูกบันทึกแต่ flood_node_id = NULL
- trade-off: บางรายงานชายขอบอาจ orphan; แก้ได้ด้วยการเพิ่ม node coverage

## 2026-06-23 — P1 Geofence: Bangkok Bounding Box

- เหตุผล: G8 guardrail ต้องการ quality gate; ตัดรายงานนอก Bangkok (lat 13.4–14.0, lon 100.3–100.95) ออกเพื่อป้องกัน spam และ sybil attacks จากนอกพื้นที่
- trade-off: bbox หยาบ ครอบคลุม provinces บางส่วนรอบ กทม.; สำหรับ pilot ยอมรับได้ก่อน

## 2026-06-23 — P1 Datagen: Async httpx ต่อ Real API (ไม่ Insert Direct)

- เหตุผล: datagen ที่ call /ingest/report endpoint จริงทดสอบ pipeline ทั้งหมด (geofence→triage→fusion→commit) ได้ครบในครั้งเดียว; การ insert direct ลัดขั้นตอนและไม่ได้ validate guardrails; G5: is_simulated=true ทุกแถว
- trade-off: ต้องรัน API server ก่อน datagen; แก้ด้วย make target ที่ระบุ prerequisite

## 2026-06-23 — P2 Water Surface: IDW Pure Python, 25×25 Grid, L.rectangle Overlay

- เหตุผล: IDW (Inverse Distance Weighting) คำนวณ water surface จาก fused node levels โดยไม่ต้องการ numpy/scipy — pure Python + math.sqrt เพียงพอสำหรับ 25×25=625 grid points กับ 20 nodes ใน Lat Krabang; render เป็น L.rectangle บน Leaflet โดยไม่ต้องการ package ใหม่ (leaflet.heat หรือ deck.gl)
- trade-off: L.rectangle 625 ชิ้นใช้ DOM มากกว่า canvas-based heatmap แต่ไม่ต้องเพิ่ม npm dep และ debug ง่ายกว่า; ถ้า performance ไม่ดีค่อยเปลี่ยนเป็น canvas layer ใน P5+

## 2026-06-23 — P2 Stats Endpoint: GET /stats สำหรับ Sidebar Live Counts

- เหตุผล: MapDashboard sidebar ต้องการ flood_node count และ today's report count แบบ live — แยก endpoint `/stats` ไว้แทนที่จะให้ frontend count จาก /flood-nodes response เพื่อให้ backend เพิ่ม logic (เช่น filter REAL only) ได้ภายหลังโดยไม่แตะ frontend
- trade-off: เพิ่ม endpoint หนึ่งตัว แต่ separation of concerns ชัดกว่า

## 2026-06-23 — Pre-P2 Bug Fixes: ST_MakePoint SRID, corroboration gate, triage None, photo ref, popup label

- เหตุผล: code review พบ 8 bugs ก่อน P2 — (1) ST_MakePoint ไม่มี ST_SetSRID ทำให้ PostGIS บางเวอร์ชัน raise error บน geography cast; (2) corroboration_min_n ใน config ไม่เคยถูกอ่าน G7 จึงไม่มีผล; (3) triage() คืน 0.30m เสมอแม้ไม่มี input ทำให้ fusion เจือด้วยข้อมูลสมมติ; (4) photo bytes ไม่เคยถูกอ่าน — VLM จะไม่มี bytes เมื่อ wire; (5) n_reports ไม่มี None guard ต่างจาก current_fused_level; (6) popup hardcode [SIMULATED-by-design] ขัด G9 เมื่อข้อมูลจริงมาใน P2; (7) API_URL hardcode localhost:8000; (8) triage redundant None guard
- trade-off: (2) corroboration_min_n=1 ยังคงค่าเดิม พฤติกรรม P1 ไม่เปลี่ยน แต่ plumbing ถูก wire แล้ว; (4) photo_ref ยังเก็บ filename ไว้ก่อน — storage layer เพิ่มใน P2 เมื่อ wire VLM จริง

## 2026-06-24 — P2 water_surface: Computed On-the-fly แทน DB Table

- เหตุผล: CLAUDE.md Key Tables ระบุ `water_surface` เป็น table ที่ persist ใน DB และ "regenerated on ingest" แต่ในทางปฏิบัติการ persist grid 625 จุดทุกครั้งที่มี ingest ต้องการ migration เพิ่มและ schema ใหม่ โดยไม่ได้ให้ประโยชน์จริงเพราะ IDW คำนวณเร็วมาก (<5ms สำหรับ 20 nodes); `GET /water-surface` คำนวณ on-the-fly ทุก request และ frontend poll เองทุก 15s
- trade-off: ไม่มี history ของ water surface — ถ้าต้องการ replay หรือ audit ต้อง recompute จาก osint_report; ถ้า node มากขึ้นหรือ grid ใหญ่ขึ้นอาจต้อง cache ใน P5+

## 2026-06-23 — P1 CORS: Allow localhost:3000

- เหตุผล: Next.js dev server (port 3000) เรียก FastAPI (port 8000); ต้องเปิด CORS ไม่งั้น browser block
- trade-off: production ต้องเปลี่ยนเป็น actual domain; ตอนนี้ hardcode localhost:3000 ไปก่อน

## 2026-06-24 — P3 Work Order: confirmed_by เป็น VARCHAR column (ไม่ใช่ notes)

- เหตุผล: เก็บ confirmed_by แยก column เพื่อให้ JOIN กับ user table ได้ง่ายในอนาคต ถ้าใส่ไว้ใน notes ต้อง parse text ซึ่ง fragile; ตอนนี้เป็น VARCHAR รับ operator handle เช่น "Operator_01"; เมื่อ Auth พร้อมแค่ migrate column เป็น FK → user.id
- trade-off: schema มี column ที่ไม่ได้ enforce FK ตอนนี้ — รับได้เพราะ P3 scope ยังไม่มี user table; frontend hardcode "Operator_01" + comment // MOCK: replace with auth session

## 2026-06-24 — P3 Dispatch: LINE = SIMULATED-by-design, marker ใน code + DB

- เหตุผล: LINE Notify / Messaging API ยังไม่ wire; ต้องมี marker ชัดเจนทั้งใน code (comment) และใน DB (notes ขึ้นต้น [SIMULATED LINE DISPATCH]) เพื่อให้ผู้ตรวจสอบ/judge เห็นทันทีว่าส่วนใดยังเป็น simulation
- trade-off: line_dispatch.py เป็น stub ทั้งไฟล์ — swap body เดียวเมื่อ LINE API พร้อม; interface เหมือนกัน

## 2026-06-24 — Smoke Test: G5 Check Logic Fix

- เหตุผล: G5 check เปรียบ `len(simulated_labeled)` กับ `len(accepted)` แต่ duplicate response ก็ได้รับ label SIMULATED-by-design ด้วย — ทำให้ 10 labeled != 8 accepted แม้ label ถูกต้องทุก row; ควรตรวจว่า **ทุก response ที่ไม่ error** (รวม duplicate) มี label ถูก ไม่ใช่แค่ accepted
- trade-off: ไม่มี — นี่คือ fix bug ใน test logic ล้วนๆ ไม่กระทบ production code

## 2026-06-24 — P4 Ledger: SHA-256 hash-chain + Ed25519 ใน PostgreSQL (ไม่ใช่ external blockchain)

- เหตุผล: CLAUDE.md ระบุ "Blockchain out of scope — hash-chain in PostgreSQL is sufficient"; `ledger_entry` table เก็บ `prev_hash` (SHA-256 hex ของ entry ก่อนหน้า) และ `hash` (SHA-256 ของ event_type + payload + prev_hash) ทำให้ตรวจสอบความต่อเนื่องได้โดยไม่ต้อง external consensus; Ed25519 signature แนบทุก entry เพื่อพิสูจน์ว่า event ถูกสร้างโดย server key จริง
- trade-off: ถ้า DB ถูก compromise ทั้งหมด hash-chain ก็ถูก tamper พร้อมกันได้ — แก้ได้ด้วย external anchor (IPFS/public chain) ใน production แต่ out of scope สำหรับ hackathon pilot

## 2026-06-24 — P4 Ledger: Ed25519 Ephemeral Key (SIMULATED-by-design)

- เหตุผล: การ persist private key ต้องการ secrets management (HSM, KMS, Vault) ซึ่ง out of scope P4; ใช้ `cryptography` package สร้าง keypair ตอน API startup แทน — key หายทุกครั้งที่ restart แต่ chain ยังตรวจสอบ integrity ได้ภายใน session; ยืนยันว่า interface เหมือน production ทุกอย่าง เพียงแต่ key ไม่ persistent
- trade-off: signature ไม่สามารถ verify ข้าม server restart ได้; แก้ด้วยการ inject persistent key via env variable เมื่อพร้อม — code ไม่ต้องเปลี่ยน

## 2026-06-24 — P4 Verification: verified_by + photo_ref Design

- เหตุผล: `verified_by` ใช้ pattern เดียวกับ `confirmed_by` — VARCHAR(100) รับ handle ก่อน, migrate เป็น FK → user.id เมื่อ auth พร้อม; `photo_ref` เก็บ filename/reference ไว้ก่อน (PENDING-WIRE) เพราะ bytes storage + VLM ยังไม่ wire — interface stable รอแค่ swap implementation
- trade-off: photo_ref ไม่มี actual bytes ใน P4 — triage ยังรัน stub เหมือน P1; ยอมรับได้เพราะ exit criteria P4 คือ loop ครบ ไม่ใช่ accuracy ของ VLM

## 2026-06-24 — P4 MISMATCH Escalation: Auto-create WO ผ่าน Orchestrator เดิม (G2)

- เหตุผล: เมื่อ outcome = MISMATCH ระบบต้องสร้าง WO ใหม่สำหรับ flood_node เดิมทันที — ใช้ `plan_dispatch` (orchestrator.py) โดยตรงเพื่อรักษา G2 (deterministic, zero LLM); WO ใหม่ขึ้นเป็น `pending` ปรากฏใน WorkOrderPanel รอ operator ยืนยันใหม่; เก็บ `[ESCALATED from WO#{old_id}]` ใน notes เพื่อ traceability
- trade-off: ไม่มี cooldown หรือ cap จำนวน escalation — อาจ loop ไม่สิ้นสุดถ้า pump ไม่ทำงานจริง; แก้ได้ด้วย `escalation_count` guard ใน P6 validate

## 2026-06-24 — Code Review Fix: outcome Literal Type ใน VerificationCreate

- เหตุผล: `outcome: str` ผ่าน Pydantic ได้ทุกค่า — "mismatch" (lowercase) จะผ่าน validation แต่ `if outcome == "MISMATCH"` ใน `verify.py` เป็น False → escalation ไม่เกิด, ledger บันทึก outcome ที่ไม่ valid, คืน 201 ราวกับสำเร็จ; เปลี่ยนเป็น `Literal["VERIFIED", "MISMATCH"]` ให้ Pydantic reject ที่ layer นี้ก่อนถึง service
- trade-off: API contract เข้มขึ้น — client ที่ส่งค่า case-insensitive จะได้ 422 แทนที่จะ silently succeed

## 2026-06-24 — Code Review Fix: 'mismatch' เป็น Terminal State แยกจาก 'done'

- เหตุผล: เดิม MISMATCH และ VERIFIED ทั้งคู่ set `status='done'` — P5 accountability board ต้อง JOIN `verification` table ทุกครั้งเพื่อแยกว่า WO นั้น resolved อย่างไร; เพิ่ม `'mismatch'` เป็น terminal state แยก ทำให้ state machine สะท้อน outcome ได้โดยตรงที่ WO level (VARCHAR(20) รองรับอยู่แล้ว ไม่ต้องทำ migration)
- trade-off: state machine มี 5 states แทน 4 (`pending → dispatched → done|mismatch`); client ที่ hardcode `status == 'done'` จะพลาด mismatch WOs — แก้ได้ด้วยการใช้ STATUS_BADGE dictionary ที่ครอบคลุมทุก state

## 2026-06-24 — Code Review Fix: G7 Enforce n_reports ก่อนสร้าง WO

- เหตุผล: CLAUDE.md G7 "A single report never triggers action alone. Corroboration ≥ N required" ไม่ถูก enforce ใน `POST /work-orders` — `_get_node_row` ไม่ fetch `n_reports`; เพิ่ม query แยกในขั้นตอนก่อน `plan_dispatch` เพื่อตรวจ `n_reports >= settings.corroboration_min_n`; ปัจจุบัน threshold = 1 (พฤติกรรมเดิม) แต่ plumbing ถูก wire แล้ว
- trade-off: query เพิ่มขึ้น 1 รายการต่อ `POST /work-orders`; ยอมรับได้เพราะ WO creation ไม่ใช่ hot path

## 2026-06-24 — Code Review Fix: G5 is_simulated Column บน work_order + verification

- เหตุผล: CLAUDE.md G5 "Every simulated data row must carry is_simulated = true" — ตาราง `work_order` และ `verification` ไม่มี column นี้ตั้งแต่ P3/P4; P5 accountability board จะไม่สามารถ filter REAL vs SIMULATED ใน command/verify path ได้; เพิ่มผ่าน migration `e6f7a8b9c0d1` ด้วย `DEFAULT TRUE` (ทุก row ปัจจุบัน + อนาคต P1–P4 เป็น SIMULATED-by-design)
- trade-off: column เพิ่ม 1 bit ต่อ row; เมื่อ wire ระบบจริง แถว REAL ต้องส่ง `is_simulated=False` อย่างชัดเจน

## 2026-06-24 — P5 Accountability Board: Route /board แยกจาก Map Dashboard

- เหตุผล: ผู้ตัดสิน hackathon ต้องการ navigate ตรงไปยัง board; map dashboard ควรเน้น real-time monitoring ไม่ต้องแชร์ space กับ ledger timeline; `/board` เป็น standalone Next.js page ทำให้ demo flow ชัดเจนกว่า embedded panel
- trade-off: navigation ข้าม 2 หน้า — แก้ด้วย link จาก header ของ MapDashboard

## 2026-06-24 — P5 Ledger data_class: Column บน ledger_entry แทน Computed จาก Payload

- เหตุผล: G9 "Accountability board shows only ledger-backed, labeled facts. No inference." — ถ้า data_class ถูก derive จาก event_type หรือ payload ในชั้น API นั่นคือ inference ไม่ใช่ labeled fact; column ใน DB ทำให้ label ถูก append พร้อมกับ entry ตอน write-time และไม่เปลี่ยนได้
- trade-off: migration เพิ่มขึ้น 1 ไฟล์; `append_event()` API signature เปลี่ยน (เพิ่ม `data_class` param ที่มี default)

## 2026-06-24 — P5 Ledger Completeness: เพิ่ม WO_CREATED + WO_DISPATCHED Events

- เหตุผล: CLAUDE.md "Every event is appended to the Ledger"; ปัจจุบันมีเฉพาะ VERIFY_OUTCOME + MISMATCH_ESCALATE — board จะเล่าเรื่อง "Created → Dispatched → Verified/Mismatch → Escalate" ไม่ได้; เพิ่ม append_event ใน `create_work_order` (หลัง flush ก่อน commit) และ `confirm_work_order` (ก่อน commit) ให้ทุก event อยู่ใน transaction เดียวกัน
- trade-off: `create_work_order` ต้องเปลี่ยนจาก `flush → commit → refresh` เป็น `flush → append_event → commit → refresh`; ถ้า ledger lock contention สูงจะกระทบ WO creation latency — ยอมรับได้เพราะ WO creation ไม่ใช่ hot path

## 2026-06-24 — P5 Chain Verification: Client-Side SHA-256 แทน API Endpoint

- เหตุผล: client มี `event_type`, `payload` (string), `prev_hash` ครบ — สามารถคำนวณ `SHA-256(event_type|payload|prev_hash)` แล้วเทียบ `hash` จาก API ได้โดยตรงโดยใช้ `crypto.subtle`; ไม่ต้องเพิ่ม API endpoint ใหม่ และแสดงให้เห็นว่า chain สามารถ verify โดยใคร ไม่ต้องพึ่ง server
- trade-off: Ed25519 signature verification ยังเป็น PENDING-WIRE (ต้อง export public key ก่อน); P5 verify เฉพาะ hash chain, ไม่ verify signature

## 2026-06-24 — P6 Smoke Test: Extend Existing Script แทนสร้างใหม่

- เหตุผล: `scripts/smoke_test.py` มี [34] concurrent ingest + [35] node update อยู่แล้ว; สร้างไฟล์ใหม่จะทำให้ `make smoke` ชี้ผิดไฟล์และ context ของ REPORTERS/fixtures ต้อง duplicate; extend ไฟล์เดิมทำให้ test ใช้ state ที่ concurrent ingest สร้างขึ้นได้โดยตรง (หา node ที่มี n_reports ≥ 1 จากผลของ [34])
- trade-off: ไฟล์เดียวยาวขึ้น (~250 → ~500 บรรทัด); ยอมรับได้เพราะเป็น test script ไม่ใช่ production code

## 2026-06-24 — P6 Chain Verify: Python hashlib แทน External Tool

- เหตุผล: test script ต้อง verify SHA-256 chain ด้วยตัวเอง — ถ้าใช้ curl แล้ว pipe ไปหา tool ภายนอกจะมี dependency นอก uv environment; ใช้ `hashlib.sha256` (stdlib) ที่อยู่ใน Python แล้ว เหมือนกับ logic ใน `services/ledger.py`; ผลที่ได้คือ smoke test verify chain ด้วย logic เดียวกับที่ server ใช้สร้าง
- trade-off: ไม่มี — stdlib เท่านั้น ไม่เพิ่ม dependency

## 2026-06-29 — P7 Plan Preview ก่อนสร้าง WO (Human-first Approval)

- เหตุผล: เดิม `POST /work-orders` สร้าง WO และขึ้น dashboard ทันที operator ค่อย approve ทีหลัง ขัดกับ G3 spirit — human ควร approve *ก่อน* state change; เพิ่ม `GET /work-orders/plan-preview` เป็น read-only endpoint (ไม่ write DB) ให้ frontend ดึงแผนจาก orchestrator แสดงใน modal ให้ operator แก้ไขและยืนยัน แล้ว WO ถึงสร้าง; ความหมาย `pending` เปลี่ยน: เดิม = รอ coordinator approve → ใหม่ = coordinator approve แล้ว รอฝ่ายปฏิบัติการ
- trade-off: เพิ่ม round-trip 1 ครั้ง; ยอมรับได้เพราะ WO creation ไม่ใช่ hot path; `plan_dispatch()` เป็น pure function — deterministic ตาม `current_fused_level` ณ ขณะนั้น ไม่ต้อง cache

## 2026-06-29 — P7 approved_by ใน WO_CREATED Ledger + DB Column

- เหตุผล: G9 accountability board ต้องจับ "ใครอนุมัติแผน" ได้ — ledger `WO_CREATED` payload เดิมไม่มี field นี้; เพิ่ม `approved_by` ทั้งใน payload และ `work_order.approved_by` column เพื่อให้ query ได้โดยตรง; แยกชัดจาก `confirmed_by` ที่หมายถึง field ops ยืนยัน; mocked `"Coordinator_01"` ไปก่อนรอ auth
- trade-off: `WorkOrderCreate` มี required field ใหม่ — smoke test และ client ทุกที่ต้องส่ง `approved_by`

## 2026-06-29 — P7 LINE Dispatch แยกออกจาก /confirm เป็น Explicit User Choice

- เหตุผล: เดิม LINE ส่งอัตโนมัติเมื่อ operator กด confirm — operator ไม่มี choice; ย้าย LINE dispatch ไปอยู่ใน creation modal (`notify_line` flag + `line_options`) และ `POST /{id}/notify-line` endpoint แยก สำหรับ resend หลัง edit; `/confirm` กลับมาเป็น pure state transition pending→dispatched; เพิ่ม `line_dispatched` + `line_dispatched_at` columns บน `work_order`
- trade-off: smoke test ที่ call `/confirm` แล้วคาดหวัง LINE ต้องอัปเดต; แต่ semantic ที่ได้ถูกต้องและยืดหยุ่นกว่า

## 2026-06-29 — P7 LINE Options: Checkbox ทุก Field + Live Preview ผ่าน Backend

- เหตุผล: operator เลือกได้ว่าจะส่ง field ใดบ้างใน LINE (node_name, water_level, action_type, assigned_unit + extra_notes); default = ทุก field; preview คำนวณที่ `GET /work-orders/line-preview` เพื่อให้ `send_dispatch()` logic อยู่จุดเดียว ไม่ duplicate ที่ frontend
- trade-off: เพิ่ม round-trip สำหรับ live preview; ใช้ debounce 300ms บน frontend ลด request

## 2026-06-29 — P7 PATCH /work-orders/{id} + WO_UPDATED Ledger Event

- เหตุผล: operator ต้องแก้ action_type/assigned_unit/notes บน pending WO ได้หลังสร้าง; PATCH state-gated (pending only); บันทึก changed_fields/old_values/new_values ลง ledger `WO_UPDATED` เพื่อ audit trail ครบ; ถ้า WO เคยส่ง LINE → response คืน `resend_required=True` ให้ operator เลือกว่าจะ resend หรือไม่
- trade-off: ไม่ auto-resend LINE เพื่อไม่สร้างความสับสนให้ field team เมื่อแก้ field เล็กน้อย

## 2026-06-24 — P4 Ledger Concurrency: pg_advisory_xact_lock แทน SELECT FOR UPDATE

- เหตุผล: `SELECT ... LIMIT 1 FOR UPDATE` บนตารางว่าง (genesis case) ไม่มี row ให้ lock — concurrent transactions ทั้งสองจะได้ GENESIS_HASH เป็น prev_hash พร้อมกัน ทำให้ chain fork; `pg_advisory_xact_lock(key)` แก้ปัญหาได้โดยตรง — transaction แรกที่ได้ lock จะถือไว้จนกว่า commit จึง release ให้ transaction ที่สองเดินต่อ; เรียกซ้ำได้ภายใน transaction เดียวโดยไม่ block (idempotent)
- trade-off: advisory lock serialises ทุก ledger write ทั่วโลก — throughput ต่ำกว่า lock-free approach; ยอมรับได้เพราะ verify event เกิดจาก user action ไม่ใช่ batch ingest

## 2026-07-01 — Database Migration for Legal Authority & Dispatch Guardrails

- เหตุผล: ต้องการนำเข้าข้อมูลความรับผิดชอบเชิงอำนาจกฎหมายและนโยบายความปลอดภัย (Guardrails) จากคลังข้อมูล Floodtirdatta มาเก็บลงฐานข้อมูล PostgreSQL/PostGIS เพื่อให้ระบบหลังบ้านสามารถใช้ควบคุมความปลอดภัยในการสั่งการและการตรวจสอบได้แบบเรียลไทม์ โดยใช้ SQLAlchemy Models คู่กับฟิลด์ JSONB สำหรับฟิลด์ที่เป็น List/Array (เช่น action_codes, authority_provision_hashes) เพื่อลดความซับซ้อนของโครงสร้างตาราง
- trade-off: การใช้ JSONB ทำให้เสียคุณสมบัติ Referential Integrity บางส่วนในระดับของ Database engine (เช่น ไม่สามารถทำ Foreign Key constraint บนข้อมูลในลิสต์ได้โดยตรง) แต่ยอมรับได้เพราะการจัดเตรียมข้อมูลฝั่งจัดเก็บ (Floodtirdatta) มีการตรวจสอบ Schema อย่างเข้มงวดผ่าน JSON Schema ไว้เรียบร้อยแล้ว

