# Spec: BMA Data Import & Conversion from JSON to Postgres/PostGIS

เอกสารสเปกและโครงสร้างการแปลงข้อมูลประวัติระดับน้ำและสถานีวัดน้ำของกรุงเทพมหานคร (BMA) จากไฟล์ JSON ใน `D:\Floodtir\Tanu\floodtir\Floodtirdatta` เข้าสู่ระบบฐานข้อมูลของ `D:\Floodtir\Tanu\floodtir`

---

## 1. จุดประสงค์ (Purpose)
แปลงข้อมูลจริง (REAL observation) จากการวัดระดับน้ำของสำนักการระบายน้ำ กทม. ที่เก็บเป็นไฟล์ JSON ในโฟลเดอร์ `Tanu/floodtir/Floodtirdatta/water-data` นำเข้าตารางฐานข้อมูลของแพลตฟอร์มประสานงาน `Tanu/floodtir` (PostgreSQL/PostGIS/TimescaleDB) เพื่อนำข้อมูลจริงนี้ไปประมวลผลต่อบน dashboard การแจ้งเตือน และการทำนายความสูงพื้นผิวระบายน้ำ (Water Surface Interpolation)

---

## 2. โครงสร้างการจับคู่ข้อมูล (Data Mapping Schema)

### 2.1 ข้อมูลผู้รายงาน (Reporter)
สร้างผู้รายงานระบบหลักของ BMA 1 ราย เพื่อกำหนดสิทธิ์ความน่าเชื่อถือระดับสูงให้กับข้อมูลจากเซนเซอร์จริง:
- **Table:** `reporter`
- **Mapping:**
  - `handle`: `"bma_telemetry"`
  - `trust_score`: `1.0` (ข้อมูลจริงจากเซนเซอร์มีความถูกต้องสูงสุด)
  - `is_simulated`: `False` (เป็นข้อมูล REAL ไม่ใช่ข้อมูลจำลอง)

### 2.2 ข้อมูลสถานี (Flood Node)
แปลงสถานีวัดน้ำทั้ง 283 แห่งจาก `water_all_stations.json`:
- **Table:** `flood_node`
- **Mapping:**
  - `id` ⟵ `station_id` (ใช้ ID เดิมเพื่อให้ง่ายต่อการเชื่อมต่อข้อมูลประวัติ)
  - `name` ⟵ `station_name_th`
  - `geom` ⟵ `ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)` (แปลงพิกัด WGS84 ดิบเป็น PostGIS geography/geometry)
  - `district` ⟵ `district_name_th`
  - `historical_max_level` ⟵ `thresholds.critical_in_m_msl` (ระดับเตือนภัยวิกฤต) 
    - *Fallback:* หากไม่มีค่าเตือนภัยวิกฤต ให้ขยับไปใช้ `levels.left_bank_m_msl` (ระดับตลิ่งซ้าย) ⟶ `levels.water_max_m_msl` ⟶ ค่ามาตรฐาน `1.50` เมตร รทก.
  - `current_fused_level` ⟵ ระดับน้ำล่าสุดของเซนเซอร์จาก snapshot (ถ้ามี)
  - `last_updated` ⟵ เวลาตรวจวัดล่าสุดของเซนเซอร์ (ถ้ามี)
  - `n_reports` ⟵ ตั้งค่าเป็น `1` หรือตามจำนวนข้อมูลประวัติที่มี

### 2.3 ข้อมูลประวัติระดับน้ำ (OSINT Report)
แปลงรายการประวัติระดับน้ำย้อนหลังราย 5 นาทีจาก `station_histories/{station_id}.json` และระดับน้ำล่าสุดจาก `water_latest_snapshot.json`:
- **Table:** `osint_report` (เป็น TimescaleDB hypertable ที่พาร์ทิชันบนคอลัมน์ `ts`)
- **Mapping:**
  - `ts` ⟵ `observed_at_utc` (แปลงจาก ISO datetime ใน JSON เป็น UTC timestamp ของ PostgreSQL)
  - `geom` ⟵ ดึงจาก `geom` ของสถานีเดียวกัน
  - `water_level_m` ⟵ `value_m_msl` (ข้ามหากพบค่า `-99` หรือ `null`)
  - `confidence` ⟵ `1.0` (ความเชื่อมั่น 100% สำหรับข้อมูลจากเซนเซอร์ระบายน้ำจริง)
  - `photo_ref` ⟵ `None`
  - `reporter_id` ⟵ `reporter.id` ของ `"bma_telemetry"`
  - `flood_node_id` ⟵ `station_id`
  - `is_simulated` ⟵ `False` (ติดป้ายข้อมูล REAL ตามหลัก G5)
  - `source_label` ⟵ `"sensor"`

---

## 3. สคริปต์นำเข้าข้อมูล (Seeder Script: `convert_and_seed_bma.py`)
สคริปต์นี้จะถูกเขียนขึ้นที่ `D:\Floodtir\Tanu\floodtir\scripts\convert_and_seed_bma.py` มีคุณสมบัติเพิ่มเติม:
- มีตัวเลือก `--clear` สำหรับล้างข้อมูลเดิมในตาราง `osint_report` และ `flood_node` เฉพาะชุดที่เป็น REAL (หรือทั้งหมด) เพื่อให้รันซ้ำเพื่อนำเข้าข้อมูลได้เรื่อยๆ โดยข้อมูลไม่เกิดการทับซ้อนหรือ Duplicate
- มีตัวเลือก `--limit-history <int>` เพื่อจำกัดจำนวนบันทึกประวัติต่อสถานี (เช่น 50-100 จุดล่าสุด) เพื่อความรวดเร็วในการพัฒนาทดสอบ ไม่ให้มีข้อมูลในตาราง `osint_report` มากเกินไปในขั้นแรก (สามารถรันโดยไม่จำกัดเพื่อนำเข้าทั้งหมดได้)
- ทำการรัน `SELECT setval('flood_node_id_seq', ...)` และ `SELECT setval('osint_report_id_seq', ...)` เสมอหลังเซ็ตค่าเสร็จสิ้น

---

## 4. แผนการตรวจสอบความถูกต้อง (Verification Plan)
1. รันคำสั่งนำเข้าข้อมูล:
   ```bash
   uv run --package api python scripts/convert_and_seed_bma.py --clear --limit-history 50
   ```
2. ตรวจสอบใน Database (เช่น ผ่าน DBeaver หรือคำสั่ง SQL) ว่าตาราง `flood_node` มีแถวข้อมูล 283 แถว และตาราง `osint_report` ถูกสร้างขึ้นโดยมี `is_simulated = false`
3. เรียกใช้ API `GET /flood-nodes` และ `GET /water-surface` ของ `Tanu/floodtir` เพื่อดูความสมบูรณ์ของจุดข้อมูลระดับน้ำจริงบนแผนที่
