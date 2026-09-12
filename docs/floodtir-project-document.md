# Floodtir — Project Document

แพลตฟอร์มประสานงานจัดการน้ำท่วม กทม. ที่ปิด loop: รับรู้ → สั่งการ → พิสูจน์ว่าทำจริง
(BDI Hackathon 2026 OPEN, โจทย์ 3 Safety) — pilot: เขตลาดกระบัง

---

## 1. ปัญหา

รัฐมี observation เยอะแล้ว (ThaiWater, แผนที่น้ำท่วม real-time). ช่องว่างจริงคือ:
1. **เส้นเลือดฝอย/สถานะเครื่องจักรมืด** — ส่วนกลางไม่เห็นซอย ไม่รู้ปั๊มเดินจริงไหม
2. **รู้แล้วไม่ปิด loop** — สั่ง–ติดตาม–ตรวจสอบ–รับผิดชอบไม่ครบวง

ฝนตกฉับพลัน = จุดที่เซนเซอร์มืดสุด → ใช้ crowdsourcing (รูป+พิกัดประชาชน) เติม

## 2. ทางแก้ & จุดต่าง

control-plane ที่เปลี่ยน "คำรายงาน" → "ความจริงที่เครื่อง/ภาพยืนยันได้" + ledger ตรวจสอบย้อนหลังได้
- **ภาพ = พยาน (verify) ไม่ใช่จอเฝ้าดู**
- **ระดับน้ำใช้ label หยาบ (เข่า/เอว)** ไม่ใช่วัดความสูงจากรูป
- **crowdsourcing = เสริม input + verify** ไม่ใช่ระบบทำนาย

---

## 3. สถาปัตยกรรม

**Backbone = Situation Model** (PostGIS + TimescaleDB + pgvector) — single source of truth,
provenance ทุกแถว. รับ 3 ชนิด: REAL observation (น้ำ/ฝน/ทะเล), crowdsourced (รูป+พิกัด+ระดับหยาบ),
generated accountability (edge-IoT = simulated-by-design)

ชั้นรอบ:
- **MCP tools (อ่านอย่างเดียว):** `query_situation/assets/sop/history` + `propose`(confirm-gated) — log ทุก call
- **RAG:** ground narration ด้วย SOP + เกณฑ์ รทก. + registry (pgvector, embedding จริง ไม่ใช่ placeholder)
- **Ledger:** hash-chain + Ed25519 + append-only trigger
- **Dashboard:** provenance cards + ป้าย real/simulated/last-update

**Agent:** 2 LLM agent (Triage, Narrator) + N data worker (ETL/loader/early-warning) +
orchestrator/command แบบ deterministic

## 4. โมเดล AI

- **LLM แตะแค่ 3 หน้าที่:** เข้าใจภาษา/คำสั่ง · มองภาพ (VLM) · เรียบเรียง
  **ไม่เลือกหน่วย/ปั๊ม ไม่เปลี่ยนสถานะงาน ไม่ตัดสิน mismatch ไม่สั่งงานเอง**
- **โมเดล: ThaiLLM 30B instruct ที่มีอยู่** (ThaiLLM NSTDA 30B หรือ Typhoon 2.5 30B-A3B)
  **ห้าม fine-tune base เอง** (base ทำตามคำสั่ง/JSON/tool-calling ไม่ได้)
- ปรับเฉพาะทางด้วย **RAG + prompt** ไม่ใช่ train
- โมเดล = config ที่ swap ได้ (Ollama/API, OpenAI-compatible) ไม่ต้องรื้อสถาปัตยกรรม

---

## 5. Data Model (เพิ่มจาก schema เดิม)

- `reporter` — citizen/OSINT source: id, handle?, trust_score, is_simulated
- `osint_report` (hypertable) — point, water_level_obs, photo_ref, reporter_id, ts, confidence, node_id, is_simulated
- `flood_node` — sampling node จาก flood-extent 2554: point, historical_max_level, current_fused_level, last_updated, n_reports
- `water_surface` (derived/cached) — interpolated grid/contours, regenerate on ingest
- เพิ่ม `verification.citizen_corroboration` เป็น input จริง
- reuse เดิม: `work_order, verification, ledger, unit, asset`

## 6. Workflow

**2 ทางเข้า:** Loop A เชิงรุก (sensor + ความหนาแน่นรายงาน → early-warning เด้งเอง) /
Loop B เชิงรับ (ประชาชนแจ้ง → triage)

| Phase | input → process → output |
|---|---|
| INGEST | รูป+พิกัด+ระดับหยาบ → triage [LLM+VLM] + quality (dedup/geofence/anti-injection) → claim + provenance |
| FUSE | หลายรายงาน/node → corroboration + interpolation (IDW/contour) → พื้นผิวความเชื่อมั่น (ไม่ใช่ความสูงแม่นยำ) |
| PREDICT | situation (3 น้ำ + density) → early-warning score [DET] → จุดเสี่ยง + เหตุผล |
| PLAN | alert/คำสั่งไทย → intent [LLM] → routing [DET PostGIS] → narrate [RAG+LLM] → ข้อเสนอ (LLM ไม่เลือกปั๊มเอง) |
| gate | → มนุษย์ยืนยัน → คำสั่งมีผู้รับผิดชอบ |
| ACT | confirm → state machine [DET] → LINE → field → รูปกลับ |
| REPORT | "เสร็จ" + Field(รูป)+Machine(edge-IoT)+Outcome(น้ำลด)+Citizen(รูปรอบใหม่) → verify → VERIFIED/MISMATCH |
| LOOP | MISMATCH → escalate WO ใหม่ → วนกลับ PLAN |
| LEDGER | ทุก event → hash-chain + sign |

claim → truth เกิดที่ REPORT; ตรึงถาวรที่ LEDGER

## 7. Guardrails

G1 LLM แค่ parse/narrate/มองภาพ · G2 command deterministic · G3 human confirm ก่อน dispatch ·
G4 ไม่ blockchain · G5 ติดป้าย `is_simulated` · G6 secrets ผ่าน env ·
G7 observation ≠ truth (รายงานเดี่ยวไม่สั่งงาน/ชี้ผิดเอง ต้อง corroborate ≥N) ·
G8 provenance + anti-abuse (กัน sybil/spam) · G9 accountability board ต้อง factual + ledger-backed + labeled

---

## 8. Scope & แนวทาง

- เดโม **1 เขต (ลาดกระบัง)** + seed flood_node ทั้ง กทม. ให้แผนที่ดูจริง
- **evolve repo เดิม (branch) ไม่ rewrite** — spine + ledger + guardrails validate แล้ว
- interpolation = **IDW + contour** (ไม่ใช่ kriging)
- ข้อควรกรอบ: node 2554 = baseline วางหมุด **ไม่ใช่โมเดลพยากรณ์**; contour = ความเชื่อมั่น/ความรุนแรงโดยประมาณ **ไม่ใช่ความสูงเป็นเมตร**
- CCTV/zero-shot = future (ไม่ทำตอนนี้)

## 9. Build Phases

- **P0 Scaffold:** branch repo + ตาราง `reporter/osint_report/flood_node` + loaders
- **P1 Data input:** intake endpoint (รูป+ระดับ) + seed node 2554 + datagen หลายผู้รายงานพร้อมกัน + fusion/node
  — *exit: ผู้รายงานจำลอง 10 คนโพสต์พร้อมกัน → ระดับบนแผนที่อัปเดต*
  
- **P2 Water surface:** IDW/contour → frontend layer; early-warning จาก fused node
- **P3 Dispatch spine:** intent → routing → confirm → LINE บนสัญญาณ crowdsourced
- **P4 Citizen-photo verify:** ขยาย `verify.run()` ให้ภาพประชาชน corroborate/contradict ร่วมกับ vibration + water-delta → MISMATCH → escalate → ledger
- **P5 Accountability board:** ledger-backed, labeled
- **P6 Validate:** smoke test ครอบคลุม concurrent ingest, fusion, citizen-corroborated MISMATCH

**Wiring ที่ต้องทำจริงควบคู่:** เปิด ThaiLLM 30B instruct · MCP tools · RAG จริง · eval 20 prompt ไทย

## 10. ความจริงของระบบ (ติดป้ายให้ตรง)

- **REAL:** ledger, routing PostGIS, state machine, mismatch logic, situation model, RBAC, crowdsourced intake + fusion, ข้อมูล swap 1 เขต
- **SIMULATED-by-design:** edge-IoT, field/LINE, ผู้รายงานจำลอง
- **PENDING-WIRE:** ThaiLLM 30B instruct, RAG, MCP
- **PLANNED:** tide/upstream เต็มรูป, CCTV video, hydraulic simulation

---

*หลักการที่ไม่ยอมแลก: constrain-the-model · deterministic command · human gate · หยาบแต่จริง · ติดป้ายความจริง · อย่าเคลมเกินกว่าที่สร้าง*
